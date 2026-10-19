"""Fixed staff roster, explicit availability and record-derived workday history."""
import json
import logging
from collections import defaultdict
from datetime import timedelta
from flask import g, jsonify, request
from roles import SUPERVISOR_ROLES
from schedule_common import ScheduleConflict, day_value, lock_schedule, require_workday, today, working_days

STAFF = [(name, '管理人员' if index < 6 or index in (22, 23) else '大学生') for index, name in enumerate(
    '步雪琼 孔德辰 赵之龙 吕泽昆 韩叙 杨昊淞 陈中磊 程镇林 葛心玉 侯明敖 姜傲云 吕雪儿 彭思宇 束紫荆 王涛 王昕怡 王子玥 徐晃 徐佳仪 袁姝慧 赵萌 左翰承 芦斌 孙慧佳 魏九发 宋辞'.split())]
VIEW = 'view_staff_availability'
EDIT = 'edit_staff_availability'


def roster_people(cur):
    cur.execute('''SELECT id,username,real_name,role,COALESCE(account_status,'active') AS account_status
      FROM users WHERE TRIM(real_name)=ANY(%s) ORDER BY id''', ([name for name, _ in STAFF],))
    matches = defaultdict(list)
    for row in cur.fetchall(): matches[row['real_name'].strip()].append(row)
    result = []
    for index, (name, position) in enumerate(STAFF):
        choices = [row for row in matches[name] if row['role'] in SUPERVISOR_ROLES and row['account_status'] == 'active']
        user = choices[0] if len(choices) == 1 else {}
        result.append(dict(id=user.get('id'), username=user.get('username', ''), role=user.get('role', ''),
            display_name=name, position=position, sequence=index + 1,
            history_ids=[matches[name][0]['id']] if len(matches[name]) == 1 else [user['id']] if user else [],
            binding='matched' if len(choices) == 1 else 'missing' if not choices else 'ambiguous'))
    return result


def daily_modes(cur, ids, start, end):
    if not ids: return {}
    cur.execute('''WITH participants AS (
      SELECT id AS inspection_id,inspector_id FROM inspections WHERE inspection_date >= %s AND inspection_date < %s
      UNION SELECT issue.inspection_id,issue.inspector_id FROM issues issue JOIN inspections ins ON ins.id=issue.inspection_id
        WHERE ins.inspection_date >= %s AND ins.inspection_date < %s
    ) SELECT p.inspector_id,ins.inspection_date::text AS day,t.checklist_mode AS mode,COUNT(DISTINCT ins.id) AS n
      FROM participants p JOIN inspections ins ON ins.id=p.inspection_id
      JOIN inspection_tables t ON t.id=ins.inspection_table_id
      WHERE p.inspector_id=ANY(%s) AND t.checklist_mode IN ('offline','online')
      GROUP BY p.inspector_id,ins.inspection_date,t.checklist_mode''', (start, end, start, end, ids))
    result = defaultdict(list)
    for row in cur.fetchall(): result[(row['inspector_id'], row['day'])].append(dict(mode=row['mode'], count=row['n']))
    return result


def available_people(cur, day):
    people = roster_people(cur)
    cur.execute('SELECT person_name,available,reason,revision FROM staff_availability WHERE day=%s', (day,))
    values = {row['person_name']: row for row in cur.fetchall()}
    planned = planned_work(cur, day, day + timedelta(days=1))
    actual = daily_modes(cur, [p['id'] for p in people if p['id']], day, day + timedelta(days=1))
    for p in people:
        value = values.get(p['display_name'], {})
        p.update(available=value.get('available'), reason=value.get('reason', ''), revision=value.get('revision', 0),
                 planned_modes=planned.get((p['id'], day.isoformat()), []), actual_modes=actual.get((p['id'], day.isoformat()), []))
    return people


def planned_work(cur, start, end):
    cur.execute('''SELECT scheduled_date::text AS day,mode,inspector_ids FROM inspection_schedule_cells
      WHERE scheduled_date >= %s AND scheduled_date < %s AND inspector_ids<>'[]'::jsonb''', (start, end))
    planned = defaultdict(set)
    for row in cur.fetchall():
        for uid in row['inspector_ids']:
            planned[(uid, row['day'])].add(row['mode'])
    return {key: sorted(modes) for key, modes in planned.items()}


def validate_people(cur, ids, day, mode, people=None):
    people = people if people is not None else {p['id']: p for p in available_people(cur, day) if p['id']}
    for uid in ids:
        p = people.get(uid)
        if not p:
            raise ValueError('只能选择人员档期名单中已唯一匹配启用督导组账号的人员。')
        if p['available'] is not True:
            raise ScheduleConflict(f"{p['display_name']}在{day}未确认有空或已标记没空，请先调整人员档期。")
        if (set(p['planned_modes']) | {row['mode'] for row in p['actual_modes']}) - {mode}:
            raise ScheduleConflict(f"{p['display_name']}当天已安排或执行另一种检查，不能同时安排现场和视频。")


def save_availability(cur, actor, data):
    edits = data.get('cells')
    if not isinstance(edits, list) or len(edits) != 1:
        raise ValueError('请逐个设置人员档期，每次只能保存一个单元格。')
    available = data.get('available')
    reason = data.get('reason', '')
    if type(available) is not bool or not isinstance(reason, str) or len(reason.strip()) > 4:
        raise ValueError('请选择有空或没空；原因最多4个字。')
    reason = '' if available else reason.strip()
    lock_schedule(cur)
    people = {p['display_name']: p for p in roster_people(cur)}
    edit = edits[0]
    if not isinstance(edit, dict): raise ValueError('档期单元格不合法。')
    name, revision = edit.get('person_name'), edit.get('revision')
    day = day_value(edit.get('day'))
    if not isinstance(name, str) or name not in people or type(revision) is not int or revision < 0:
        raise ValueError('人员或版本不合法。')
    require_workday(cur, day)
    cur.execute('SELECT available,reason,revision FROM staff_availability WHERE person_name=%s AND day=%s FOR UPDATE', (name, day))
    previous = cur.fetchone() or dict(available=None, reason='', revision=0)
    if previous['revision'] != revision: raise ScheduleConflict('档期已被其他用户修改，请重新载入后调整。')
    if not available and people[name]['id']:
        cur.execute('''SELECT 1 FROM inspection_schedule_cells WHERE scheduled_date=%s
          AND inspector_ids @> %s::jsonb LIMIT 1''', (day, json.dumps([people[name]['id']])))
        if cur.fetchone(): raise ScheduleConflict(f'{name}当天已有排班，请先改派或取消排班，再标记没空。')
    if previous['available'] == available and previous['reason'] == reason: return
    cur.execute('''INSERT INTO staff_availability(person_name,day,available,reason,revision,updated_by)
      VALUES(%s,%s,%s,%s,1,%s) ON CONFLICT(person_name,day) DO UPDATE SET available=EXCLUDED.available,
      reason=EXCLUDED.reason,revision=staff_availability.revision+1,updated_by=EXCLUDED.updated_by,updated_at=CURRENT_TIMESTAMP''',
                (name, day, available, reason, actor['id']))
    cur.execute('''INSERT INTO staff_availability_events(person_name,day,before_value,after_value,actor_id,actor_name)
      VALUES(%s,%s,%s,%s,%s,%s)''', (name, day, json.dumps(dict(previous)), json.dumps(dict(available=available, reason=reason)),
      actor['id'], actor.get('real_name') or actor.get('username') or str(actor['id'])))


def staff_board(cur, week):
    start = week - timedelta(days=week.weekday()); end = start + timedelta(days=7)
    days = working_days(cur, start, end)
    cur.execute('SELECT COUNT(*) AS n FROM quality_work_calendar WHERE day>=%s AND day<%s', (start, end))
    known = cur.fetchone()['n'] == 7
    people = roster_people(cur)
    cur.execute('''SELECT a.*,COALESCE(NULLIF(TRIM(u.real_name),''),u.username,'未记录') AS updated_by_name,
      to_char(a.updated_at,'YYYY-MM-DD HH24:MI') AS saved_at FROM staff_availability a LEFT JOIN users u ON u.id=a.updated_by
      WHERE day>=%s AND day<%s''', (start, end))
    saved = {(r['person_name'], r['day'].isoformat()): r for r in cur.fetchall()}
    planned = planned_work(cur, start, end)
    actual = daily_modes(cur, [uid for p in people for uid in p['history_ids']], start, min(end, today() + timedelta(days=1)))
    for p in people:
        p['cells'] = {}
        for d in days:
            v = saved.get((p['display_name'], d['day']), {})
            p['cells'][d['day']] = dict(available=v.get('available'), reason=v.get('reason', ''),
                revision=v.get('revision', 0), updated_by_name=v.get('updated_by_name', ''), updated_at=v.get('saved_at', ''),
                planned_modes=planned.get((p['id'], d['day']), []),
                actual_modes=[mode for uid in p['history_ids'] for mode in actual.get((uid, d['day']), [])])
    return dict(week=start.isoformat(), today=today().isoformat(), days=days, calendar_known=known, people=people)


def register_staff_availability(app, *, connect, has_permission):
    @app.route('/api/staff-availability', methods=['GET', 'PUT'])
    def staff_availability_board():
        actor = getattr(g, 'current_user', None)
        if not actor: return jsonify(success=False, error='请先登录。'), 401
        conn = cur = None
        try:
            conn = connect(); cur = conn.cursor()
            if not has_permission(cur, actor, VIEW): raise PermissionError('当前账号无权查看人员档期。')
            can_edit = has_permission(cur, actor, EDIT)
            cur.execute("SET LOCAL lock_timeout='3s'; SET LOCAL statement_timeout='10s'")
            if request.method == 'PUT':
                if not can_edit: raise PermissionError('当前账号不能编辑人员档期。')
                data = request.get_json(silent=True)
                if not isinstance(data, dict): raise ValueError('请提交有效的档期数据。')
                save_availability(cur, actor, data); conn.commit()
                result = dict(message='人员档期已保存。')
            else:
                result = staff_board(cur, day_value(request.args.get('week', today().isoformat())))
            response = jsonify(success=True, can_edit=can_edit, **result)
            response.headers['Cache-Control'] = 'private, no-store'
            return response
        except (ValueError, PermissionError) as exc:
            if conn: conn.rollback()
            return jsonify(success=False, error=str(exc)), 409 if isinstance(exc, ScheduleConflict) else 403 if isinstance(exc, PermissionError) else 400
        except Exception:
            if conn: conn.rollback()
            logging.exception('Staff availability failed')
            return jsonify(success=False, error='人员档期暂时无法处理，请稍后重试。'), 500
        finally:
            if cur: cur.close()
            if conn: conn.close()
