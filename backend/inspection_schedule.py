"""Quarterly/monthly scheduling intent, with record-derived, read-only completion."""
import json
import logging
from collections import defaultdict

from flask import g, jsonify, request

from inspection_schedule_catalog import COLUMNS, normalized_region, roster_position
from roles import SUPERVISOR_ROLES
from scheduling_map import period
from station_plan_eligibility import plan_field

VIEW_PERMISSION = 'view_inspection_schedule'
EDIT_PERMISSION = 'edit_inspection_schedule'


class ScheduleConflict(ValueError):
    pass


def person(row):
    return dict(id=row['id'], username=row.get('username') or '', role=row.get('role') or '',
                display_name=str(row.get('real_name') or '').strip() or row.get('username') or '未记录姓名')


def period_number(chosen):
    return chosen['quarter' if chosen['mode'] == 'offline' else 'month']


def table_columns(cur, mode, table_scope, lock=False):
    clauses, params = table_scope
    names = [entry[2] for entry in COLUMNS[mode]]
    cur.execute('''SELECT t.id,t.table_name FROM inspection_tables t
        WHERE t.checklist_mode=%s AND t.is_active=TRUE AND t.table_name=ANY(%s) AND ''' +
                ' AND '.join(clauses or ['TRUE']) + (' FOR SHARE OF t' if lock else ''),
                [mode, names, *params])
    by_name = defaultdict(list)
    for row in cur.fetchall():
        by_name[row['table_name']].append(row['id'])
    # Ambiguous or missing definitions must not silently attach to a different table.
    return [dict(key=key, label=label, full_name=name,
                 table_id=by_name[name][0] if len(by_name[name]) == 1 else None)
            for key, label, name in COLUMNS[mode]]


def scoped_stations(cur, chosen, station_scope, station_id=None, lock=False):
    clauses, params = station_scope
    clauses = [*clauses, f's.{plan_field(chosen["mode"])}=TRUE']
    params = list(params)
    if station_id is not None:
        clauses.append('s.id=%s')
        params.append(station_id)
    cur.execute('SELECT s.id,s.station_name,s.region FROM stations s WHERE ' +
                ' AND '.join(clauses or ['TRUE']) + (' FOR SHARE OF s' if lock else ''), params)
    rows = [dict(row, sequence=roster_position(row, chosen['mode'])) for row in cur.fetchall()]
    return sorted((row for row in rows if row['sequence']), key=lambda row: (row['sequence'], row['id']))


def record_cells(cur, station_ids, table_ids, start, end):
    if not station_ids or not table_ids:
        return {}
    cur.execute('''WITH matched AS MATERIALIZED (
        SELECT id,station_id,inspection_table_id,inspector_id,inspection_date FROM inspections
        WHERE station_id=ANY(%s) AND inspection_table_id=ANY(%s)
          AND inspection_date >= %s AND inspection_date < %s
      ), participants AS (
        SELECT id AS inspection_id,inspector_id FROM matched WHERE inspector_id IS NOT NULL
        UNION
        SELECT i.inspection_id,i.inspector_id FROM issues i JOIN matched m ON m.id=i.inspection_id
        WHERE i.inspector_id IS NOT NULL
      ) SELECT m.station_id,m.inspection_table_id,COUNT(DISTINCT m.id) AS record_count,
        MAX(m.inspection_date)::text AS last_inspection_date,
        COALESCE(jsonb_agg(DISTINCT jsonb_build_object('id',u.id,'username',u.username,
          'display_name',COALESCE(NULLIF(TRIM(u.real_name),''),u.username),'role',u.role))
          FILTER(WHERE u.id IS NOT NULL),'[]') AS inspectors
      FROM matched m LEFT JOIN participants p ON p.inspection_id=m.id LEFT JOIN users u ON u.id=p.inspector_id
      GROUP BY m.station_id,m.inspection_table_id''', (station_ids, table_ids, start, end))
    return {(row['station_id'], row['inspection_table_id']): dict(row) for row in cur.fetchall()}


def read_board(cur, chosen, start, end, station_scope, table_scope):
    columns = table_columns(cur, chosen['mode'], table_scope)
    stations = scoped_stations(cur, chosen, station_scope)
    station_ids = [row['id'] for row in stations]
    complete = record_cells(cur, station_ids, [col['table_id'] for col in columns if col['table_id']], start, end)
    cur.execute('''SELECT c.*,COALESCE(NULLIF(TRIM(u.real_name),''),u.username,'未记录') AS updated_by_name,
      to_char(c.updated_at,'YYYY-MM-DD HH24:MI:SS') AS saved_at
      FROM inspection_schedule_cells c LEFT JOIN users u ON u.id=c.updated_by
      WHERE c.mode=%s AND c.year=%s AND c.period_number=%s AND c.station_id=ANY(%s)''',
                (chosen['mode'], chosen['year'], period_number(chosen), station_ids))
    saved = {(row['station_id'], row['column_key']): row for row in cur.fetchall()}
    saved_ids = sorted({int(uid) for row in saved.values() for uid in row['inspector_ids']})
    cur.execute('SELECT id,username,real_name,role FROM users WHERE id=ANY(%s)', (saved_ids,))
    people = {row['id']: person(row) for row in cur.fetchall()}
    cur.execute('''SELECT id,username,real_name,role FROM users WHERE role=ANY(%s)
      AND COALESCE(account_status,'active')='active' ORDER BY role,real_name,username,id''', (list(SUPERVISOR_ROLES),))
    inspectors = [person(row) for row in cur.fetchall()]
    rows = []
    summary = dict(completed=0, assigned=0, unassigned=0)
    for station in stations:
        cells = {}
        for column in columns:
            existing = saved.get((station['id'], column['key'])) or {}
            record = complete.get((station['id'], column['table_id'])) or {}
            assignees = [people.get(uid, dict(id=uid, username='', role='', display_name='账号已删除'))
                         for uid in existing.get('inspector_ids', [])]
            status = 'unavailable' if not column['table_id'] else 'completed' if record else 'assigned' if assignees else 'unassigned'
            if status in summary:
                summary[status] += 1
            cells[column['key']] = dict(status=status, assignees=assignees,
                completed_inspectors=sorted(record.get('inspectors', []), key=lambda user: (user['display_name'], user['id'])),
                record_count=record.get('record_count', 0), last_inspection_date=record.get('last_inspection_date'),
                revision=existing.get('revision', 0), updated_by_name=existing.get('updated_by_name', ''),
                updated_at=existing.get('saved_at', ''))
        rows.append(dict(station_id=station['id'], station_name=station['station_name'],
                         region=normalized_region(station['region']), sequence=station['sequence'], cells=cells))
    return dict(period=chosen, columns=columns, rows=rows, inspectors=inspectors, summary=summary)


def integer(value, label, minimum=1):
    if type(value) is not int or value < minimum:
        raise ValueError(f'{label}不合法。')
    return value


def save_cell(cur, actor, data, chosen, start, end, station_scope, table_scope):
    station_id = integer(data.get('station_id'), '站点')
    key = data.get('column_key')
    if not isinstance(key, str) or key not in {entry[0] for entry in COLUMNS[chosen['mode']]}:
        raise ValueError('检查表列不合法。')
    revision = integer(data.get('revision'), '版本', 0)
    ids = data.get('inspector_ids')
    if not isinstance(ids, list) or len(ids) > 100:
        raise ValueError('请选择督导组检查人，最多100人。')
    ids = sorted({integer(value, '检查人') for value in ids})
    cell_key = (chosen['mode'], chosen['year'], period_number(chosen), station_id, key)
    # Cross-worker serialization plus a revision check avoids lost updates and ABA on clears.
    cur.execute('SELECT pg_advisory_xact_lock(9701,hashtext(%s))', (json.dumps(cell_key),))
    stations = scoped_stations(cur, chosen, station_scope, station_id, lock=True)
    if len(stations) != 1:
        raise PermissionError('本站不在可编辑名单、账号范围内，或已关闭对应计划纳入。')
    column = next(col for col in table_columns(cur, chosen['mode'], table_scope, lock=True) if col['key'] == key)
    if not column['table_id']:
        raise PermissionError('检查表未启用、定义不唯一或不在账号可编辑范围内。')
    if record_cells(cur, [station_id], [column['table_id']], start, end):
        raise ScheduleConflict('该站点本周期已有此检查表的巡检记录，单元格已完成，不能再分配。')
    cur.execute('''SELECT inspector_ids,revision FROM inspection_schedule_cells
      WHERE mode=%s AND year=%s AND period_number=%s AND station_id=%s AND column_key=%s FOR UPDATE''', cell_key)
    existing = cur.fetchone() or dict(inspector_ids=[], revision=0)
    if existing['revision'] != revision:
        raise ScheduleConflict('该单元格已被其他用户修改，请刷新最新排班后再调整。')
    if ids:
        cur.execute('''SELECT id FROM users WHERE id=ANY(%s) AND role=ANY(%s)
          AND COALESCE(account_status,'active')='active' ORDER BY id FOR SHARE''', (ids, list(SUPERVISOR_ROLES)))
        if {row['id'] for row in cur.fetchall()} != set(ids):
            raise ValueError('只能选择当前启用的督导组管理人员或督导组组员，请重新选择。')
    if existing['inspector_ids'] == ids:
        return existing['revision']
    cur.execute('''INSERT INTO inspection_schedule_cells
        (mode,year,period_number,station_id,column_key,inspector_ids,revision,updated_by)
      VALUES (%s,%s,%s,%s,%s,%s,1,%s) ON CONFLICT (mode,year,period_number,station_id,column_key)
      DO UPDATE SET inspector_ids=EXCLUDED.inspector_ids,revision=inspection_schedule_cells.revision+1,
        updated_by=EXCLUDED.updated_by,updated_at=CURRENT_TIMESTAMP RETURNING revision''',
                (*cell_key, json.dumps(ids), actor['id']))
    saved_revision = cur.fetchone()['revision']
    cur.execute('''INSERT INTO inspection_schedule_events
      (mode,year,period_number,station_id,station_name,column_key,before_ids,after_ids,actor_id,actor_name)
      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
      (chosen['mode'], chosen['year'], period_number(chosen), station_id, stations[0]['station_name'], key,
       json.dumps(existing['inspector_ids']), json.dumps(ids), actor['id'], person(actor)['display_name']))
    return saved_revision


def register_inspection_schedule(app, *, connect, has_permission, scope):
    @app.route('/api/inspection-schedule', methods=['GET', 'PUT'])
    def inspection_schedule_board():
        actor = getattr(g, 'current_user', None)
        if not actor:
            return jsonify(success=False, error='请先登录。'), 401
        conn = cur = None
        try:
            conn = connect()
            cur = conn.cursor()
            if not has_permission(cur, actor, VIEW_PERMISSION):
                raise PermissionError('当前账号无权查看巡检计划。')
            can_edit = has_permission(cur, actor, EDIT_PERMISSION)
            if request.method == 'PUT' and not can_edit:
                raise PermissionError('当前账号只有查看权限，不能编辑排班。')
            data = request.get_json(silent=True) if request.method == 'PUT' else request.args
            if data is None or not hasattr(data, 'get'):
                raise ValueError('请提交有效的排班数据。')
            chosen, start, end = period(data)
            station_scope, table_scope = scope(cur, actor)
            cur.execute("SET LOCAL statement_timeout = '10s'")
            if request.method == 'PUT':
                revision = save_cell(cur, actor, data, chosen, start, end, station_scope, table_scope)
                conn.commit()
                result = dict(revision=revision, message='排班已保存，暂不推送待办任务。')
            else:
                result = read_board(cur, chosen, start, end, station_scope, table_scope)
            response = jsonify(success=True, can_edit=can_edit, **result)
            response.headers['Cache-Control'] = 'private, no-store'
            return response
        except (ValueError, PermissionError) as exc:
            if conn:
                conn.rollback()
            status = 409 if isinstance(exc, ScheduleConflict) else 403 if isinstance(exc, PermissionError) else 400
            return jsonify(success=False, error=str(exc)), status
        except Exception:
            if conn:
                conn.rollback()
            logging.exception('Inspection schedule request failed')
            return jsonify(success=False, error='排班数据暂时无法处理，请稍后重试。'), 500
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
