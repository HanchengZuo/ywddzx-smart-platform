"""Dedicated initial/weekly collector; never runs from Flask requests or imports."""
from datetime import datetime, timezone
import os
import time
from psycopg2.extras import Json, execute_values

from amap_driving import DrivingUnavailable, fetch_distance, parse_results
from driving_matrix import LOCK_ID, latest_slot, next_refresh, station_snapshot, snapshot_hash


def run_refresh(connect, *, now=None, fetch=fetch_distance, sleep=time.sleep, interval=0.65):
    now = now or datetime.now(timezone.utc)
    lease = connect()
    lease.autocommit = True
    run_id = None
    try:
        with lease.cursor() as cur:
            cur.execute('SELECT pg_try_advisory_lock(%s) AS acquired', (LOCK_ID,))
            if not cur.fetchone()['acquired']:
                return dict(status='busy')
            cur.execute('''SELECT r.finished_at FROM driving_matrix_state s JOIN driving_matrix_runs r
                ON r.id=s.active_run_id WHERE s.id=1''')
            active = cur.fetchone()
            slot = latest_slot(now)
            if active and active['finished_at'] >= datetime.fromisoformat(slot):
                return dict(status='not_due', next_refresh=next_refresh(now).isoformat())
            slot = slot if active else 'initial-v1'
            cur.execute('SELECT * FROM driving_matrix_runs WHERE slot=%s', (slot,))
            run = cur.fetchone()
            if run and run['status'] == 'published':
                return dict(status='not_due')
            if run:
                run_id, stations = run['id'], run['stations']
                cur.execute("UPDATE driving_matrix_runs SET status='collecting',last_error=NULL,attempts=attempts+1,heartbeat_at=CURRENT_TIMESTAMP WHERE id=%s", (run_id,))
            else:
                stations, invalid = station_snapshot(cur)
                cur.execute('''INSERT INTO driving_matrix_runs(slot,status,stations,invalid_stations,station_hash,expected_pairs)
                    VALUES(%s,'collecting',%s,%s,%s,%s) RETURNING id''',
                    (slot, Json(stations), Json(invalid), snapshot_hash(stations), len(stations) * (len(stations)-1)//2))
                run_id = cur.fetchone()['id']
        key = os.environ.get('AMAP_WEB_SERVICE_KEY', '').strip() or os.environ.get('AMAP_KEY', '').strip()
        if len(stations) > 1 and not key:
            raise DrivingUnavailable('未配置高德Web服务Key，未更新路网数据库。')
        for destination in stations:
            with lease.cursor() as cur:
                cur.execute('SELECT origin_id FROM driving_matrix_pairs WHERE run_id=%s AND destination_id=%s', (run_id, destination['station_id']))
                completed = {r['origin_id'] for r in cur.fetchall()}
            pending = [s for s in stations if s['station_id'] < destination['station_id'] and s['station_id'] not in completed]
            for offset in range(0, len(pending), 100):
                batch = pending[offset:offset+100]
                sleep(interval)
                with lease.cursor() as cur:
                    cur.execute('UPDATE driving_matrix_runs SET api_requests=api_requests+1,heartbeat_at=CURRENT_TIMESTAMP WHERE id=%s', (run_id,))
                values = parse_results(fetch(key, [s['point'] for s in batch], destination['point'], 12), len(batch))
                conn = connect()
                try:
                    with conn.cursor() as cur:
                        execute_values(cur, '''INSERT INTO driving_matrix_pairs(run_id,origin_id,destination_id,seconds,meters,reachable)
                            VALUES %s ON CONFLICT DO NOTHING''',
                            [(run_id, s['station_id'], destination['station_id'],
                              values[i]['seconds'] if values[i] else None, values[i]['meters'] if values[i] else None,
                              values[i] is not None) for i, s in enumerate(batch)])
                        cur.execute('''UPDATE driving_matrix_runs r SET completed_pairs=p.total,unreachable_pairs=p.unreachable,
                            heartbeat_at=CURRENT_TIMESTAMP FROM (SELECT COUNT(*) total,COUNT(*) FILTER(WHERE NOT reachable) unreachable
                            FROM driving_matrix_pairs WHERE run_id=%s) p WHERE r.id=%s''', (run_id, run_id))
                    conn.commit()
                finally:
                    conn.close()
        conn = connect()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT COUNT(*) AS n FROM driving_matrix_pairs WHERE run_id=%s', (run_id,))
                total = cur.fetchone()['n']
                if total != len(stations) * (len(stations)-1)//2:
                    raise DrivingUnavailable('站间数据不完整，保留上一批有效路网。')
                cur.execute("UPDATE driving_matrix_runs SET status='published',last_error=NULL,finished_at=CURRENT_TIMESTAMP,heartbeat_at=CURRENT_TIMESTAMP WHERE id=%s", (run_id,))
                cur.execute('UPDATE driving_matrix_state SET active_run_id=%s,published_at=CURRENT_TIMESTAMP WHERE id=1', (run_id,))
                # Keep one previous full generation. Preview evidence embeds its
                # own estimates and does not depend on historical pair rows.
                cur.execute('''DELETE FROM driving_matrix_pairs WHERE run_id IN (SELECT id FROM driving_matrix_runs
                    WHERE status='published' ORDER BY id DESC OFFSET 2)''')
            conn.commit()
        finally:
            conn.close()
        return dict(status='published', run_id=run_id, pairs=total, next_refresh=next_refresh(now).isoformat())
    except Exception as exc:
        if run_id:
            # Vendor URLs/keys are redacted by the transport; unexpected errors
            # are represented by a fixed message, never a raw exception repr.
            message = str(exc) if isinstance(exc, DrivingUnavailable) else '采集任务中断，已保留完成部分，可由定时任务续采；上一批数据不受影响。'
            with lease.cursor() as cur:
                cur.execute("UPDATE driving_matrix_runs SET status='failed',last_error=%s,heartbeat_at=CURRENT_TIMESTAMP WHERE id=%s", (message, run_id))
        raise
    finally:
        try:
            with lease.cursor() as cur:
                cur.execute('SELECT pg_advisory_unlock(%s)', (LOCK_ID,))
        finally:
            lease.close()
