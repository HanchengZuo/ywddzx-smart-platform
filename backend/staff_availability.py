"""Fixed staff roster, explicit availability and record-derived workday history."""
import json
import logging
from collections import defaultdict
from datetime import timedelta
from flask import g, jsonify, request
from roles import SUPERVISOR_ROLES
from staff_daily_teams import team_days, team_members
from schedule_common import ScheduleConflict, day_value, lock_schedule, require_workday, today, working_days

STAFF = ([(name, '管理人员') for name in '步雪琼 孔德辰 赵之龙 吕泽昆 韩叙 杨昊淞 芦斌'.split()]
         + [(name, '大学生') for name in '陈中磊 程镇林 葛心玉 侯明敖 姜傲云 吕雪儿 彭思宇 束紫荆 王涛 王昕怡 王子玥 徐晃 徐佳仪 袁姝慧 赵萌 左翰承 魏九发 宋辞'.split()])
VIEW = 'view_staff_availability'
EDIT = 'edit_staff_availability'


def excluded_reason(person):
    """Shared availability wording for personnel grouping and station dispatch."""
    reasons = []
    if person['available'] is False:
        reasons.append('没空' + (f"（{person['reason']}）" if person['reason'] else ''))
    elif person['available'] is None:
        reasons.append('未确认有空或没空')
    if not person['id']: reasons.append('账号未唯一匹配')
    return '；'.join(reasons)


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
    teams = team_members(team_days(cur, day, day + timedelta(days=1)))
    actual = daily_modes(cur, [p['id'] for p in people if p['id']], day, day + timedelta(days=1))
    for p in people:
        value = values.get(p['display_name'], {})
        assigned = teams.get((p['id'], day.isoformat()))
        station_modes = planned.get((p['id'], day.isoformat()), [])
        p.update(available=value.get('available'), reason=value.get('reason', ''), revision=value.get('revision', 0),
                 station_modes=station_modes, daily_assignment=assigned,
                 planned_modes=sorted(set(station_modes) | ({assigned['mode']} if assigned else set())),
                 actual_modes=actual.get((p['id'], day.isoformat()), []))
    return people


def planned_work(cur, start, end):
    cur.execute('''SELECT scheduled_date::text AS day,mode,inspector_ids FROM inspection_schedule_cells
      WHERE scheduled_date >= %s AND scheduled_date < %s AND inspector_ids<>'[]'::jsonb''', (start, end))
    planned = defaultdict(set)
    for row in cur.fetchall():
        for uid in row['inspector_ids']:
            planned[(uid, row['day'])].add(row['mode'])
    return {key: sorted(modes) for key, modes in planned.items()}


def today_summary(cur, day):
    """Today's person counts stay independent of the week being browsed."""
    people = available_people(cur, day)
    actual = daily_modes(cur, [uid for p in people for uid in p['history_ids']], day, day + timedelta(days=1))
    counts = dict(free=0, busy=0, unknown=0, offline=0, online=0)
    for person in people:
        records = [row for uid in person['history_ids'] for row in actual.get((uid, day.isoformat()), [])]
        modes = {row['mode'] for row in records} if records else set(person['planned_modes'])
        if modes:
            for mode in modes: counts[mode] += 1
        else:
            key = 'free' if person['available'] is True else 'busy' if person['available'] is False else 'unknown'
            counts[key] += 1
    return counts


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
    edits_day = day_value(edits[0].get('day')) if isinstance(edits[0], dict) else None
    historical = edits_day is not None and edits_day < today()
    history_status = data.get('history_status')
    if historical:
        if history_status not in ('offline', 'online', 'busy', 'auto'):
            raise ValueError('历史日期请选择现场巡检、视频巡检、没空或恢复自动记录。')
        available = history_status != 'busy'
        history_status = None if history_status == 'auto' else history_status
    else:
        if history_status is not None: raise ValueError('今天及未来日期只能设置有空或没空。')
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
    require_workday(cur, day, allow_past=historical)
    cur.execute('SELECT available,reason,revision,history_status FROM staff_availability WHERE person_name=%s AND day=%s FOR UPDATE', (name, day))
    previous = cur.fetchone() or dict(available=None, reason='', revision=0, history_status=None)
    if previous['revision'] != revision: raise ScheduleConflict('档期已被其他用户修改，请重新载入后调整。')
    if not historical and not available and people[name]['id']:
        cur.execute('''SELECT 1 FROM inspection_schedule_cells WHERE scheduled_date=%s
          AND inspector_ids @> %s::jsonb LIMIT 1''', (day, json.dumps([people[name]['id']])))
        if cur.fetchone(): raise ScheduleConflict(f'{name}当天已有排班，请先改派或取消排班，再标记没空。')
        assigned = team_members(team_days(cur, day, day + timedelta(days=1))).get((people[name]['id'], day.isoformat()))
        if assigned: raise ScheduleConflict('此人已加入今日巡检分组，不能直接标记没空；请调整分组安排后再保存。')
    if previous['available'] == available and previous['reason'] == reason and previous['history_status'] == history_status: return
    cur.execute('''INSERT INTO staff_availability(person_name,day,available,reason,revision,updated_by,history_status)
      VALUES(%s,%s,%s,%s,1,%s,%s) ON CONFLICT(person_name,day) DO UPDATE SET available=EXCLUDED.available,
      reason=EXCLUDED.reason,history_status=EXCLUDED.history_status,revision=staff_availability.revision+1,updated_by=EXCLUDED.updated_by,updated_at=CURRENT_TIMESTAMP''',
                (name, day, available, reason, actor['id'], history_status))
    cur.execute('''INSERT INTO staff_availability_events(person_name,day,before_value,after_value,actor_id,actor_name)
      VALUES(%s,%s,%s,%s,%s,%s)''', (name, day, json.dumps(dict(previous)), json.dumps(dict(available=available, reason=reason, history_status=history_status)),
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
    field_groups = defaultdict(set)
    cur.execute('''SELECT scheduled_date::text AS day,inspector_ids,plan_team->>'name' AS name
      FROM inspection_schedule_cells WHERE mode='offline' AND scheduled_date>=%s AND scheduled_date<%s
      AND jsonb_typeof(plan_team)='object' ''', (start, end))
    for plan in cur.fetchall():
        if plan['name']:
            for uid in plan['inspector_ids']:
                field_groups[(uid, plan['day'])].add(plan['name'])
    teams = team_days(cur, start, end)
    members = team_members(teams)
    actual = daily_modes(cur, [uid for p in people for uid in p['history_ids']], start, min(end, today() + timedelta(days=1)))
    for p in people:
        p['cells'] = {}
        for d in days:
            v = saved.get((p['display_name'], d['day']), {})
            assigned = members.get((p['id'], d['day']))
            modes = set(planned.get((p['id'], d['day']), [])) | ({assigned['mode']} if assigned else set())
            group_names = set(field_groups.get((p['id'], d['day']), []))
            if assigned and assigned['mode'] == 'offline': group_names.add(assigned['group_name'])
            p['cells'][d['day']] = dict(available=v.get('available'), reason=v.get('reason', ''),
                history_status=v.get('history_status'), daily_assignment=assigned,
                revision=v.get('revision', 0), updated_by_name=v.get('updated_by_name', ''), updated_at=v.get('saved_at', ''),
                planned_modes=sorted(modes),
                field_group_names=sorted(group_names),
                actual_modes=[mode for uid in p['history_ids'] for mode in actual.get((uid, d['day']), [])])
    return dict(week=start.isoformat(), today=today().isoformat(), days=days, calendar_known=known, people=people,
                today_summary=today_summary(cur, today()),
                daily_teams=list(teams.values()))


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
            response = jsonify(success=True, can_edit=can_edit, current_user_id=actor['id'], **result)
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
