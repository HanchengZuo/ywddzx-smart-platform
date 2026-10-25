"""Read-only matrix management, with an independently assignable permission."""
from datetime import datetime, timezone
import logging
from flask import g, jsonify, request
from driving_matrix import LOCK_ID, VIEW_PERMISSION, next_refresh, snapshot_hash, station_snapshot


def serialize(row):
    return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in dict(row).items()}


def read_status(cur):
    cur.execute('''SELECT r.* FROM driving_matrix_state s JOIN driving_matrix_runs r
        ON r.id=s.active_run_id WHERE s.id=1''')
    active = cur.fetchone()
    cur.execute('SELECT * FROM driving_matrix_runs ORDER BY id DESC LIMIT 10')
    runs = cur.fetchall()
    cur.execute('''SELECT EXISTS(SELECT 1 FROM pg_locks WHERE locktype='advisory' AND classid=0
        AND objid=%s AND granted AND database=(SELECT oid FROM pg_database WHERE datname=current_database())) AS running''', (LOCK_ID,))
    running = cur.fetchone()['running']
    current, invalid = station_snapshot(cur)
    latest = serialize(runs[0]) if runs else None
    if latest and latest['status'] == 'collecting' and not running:
        latest['status'] = 'interrupted'
    return dict(active=serialize(active) if active else None, latest=latest,
                runs=[serialize({k: v for k, v in r.items() if k not in ('stations', 'invalid_stations')}) for r in runs], worker_running=running,
                current_station_count=len(current), invalid_stations=invalid,
                registry_changed=bool(active and active['station_hash'] != snapshot_hash(current)),
                next_refresh_at=next_refresh(datetime.now(timezone.utc)).isoformat())


def register_driving_matrix(app, *, connect, has_permission):
    @app.get('/api/management/driving-matrix')
    def matrix_page():
        actor = getattr(g, 'current_user', None)
        if not actor:
            return jsonify(success=False, error='请先登录。'), 401
        conn = None
        try:
            conn = connect()
            with conn.cursor() as cur:
                if not has_permission(cur, actor, VIEW_PERMISSION):
                    return jsonify(success=False, error='当前账号无权查看路网数据。'), 403
                status = read_status(cur)
                active = status['active']
                page = int(request.args.get('page', 1))
                if not 1 <= page <= 100000:
                    raise ValueError()
                where, params = ['run_id=%s'], [active['id'] if active else 0]
                for name in ('station', 'counterpart'):
                    value = request.args.get(name, '')
                    if value:
                        sid = int(value)
                        where.append('(origin_id=%s OR destination_id=%s)'); params.extend([sid, sid])
                keyword = request.args.get('keyword', '').strip()
                if len(keyword) > 80:
                    raise ValueError()
                if keyword:
                    # Search the published names, not live archives that may
                    # have changed since this dataset was collected.
                    matching = [s['station_id'] for s in (active['stations'] if active else [])
                                if keyword.casefold() in s['station_name'].casefold()]
                    where.append('(origin_id=ANY(%s) OR destination_id=ANY(%s))')
                    params.extend([matching, matching])
                state = request.args.get('state', '')
                if state not in ('', 'reachable', 'unreachable'):
                    raise ValueError()
                if state:
                    where.append('reachable=%s'); params.append(state == 'reachable')
                orders = {'': 'origin_id,destination_id', 'fastest': 'seconds ASC NULLS LAST,origin_id,destination_id',
                          'slowest': 'seconds DESC NULLS LAST,origin_id,destination_id',
                          'distance_asc': 'meters ASC NULLS LAST,origin_id,destination_id',
                          'distance_desc': 'meters DESC NULLS LAST,origin_id,destination_id'}
                order = request.args.get('sort', '')
                if order not in orders:
                    raise ValueError()
                predicate = ' AND '.join(where)
                cur.execute('SELECT COUNT(*) AS total FROM driving_matrix_pairs WHERE ' + predicate, params)
                total = cur.fetchone()['total']
                cur.execute('SELECT * FROM driving_matrix_pairs WHERE ' + predicate + ' ORDER BY ' + orders[order] + ' LIMIT 30 OFFSET %s', params + [(page-1)*30])
                items = [serialize(r) for r in cur.fetchall()]
                names = {s['station_id']: s for s in active['stations']} if active else {}
                for item in items:
                    item['origin'] = names.get(item['origin_id'])
                    item['destination'] = names.get(item['destination_id'])
                result = dict(success=True, **status, items=items, total=total, page=page, page_size=30)
            response = jsonify(result)
            response.headers['Cache-Control'] = 'private, no-store'
            return response
        except (ValueError, TypeError):
            return jsonify(success=False, error='路网查询条件不正确。'), 400
        except Exception:
            logging.exception('Driving matrix read failed')
            return jsonify(success=False, error='路网数据库暂不可用，请检查数据库升级。'), 503
        finally:
            if conn:
                conn.close()
