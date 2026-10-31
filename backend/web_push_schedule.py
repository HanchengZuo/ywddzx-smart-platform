"""Coalesce committed personnel/station plans into one private reminder per person and version."""
from datetime import datetime
from zoneinfo import ZoneInfo
from psycopg2.extras import RealDictCursor
from web_push_outbox import enqueue_business


def current_day():
    return datetime.now(ZoneInfo('Asia/Shanghai')).date()


def snapshot(cur, user_id, day):
    cur.execute('SELECT value,md5(value::text) AS fingerprint FROM (SELECT push_schedule_snapshot(%s,%s) AS value) agenda',(user_id,day))
    return cur.fetchone()


def event_key(user_id, day, fingerprint):
    return f'daily_schedule:{user_id}:{day.isoformat()}:{fingerprint}'


def notice_body(agenda, day):
    assignment=agenda.get('assignment') or {}
    tasks=agenda.get('tasks') or []
    field={task['station_id'] for task in tasks if task['mode']=='offline'}
    video={task['station_id'] for task in tasks if task['mode']=='online'}
    lines=[f'{day.isoformat()} 的今日安排已更新。']
    if assignment:
        lines.append(assignment.get('group_name') or ('现场巡检' if assignment['mode']=='offline' else '视频巡检'))
        names=[person['name'] for person in assignment.get('members') or [] if person.get('name')]
        if names: lines.append('同行成员：'+'、'.join(names)+'。')
    if field or video:
        lines.append(f'现场巡检 {len(field)} 站，视频巡检 {len(video)} 站，共 {len(tasks)} 项检查表任务。')
    else:
        lines.append('人员分工已确认，具体站点任务待分配。')
    lines.append('请打开右上角“今日安排”查看最新分工、站点与任务完成情况。')
    return '\n'.join(lines)


def process_schedule_changes(connect, limit=100, *, day=None):
    day=day or current_day()
    conn=connect()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('SELECT pg_try_advisory_xact_lock(12332001) AS acquired')
            if not cur.fetchone()['acquired']:
                conn.commit();return 0
            cur.execute("SET LOCAL lock_timeout='3s'")
            cur.execute("SET LOCAL statement_timeout='15s'")
            cur.execute('''SELECT user_id,day,max(id) AS revision FROM web_push_schedule_changes
              WHERE day<=%s GROUP BY user_id,day ORDER BY day,min(id) LIMIT %s''',(day,limit))
            changes=cur.fetchall()
            for change in changes:
                uid=change['user_id']
                if change['day']==day:
                    agenda=snapshot(cur,uid,day)
                    cur.execute('SELECT fingerprint FROM web_push_schedule_state WHERE user_id=%s AND day=%s',(uid,day))
                    previous=cur.fetchone()
                    if agenda['value'] and (not previous or previous['fingerprint']!=agenda['fingerprint']):
                        enqueue_business(cur,event_key=event_key(uid,day,agenda['fingerprint']),source='daily_schedule',entity_id=uid,
                            title='今日巡检安排已更新',body=notice_body(agenda['value'],day),recipients=[uid],
                            action_path='/notifications',push_hint='你的今日巡检安排已更新，请登录查看右上角“今日安排”。')
                    cur.execute('''INSERT INTO web_push_schedule_state(user_id,day,fingerprint) VALUES(%s,%s,%s)
                      ON CONFLICT(user_id,day) DO UPDATE SET fingerprint=EXCLUDED.fingerprint''',(uid,day,agenda['fingerprint']))
                # New concurrent writes are appended, never overwritten/consumed by an old scan.
                cur.execute('DELETE FROM web_push_schedule_changes WHERE user_id=%s AND day=%s AND id<=%s',(uid,change['day'],change['revision']))
        conn.commit();return len(changes)
    except Exception:
        conn.rollback();raise
    finally:
        conn.close()


def delivery_allowed(cur, message, user_id):
    if message['entity_id']!=user_id:
        return False
    day=current_day()
    agenda=snapshot(cur,user_id,day)
    return bool(agenda['value'] and message['event_key']==event_key(user_id,day,agenda['fingerprint']))
