"""An assigned inspector may waive a whole monthly video station, never fabricate actuals."""
import json
import logging

from flask import g, jsonify, request

from inspection_schedule_catalog import COLUMNS
from schedule_common import ScheduleConflict, lock_schedule, today
from schedule_task_progress import PROGRESS_SQL, params


def video_exceptions(cur, chosen, station_ids):
    if chosen['mode'] != 'online' or not station_ids:
        return {}
    cur.execute('''SELECT id,station_id,reason,reported_by,reporter_name,
      to_char(created_at AT TIME ZONE 'Asia/Shanghai','YYYY-MM-DD HH24:MI:SS') AS reported_at
      FROM inspection_schedule_video_exceptions WHERE year=%s AND month=%s AND station_id=ANY(%s)''',
      (chosen['year'], chosen['month'], station_ids))
    return {r['station_id']: dict(r) for r in cur.fetchall()}


def report_exception(cur, actor, task_id, reason):
    if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 500:
        raise ValueError('请填写1至500字的视频巡检异常原因。')
    reason = reason.strip()
    lock_schedule(cur)
    cur.execute('SELECT * FROM inspection_schedule_tasks WHERE id=%s FOR UPDATE', (task_id,))
    task = cur.fetchone()
    if not task or task['user_id'] != actor['id']:
        raise PermissionError('只能报告分配给自己的视频巡检站点异常。')
    keys = {c[0] for c in COLUMNS['online']}
    if task['mode'] != 'online' or task['column_key'] not in keys:
        raise ValueError('仅月度视频巡检支持整站异常免检。')
    if task['status'] not in ('pending', 'completed') or not task['station_id'] or task['scheduled_date'] > today():
        raise ScheduleConflict('该任务已取消、改派或尚未到执行日期，请刷新待办。')
    chosen = dict(mode='online', year=task['year'], month=task['period_number'])
    existing = video_exceptions(cur, chosen, [task['station_id']]).get(task['station_id'])
    if existing:
        if existing['reported_by'] == actor['id'] and existing['reason'] == reason:
            return existing
        raise ScheduleConflict('本站本月已登记视频巡检异常，请刷新查看。')
    cur.execute(PROGRESS_SQL + 'SELECT id FROM progress WHERE id=%s AND group_pending=1',
                (*params(actor['id'], today()), task_id))
    if not cur.fetchone():
        raise ScheduleConflict('该站任务已全部完成或派工已变化，请刷新待办。')
    cur.execute('''SELECT column_key,inspector_ids,scheduled_date,revision FROM inspection_schedule_cells
      WHERE mode='online' AND year=%s AND period_number=%s AND station_id=%s FOR UPDATE''',
      (task['year'], task['period_number'], task['station_id']))
    cells = cur.fetchall()
    if {c['column_key'] for c in cells} != keys or any(
            c['inspector_ids'] != [actor['id']] or c['scheduled_date'] != task['scheduled_date'] for c in cells):
        raise ScheduleConflict('本站三张视频检查表的派工已变化，请刷新后再报告异常。')
    cur.execute(PROGRESS_SQL + '''SELECT id,column_key,table_id,table_name,record_count,inspection_id
      FROM progress WHERE mode='online' AND station_id=%s AND scheduled_date=%s
        AND year=%s AND period_number=%s ORDER BY id''',
      (*params(actor['id'], today()), task['station_id'], task['scheduled_date'], task['year'], task['period_number']))
    tasks = [dict(r) for r in cur.fetchall()]
    if len(tasks) != 3 or {t['column_key'] for t in tasks} != keys:
        raise ScheduleConflict('本站视频派工任务不完整，请联系排班人员核对。')
    cur.execute('''INSERT INTO inspection_schedule_video_exceptions
      (year,month,station_id,station_name,scheduled_date,reported_by,reporter_name,reason,source_task_id,task_ids,dispatch_snapshot)
      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
      (task['year'], task['period_number'], task['station_id'], task['station_name'], task['scheduled_date'],
       actor['id'], str(actor.get('real_name') or actor.get('username') or '未记录').strip(), reason, task_id,
       json.dumps([t['id'] for t in tasks]),
       json.dumps(dict(cells=[dict(c) for c in cells], tasks=tasks), ensure_ascii=False, default=str)))
    return video_exceptions(cur, chosen, [task['station_id']])[task['station_id']]


def register_video_exceptions(app, *, connect):
    @app.post('/api/my-schedule-tasks/<int:task_id>/video-exception')
    def my_video_exception(task_id):
        actor = getattr(g, 'current_user', None)
        if not actor:
            return jsonify(success=False, error='请先登录。'), 401
        conn = cur = None
        try:
            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                raise ValueError('请填写视频巡检异常原因。')
            conn = connect(); cur = conn.cursor()
            cur.execute("SET LOCAL statement_timeout='10s'")
            cur.execute("SET LOCAL lock_timeout='3s'")
            result = report_exception(cur, actor, task_id, data.get('reason'))
            conn.commit()
            response = jsonify(success=True, video_exception=result, message='已登记整站视频异常，三张检查表无需再完成。')
            response.headers['Cache-Control'] = 'private, no-store'
            return response
        except (ValueError, PermissionError) as exc:
            if conn: conn.rollback()
            return jsonify(success=False, error=str(exc)), 409 if isinstance(exc, ScheduleConflict) else 403 if isinstance(exc, PermissionError) else 400
        except Exception:
            if conn: conn.rollback()
            logging.exception('Video task exception failed')
            return jsonify(success=False, error='视频异常暂时无法保存，请稍后重试。'), 500
        finally:
            if cur: cur.close()
            if conn: conn.close()
