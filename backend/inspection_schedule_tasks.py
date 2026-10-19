"""Personal dispatch inbox; completion follows actual records, never a manual checkbox."""
import json
import logging
from flask import g, jsonify
from schedule_common import today


def sync_tasks(cur, user_id):
    cur.execute('SELECT pg_try_advisory_xact_lock(9801,1) AS acquired')
    if not cur.fetchone()['acquired']:
        return  # A dispatch is in progress; the next notification refresh reconciles it.
    cur.execute('''UPDATE inspection_schedule_tasks task SET status='pending',completed_at=NULL,completion_inspection_id=NULL
      WHERE user_id=%s AND status='completed' AND NOT EXISTS (
        SELECT 1 FROM inspections ins WHERE ins.id=task.completion_inspection_id
        AND ins.station_id=task.station_id AND ins.inspection_table_id=task.table_id
        AND ins.inspection_date>=task.period_start AND ins.inspection_date<=%s)
      AND NOT EXISTS(SELECT 1 FROM inspection_schedule_tasks newer WHERE newer.user_id=task.user_id
        AND newer.mode=task.mode AND newer.year=task.year AND newer.period_number=task.period_number
        AND newer.station_id=task.station_id AND newer.column_key=task.column_key AND newer.status='pending')''', (user_id, today()))
    cur.execute('''UPDATE inspection_schedule_tasks SET status='cancelled',cancelled_at=CURRENT_TIMESTAMP
      WHERE user_id=%s AND status='pending' AND (station_id IS NULL OR table_id IS NULL)''', (user_id,))
    # These are coverage tasks, using the same record-based completion as the matrix.
    # Another inspector, early work and cross-period catch-up must not leave a locked cell's task stuck.
    cur.execute('''WITH matches AS (
      SELECT task.id,MIN(ins.id) AS inspection_id FROM inspection_schedule_tasks task
      JOIN inspections ins ON ins.station_id=task.station_id AND ins.inspection_table_id=task.table_id
        AND ins.inspection_date >= task.period_start
        AND ins.inspection_date <= %s
      WHERE task.user_id=%s AND task.status='pending'
      GROUP BY task.id
    ) UPDATE inspection_schedule_tasks task SET status='completed',completion_inspection_id=matches.inspection_id,
      completed_at=CURRENT_TIMESTAMP FROM matches WHERE task.id=matches.id AND task.status='pending' ''', (today(), user_id))


def task_count(cur, user_id):
    sync_tasks(cur, user_id)
    cur.execute("SELECT COUNT(*) AS n FROM inspection_schedule_tasks WHERE user_id=%s AND status='pending' AND scheduled_date<=%s", (user_id, today()))
    return int(cur.fetchone()['n'])


def dispatch_tasks(cur, actor, chosen, station, column, ids, day, start):
    key = (chosen['mode'], chosen['year'], chosen.get('quarter', chosen.get('month')), station['id'], column['key'])
    cur.execute('''UPDATE inspection_schedule_tasks task SET status='cancelled',cancelled_at=CURRENT_TIMESTAMP
      WHERE mode=%s AND year=%s AND period_number=%s AND station_id=%s AND column_key=%s AND status='completed'
      AND NOT EXISTS(SELECT 1 FROM inspections ins WHERE ins.id=task.completion_inspection_id
        AND ins.station_id=task.station_id AND ins.inspection_table_id=task.table_id
        AND ins.inspection_date>=task.period_start AND ins.inspection_date<=%s)''', (*key, today()))
    cur.execute('''UPDATE inspection_schedule_tasks SET status='cancelled',cancelled_at=CURRENT_TIMESTAMP
      WHERE mode=%s AND year=%s AND period_number=%s AND station_id=%s AND column_key=%s
      AND status='pending' AND (scheduled_date IS DISTINCT FROM %s OR NOT(user_id=ANY(%s)))''', (*key, day, ids))
    if not ids:
        return
    cur.execute('''UPDATE inspection_schedule_tasks SET team_ids=%s
      WHERE mode=%s AND year=%s AND period_number=%s AND station_id=%s AND column_key=%s AND status='pending' ''', (json.dumps(ids), *key))
    for uid in ids:
        cur.execute('''INSERT INTO inspection_schedule_tasks(mode,year,period_number,station_id,column_key,
          station_name,table_id,table_name,user_id,team_ids,scheduled_date,period_start,created_by)
          SELECT %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s WHERE NOT EXISTS (
            SELECT 1 FROM inspection_schedule_tasks WHERE mode=%s AND year=%s AND period_number=%s
            AND station_id=%s AND column_key=%s AND user_id=%s AND status='pending')''',
          (*key, station['station_name'], column['table_id'], column['full_name'], uid, json.dumps(ids), day, start, actor['id'], *key, uid))


def register_schedule_tasks(app, *, connect):
    @app.get('/api/my-schedule-tasks')
    def my_schedule_tasks():
        actor = getattr(g, 'current_user', None)
        if not actor:
            return jsonify(success=False, error='请先登录。'), 401
        conn = cur = None
        try:
            conn = connect(); cur = conn.cursor()
            count = task_count(cur, actor['id'])
            cur.execute('''SELECT id,mode,station_id,station_name,table_id,table_name,
              scheduled_date::text,status,completion_inspection_id
              FROM inspection_schedule_tasks WHERE user_id=%s AND status='pending' AND scheduled_date<=%s
              ORDER BY scheduled_date,mode,station_name,id LIMIT 500''', (actor['id'], today()))
            rows = [dict(row) for row in cur.fetchall()]
            conn.commit()
            response = jsonify(success=True, today=today().isoformat(), count=count, tasks=rows)
            response.headers['Cache-Control'] = 'private, no-store'
            return response
        except Exception:
            if conn: conn.rollback()
            logging.exception('Schedule inbox failed')
            return jsonify(success=False, error='巡检待办暂时无法读取，请稍后重试。'), 500
        finally:
            if cur: cur.close()
            if conn: conn.close()
