"""Personal dispatch inbox; completion follows actual records, never a manual checkbox."""
import json
import logging
from flask import g, jsonify, request
from schedule_common import today
from staff_availability import STAFF, ensure_today_availability
from schedule_task_progress import PROGRESS_SQL, params, coverage_end_sql, inbox_summary, inbox_page, BUCKETS


def sync_tasks(cur, user_id):
    cur.execute('SELECT pg_try_advisory_xact_lock(9801,1) AS acquired')
    if not cur.fetchone()['acquired']:
        return  # A dispatch is in progress; the next notification refresh reconciles it.
    cur.execute('''UPDATE inspection_schedule_tasks SET status='cancelled',cancelled_at=CURRENT_TIMESTAMP
      WHERE user_id=%s AND status='pending' AND (station_id IS NULL OR table_id IS NULL)''', (user_id,))
    # Cache reconciles lazily under the existing try-lock. Reads below use the
    # record projection directly, so contention cannot hide new completion.
    cur.execute(PROGRESS_SQL+'''UPDATE inspection_schedule_tasks task
      SET status=p.effective_status,completion_inspection_id=p.inspection_id,
        completed_at=CASE WHEN p.effective_status='completed' THEN COALESCE(task.completed_at,CURRENT_TIMESTAMP) ELSE NULL END
      FROM progress p WHERE task.id=p.id AND p.effective_status IN ('pending','completed')
        AND (task.status IS DISTINCT FROM p.effective_status OR task.completion_inspection_id IS DISTINCT FROM p.inspection_id)
        AND (p.effective_status='completed' OR NOT EXISTS(
          SELECT 1 FROM inspection_schedule_tasks other WHERE other.id<>task.id AND other.user_id=task.user_id
          AND other.mode=task.mode AND other.year=task.year AND other.period_number=task.period_number
          AND other.station_id=task.station_id AND other.column_key=task.column_key AND other.status='pending'))''',params(user_id,today()))


def task_count(cur, user_id):
    sync_tasks(cur, user_id)
    return inbox_summary(cur,user_id,today())['count']


def personal_agenda(cur, user_id, summary=None):
    # Self-only data, independent of schedule administration privileges.
    cur.execute('''SELECT u.real_name,a.available,a.reason,d.assignments FROM users u
      LEFT JOIN staff_availability a ON a.person_name=TRIM(u.real_name) AND a.day=%s
      LEFT JOIN staff_daily_teams d ON d.day=%s WHERE u.id=%s''', (today(), today(), user_id))
    row = cur.fetchone() or {}
    if row.get('available') is None and (row.get('real_name') or '').strip() in {name for name,_ in STAFF}:
        ensure_today_availability(cur,today())
        # Re-read after the conditional insert: a concurrent explicit busy setting always wins.
        cur.execute('SELECT available,reason FROM staff_availability WHERE person_name=%s AND day=%s',
                    (row['real_name'].strip(),today()))
        row.update(cur.fetchone() or dict(available=True,reason=''))
    assignment = next((p for p in row.get('assignments') or [] if p['id'] == user_id), None)
    field_team = None
    if assignment and assignment['mode'] == 'offline':
        members = [p for p in row['assignments'] if p['mode'] == 'offline' and p['leader_id'] == assignment['leader_id']]
        field_team = dict(name=assignment['group_name'],leader_id=assignment['leader_id'],
                          members=[dict(id=p['id'],display_name=p['display_name'],position=p['position']) for p in members])
    buckets=(summary or inbox_summary(cur,user_id,today()))['buckets']
    counts={mode:dict(count=buckets['today_'+mode]['pending']+buckets['history_'+mode]['pending'],
                      overdue=buckets['history_'+mode]['pending']) for mode in ('offline','online')}
    return dict(day=today().isoformat(), available=row.get('available'), reason=row.get('reason') or '',
                assignment=assignment, field_team=field_team, offline=counts.get('offline', dict(count=0, overdue=0)),
                online=counts.get('online', dict(count=0, overdue=0)))


def dispatch_tasks(cur, actor, chosen, station, column, ids, day, start, team, event_id, *, replace_team=False):
    if chosen['mode']=='annual':
        # Both annual columns are field-team day tasks, never monthly video carry-over.
        # Their distinct column keys use a stable year key so date moves cancel the old task too.
        chosen=dict(mode='offline',year=chosen['year'],quarter=1)
    key = (chosen['mode'], chosen['year'], chosen.get('quarter', chosen.get('month')), station['id'], column['key'])
    cur.execute(f'''UPDATE inspection_schedule_tasks task SET status='cancelled',cancelled_at=CURRENT_TIMESTAMP
      WHERE mode=%s AND year=%s AND period_number=%s AND station_id=%s AND column_key=%s AND status='completed'
      AND NOT EXISTS(SELECT 1 FROM inspections ins WHERE ins.id=task.completion_inspection_id
        AND ins.station_id=task.station_id AND ins.inspection_table_id=task.table_id
        AND ins.inspection_date>=task.period_start AND ins.inspection_date<{coverage_end_sql('task')})''', key)
    cur.execute('''UPDATE inspection_schedule_tasks SET status='cancelled',cancelled_at=CURRENT_TIMESTAMP
      WHERE mode=%s AND year=%s AND period_number=%s AND station_id=%s AND column_key=%s
      AND (status='pending' OR (%s AND status IN ('completed','expired'))) AND (scheduled_date IS DISTINCT FROM %s OR NOT(user_id=ANY(%s))
        OR team_ids<>%s::jsonb OR plan_team IS DISTINCT FROM %s::jsonb)''',
      (*key, replace_team, day, ids, json.dumps(ids), json.dumps(team,ensure_ascii=False)))
    if not ids:
        return
    for uid in ids:
        cur.execute('''INSERT INTO inspection_schedule_tasks(mode,year,period_number,station_id,column_key,
          station_name,table_id,table_name,user_id,team_ids,scheduled_date,period_start,created_by,plan_team,dispatch_event_id)
          SELECT %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s WHERE NOT EXISTS (
            SELECT 1 FROM inspection_schedule_tasks WHERE mode=%s AND year=%s AND period_number=%s
            AND station_id=%s AND column_key=%s AND user_id=%s AND status='pending')''',
          (*key, station['station_name'], column['table_id'], column['full_name'], uid, json.dumps(ids), day, start, actor['id'],
           json.dumps(team,ensure_ascii=False),event_id,*key,uid))


def register_schedule_tasks(app, *, connect):
    from schedule_video_exceptions import register_video_exceptions
    register_video_exceptions(app, connect=connect)
    @app.get('/api/my-schedule-tasks')
    def my_schedule_tasks():
        actor = getattr(g, 'current_user', None)
        if not actor:
            return jsonify(success=False, error='请先登录。'), 401
        conn = cur = None
        try:
            conn = connect(); cur = conn.cursor()
            bucket=request.args.get('bucket','all')
            if bucket not in ('all',*BUCKETS):
                return jsonify(success=False,error='请选择有效的待办分类。'),400
            try:
                page=int(request.args.get('page','1'));page_size=int(request.args.get('page_size','24'))
                if page<1 or not 1<=page_size<=50: raise ValueError()
            except ValueError:
                return jsonify(success=False,error='待办分页参数不合法。'),400
            cur.execute("SET LOCAL statement_timeout='10s'")
            sync_tasks(cur,actor['id'])
            result=inbox_page(cur,actor['id'],today(),bucket,page,page_size)
            agenda = personal_agenda(cur, actor['id'],result)
            conn.commit()
            response = jsonify(success=True,today=today().isoformat(),**result,bucket=bucket,agenda=agenda)
            response.headers['Cache-Control'] = 'private, no-store'
            return response
        except Exception:
            if conn: conn.rollback()
            logging.exception('Schedule inbox failed')
            return jsonify(success=False, error='巡检待办暂时无法读取，请稍后重试。'), 500
        finally:
            if cur: cur.close()
            if conn: conn.close()
