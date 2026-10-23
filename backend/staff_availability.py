"""Fixed staff roster, explicit availability and record-derived workday history."""
import json
import logging
from collections import defaultdict
from datetime import timedelta
from flask import g, jsonify, request
from roles import SUPERVISOR_ROLES
from staff_daily_teams import (team_days, team_members, without_member, validate_team_changes,
                              save_teams, group_assignments)
from schedule_shelf_store import seed_daily_shelf
from staff_schedule_history import dispatch_history, personal_records, cell_read_only_reason
from staff_actuals import actuals_window, assert_actuals_window, merge_actual_modes
from schedule_common import ScheduleConflict, day_value, lock_schedule, require_workday, today, working_days

STAFF = ([(name, '管理人员') for name in '步雪琼 孔德辰 赵之龙 吕泽昆 韩叙 杨昊淞 芦斌'.split()]
         + [(name, '大学生') for name in '陈中磊 程镇林 葛心玉 侯明敖 姜傲云 吕雪儿 彭思宇 束紫荆 王涛 王昕怡 王子玥 徐晃 徐佳仪 袁姝慧 赵萌 左翰承 魏九发 宋辞'.split()])
VIEW = 'view_staff_availability'
EDIT = 'edit_staff_availability'


def ensure_today_availability(cur, day=None):
    """Persist missing defaults without waiting behind dispatch or overwriting manual choices."""
    day = day or today()
    names = [name for name,_ in STAFF]
    cur.execute('SELECT COUNT(*) AS n FROM staff_availability WHERE day=%s AND person_name=ANY(%s)', (day,names))
    if cur.fetchone()['n'] == len(names): return
    cur.execute('SELECT pg_try_advisory_xact_lock(9801,1) AS locked')
    if not cur.fetchone()['locked']: return
    cur.execute('''WITH inserted AS (
      INSERT INTO staff_availability(person_name,day,available,reason,revision,is_default)
      SELECT name,%s,TRUE,'',1,TRUE FROM unnest(%s::text[]) AS name
      ON CONFLICT(person_name,day) DO NOTHING RETURNING person_name,day
    ) INSERT INTO staff_availability_events(person_name,day,before_value,after_value,actor_name)
      SELECT person_name,day,'{"available":null}'::jsonb,
        '{"available":true,"reason":"","is_default":true}'::jsonb,'系统默认有空' FROM inserted''',
                (day,names))


def effective_availability(saved, day):
    return saved.get('available', True if day == today() else None)


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
    cur.execute('''SELECT id,username,real_name,role,has_driving_permit,COALESCE(account_status,'active') AS account_status
      FROM users WHERE TRIM(real_name)=ANY(%s) ORDER BY id''', ([name for name, _ in STAFF],))
    matches = defaultdict(list)
    for row in cur.fetchall(): matches[row['real_name'].strip()].append(row)
    result = []
    for index, (name, position) in enumerate(STAFF):
        choices = [row for row in matches[name] if row['role'] in SUPERVISOR_ROLES and row['account_status'] == 'active']
        user = choices[0] if len(choices) == 1 else {}
        result.append(dict(id=user.get('id'), username=user.get('username', ''), role=user.get('role', ''),
            display_name=name, position=position, sequence=index + 1,
            has_driving_permit=user.get('has_driving_permit') is True,
            history_ids=[matches[name][0]['id']] if len(matches[name]) == 1 else [user['id']] if user else [],
            binding='matched' if len(choices) == 1 else 'missing' if not choices else 'ambiguous'))
    return result


def daily_modes(cur, ids, start, end, *, include_ids=False):
    if not ids or start>=end: return {}
    evidence = ',array_agg(DISTINCT ins.id) AS record_ids' if include_ids else ''
    cur.execute(f'''WITH participants AS (
      SELECT id AS inspection_id,inspector_id FROM inspections WHERE inspection_date >= %s AND inspection_date < %s
      UNION SELECT issue.inspection_id,issue.inspector_id FROM issues issue JOIN inspections ins ON ins.id=issue.inspection_id
        WHERE ins.inspection_date >= %s AND ins.inspection_date < %s
    ) SELECT p.inspector_id,ins.inspection_date::text AS day,t.checklist_mode AS mode,COUNT(DISTINCT ins.id) AS n{evidence}
      FROM participants p JOIN inspections ins ON ins.id=p.inspection_id
      JOIN inspection_tables t ON t.id=ins.inspection_table_id
      WHERE p.inspector_id=ANY(%s) AND t.checklist_mode IN ('offline','online')
      GROUP BY p.inspector_id,ins.inspection_date,t.checklist_mode''', (start, end, start, end, ids))
    result = defaultdict(list)
    for row in cur.fetchall():
        value = dict(mode=row['mode'],count=row['n'])
        if include_ids: value['record_ids'] = row['record_ids']
        result[(row['inspector_id'], row['day'])].append(value)
    return result


def available_people(cur, day, *, window=None):
    if day == today(): ensure_today_availability(cur)
    people = roster_people(cur)
    cur.execute('SELECT person_name,available,reason,revision,is_default FROM staff_availability WHERE day=%s', (day,))
    values = {row['person_name']: row for row in cur.fetchall()}
    planned = planned_work(cur, day, day + timedelta(days=1))
    teams = team_members(team_days(cur, day, day + timedelta(days=1)))
    window = window or actuals_window(today())
    actual = daily_modes(cur, [p['id'] for p in people if p['id']], day, min(day+timedelta(days=1),window.as_of+timedelta(days=1)))
    for p in people:
        value = values.get(p['display_name'], {})
        assigned = teams.get((p['id'], day.isoformat()))
        station_modes = planned.get((p['id'], day.isoformat()), [])
        p.update(available=effective_availability(value,day), reason=value.get('reason', ''), revision=value.get('revision', 0),
                 is_default=value.get('is_default',day == today()),
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
            planned[(uid, row['day'])].add('offline' if row['mode']=='annual' else row['mode'])
    return {key: sorted(modes) for key, modes in planned.items()}


def today_summary(cur, day, *, window=None, actual=None, history=None):
    """Today's person counts stay independent of the week being browsed."""
    window = window or actuals_window(today())
    people = available_people(cur,day,window=window)
    ids = [uid for p in people for uid in p['history_ids']]
    if actual is None:
        actual = daily_modes(cur,ids,day,min(day+timedelta(days=1),window.as_of+timedelta(days=1)),include_ids=True)
    if history is None:
        history = dispatch_history(cur,ids,day,day+timedelta(days=1),window.today,
                                   defer_day=window.today if window.as_of<window.today else None)
    counts = dict(free=0, busy=0, unknown=0, offline=0, online=0)
    for person in people:
        records = [row for uid in person['history_ids'] for row in actual.get((uid, day.isoformat()), [])]
        work = next((history[(uid,day.isoformat())]['summary'] for uid in person['history_ids'] if (uid,day.isoformat()) in history),{})
        records = merge_actual_modes(records,work)
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
    cur.execute('SELECT available,reason,revision,history_status,is_default FROM staff_availability WHERE person_name=%s AND day=%s FOR UPDATE', (name, day))
    previous = cur.fetchone() or dict(available=None, reason='', revision=0, history_status=None)
    if previous['revision'] != revision: raise ScheduleConflict('档期已被其他用户修改，请重新载入后调整。')
    window = actuals_window(today())
    cell = single_staff_cell(cur,people[name],day,previous,window=window)
    if cell['read_only_reason']:
        raise ScheduleConflict(cell['read_only_reason'])
    if not historical and not available and people[name]['id']:
        cur.execute('''SELECT 1 FROM inspection_schedule_cells WHERE scheduled_date=%s
          AND inspector_ids @> %s::jsonb LIMIT 1''', (day, json.dumps([people[name]['id']])))
        if cur.fetchone(): raise ScheduleConflict(f'{name}当天已有排班，请先改派或取消排班，再标记没空。')
        saved = team_days(cur, day, day + timedelta(days=1)).get(day.isoformat(), {})
        before = saved.get('assignments', [])
        if any(p['id'] == people[name]['id'] for p in before):
            after = without_member(before, people[name]['id'])
            validate_team_changes(cur, day, before, after)
            # A leader's departure also changes their students' mode. Keep the
            # existing released-actuals protection for everyone affected.
            current_people = {p['id']: p for p in available_people(cur, day, window=window) if p['id']}
            old = {p['id']: p for p in before}
            for p in after:
                if p['mode'] != old[p['id']]['mode']:
                    if p['id'] not in current_people:
                        raise ScheduleConflict('原组成员账号已变化，请先核对今日巡检安排。')
                    if current_people[p['id']]['actual_modes']:
                        raise ScheduleConflict('原外勤组成员已有巡检实绩，不能自动调整为视频巡检。')
            revision = save_teams(cur, actor, day, after, before)
            seed_daily_shelf(cur, actor, day, group_assignments(after), revision)
    if (previous['available'] == available and previous['reason'] == reason and previous['history_status'] == history_status
            and not previous.get('is_default')): return
    cur.execute('''INSERT INTO staff_availability(person_name,day,available,reason,revision,updated_by,history_status,is_default)
      VALUES(%s,%s,%s,%s,1,%s,%s,FALSE) ON CONFLICT(person_name,day) DO UPDATE SET available=EXCLUDED.available,
      reason=EXCLUDED.reason,history_status=EXCLUDED.history_status,is_default=FALSE,
      revision=staff_availability.revision+1,updated_by=EXCLUDED.updated_by,updated_at=CURRENT_TIMESTAMP''',
                (name, day, available, reason, actor['id'], history_status))
    cur.execute('''INSERT INTO staff_availability_events(person_name,day,before_value,after_value,actor_id,actor_name)
      VALUES(%s,%s,%s,%s,%s,%s)''', (name, day, json.dumps(dict(previous)), json.dumps(dict(available=available, reason=reason, history_status=history_status,is_default=False)),
      actor['id'], actor.get('real_name') or actor.get('username') or str(actor['id'])))
    assert_actuals_window(window,today())


def staff_cell(day, saved, assigned, direct_actual, history, *, window=None):
    window = window or actuals_window(today())
    work = history.get('summary', {})
    actual = merge_actual_modes(direct_actual if day<=window.as_of else [],work)
    groups = set(work.get('group_names', []))
    if assigned and assigned['mode'] == 'offline': groups.add(assigned['group_name'])
    value = dict(available=effective_availability(saved,day),is_default=saved.get('is_default',day == today()),reason=saved.get('reason',''),
        history_status=saved.get('history_status'),daily_assignment=assigned,
        revision=saved.get('revision',0),updated_by_name=saved.get('updated_by_name',''),updated_at=saved.get('saved_at',''),
        planned_modes=sorted(set(work.get('modes',[])) | ({assigned['mode']} if assigned else set())),
        field_group_names=sorted(groups),actual_modes=actual,
        dispatch={k:v for k,v in work.items() if k!='_actual_record_ids'},
        actuals_pending=day==window.today and window.as_of<window.today,
        has_actual=bool(actual))
    value['read_only_reason'] = cell_read_only_reason(value,day,today())
    value['read_only'] = bool(value['read_only_reason'])
    return value


def single_staff_cell(cur, person, day, saved=None, *, details=False, window=None):
    window = window or actuals_window(today())
    if saved is None:
        if day == today(): ensure_today_availability(cur)
        cur.execute('''SELECT a.*,CASE WHEN a.is_default THEN '系统默认' ELSE
          COALESCE(NULLIF(TRIM(u.real_name),''),u.username,'未记录') END AS updated_by_name,
          to_char(a.updated_at,'YYYY-MM-DD HH24:MI') AS saved_at
          FROM staff_availability a LEFT JOIN users u ON u.id=a.updated_by WHERE person_name=%s AND day=%s''', (person['display_name'],day))
        saved = cur.fetchone() or {}
    ids = person['history_ids']
    history = dispatch_history(cur,ids,day,day+timedelta(days=1),window.today,details=details,
                               defer_day=window.today if window.as_of<window.today else None)
    work = next(iter(history.values()),{})
    teams = team_members(team_days(cur,day,day+timedelta(days=1)))
    assigned = next((teams[(uid,day.isoformat())] for uid in ids if (uid,day.isoformat()) in teams),None)
    actual = daily_modes(cur,ids,day,min(day+timedelta(days=1),window.as_of+timedelta(days=1)),include_ids=True)
    cell = staff_cell(day,saved,assigned,[r for uid in ids for r in actual.get((uid,day.isoformat()),[])],work,window=window)
    return dict(cell,tasks=work.get('tasks',[])) if details else cell


def staff_board(cur, week):
    window = actuals_window(today())
    ensure_today_availability(cur)
    start = week - timedelta(days=week.weekday()); end = start + timedelta(days=7)
    days = working_days(cur, start, end)
    cur.execute('SELECT COUNT(*) AS n FROM quality_work_calendar WHERE day>=%s AND day<%s', (start, end))
    known = cur.fetchone()['n'] == 7
    people = roster_people(cur)
    cur.execute('''SELECT a.*,CASE WHEN a.is_default THEN '系统默认' ELSE
      COALESCE(NULLIF(TRIM(u.real_name),''),u.username,'未记录') END AS updated_by_name,
      to_char(a.updated_at,'YYYY-MM-DD HH24:MI') AS saved_at FROM staff_availability a LEFT JOIN users u ON u.id=a.updated_by
      WHERE day>=%s AND day<%s''', (start, end))
    saved = {(r['person_name'], r['day'].isoformat()): r for r in cur.fetchall()}
    history_ids = [uid for p in people for uid in p['history_ids']]
    history = dispatch_history(cur,history_ids,start,end,window.today,
                               defer_day=window.today if window.as_of<window.today else None)
    teams = team_days(cur, start, end)
    members = team_members(teams)
    actual = daily_modes(cur,history_ids,start,min(end,window.as_of+timedelta(days=1)),include_ids=True)
    for p in people:
        p['cells'] = {}
        for d in days:
            v = saved.get((p['display_name'], d['day']), {})
            assigned = next((members[(uid,d['day'])] for uid in p['history_ids'] if (uid,d['day']) in members),None)
            work = next((history[(uid,d['day'])] for uid in p['history_ids'] if (uid,d['day']) in history),{})
            p['cells'][d['day']] = staff_cell(day_value(d['day']),v,assigned,
                [mode for uid in p['history_ids'] for mode in actual.get((uid,d['day']),[])],work,window=window)
    return dict(week=start.isoformat(), today=today().isoformat(), days=days, calendar_known=known, people=people,
                today_summary=today_summary(cur,today(),window=window,
                    **(dict(actual=actual,history=history) if start<=window.today<end else {})),**window.metadata(),
                daily_teams=list(teams.values()))


def register_staff_availability(app, *, connect, has_permission):
    @app.get('/api/staff-availability/detail')
    def staff_availability_detail():
        actor = getattr(g,'current_user',None)
        if not actor: return jsonify(success=False,error='请先登录。'),401
        conn = cur = None
        try:
            conn = connect(); cur = conn.cursor()
            if not has_permission(cur,actor,VIEW): raise PermissionError('当前账号无权查看人员档期。')
            cur.execute("SET LOCAL statement_timeout='10s'")
            name = request.args.get('person_name')
            day = day_value(request.args.get('day'))
            person = next((p for p in roster_people(cur) if p['display_name']==name),None)
            if not person: raise ValueError('请选择人员档期名单中的人员。')
            window = actuals_window(today())
            cell = single_staff_cell(cur,person,day,details=True,window=window)
            records = personal_records(cur,person['history_ids'],day) if day<=window.as_of else []
            response = jsonify(success=True,person=person,day=day.isoformat(),today=today().isoformat(),
                can_edit=has_permission(cur,actor,EDIT),cell=cell,records=records,**window.metadata())
            conn.commit()
            response.headers['Cache-Control']='private, no-store'
            return response
        except (ValueError,PermissionError) as exc:
            return jsonify(success=False,error=str(exc)),403 if isinstance(exc,PermissionError) else 400
        except Exception:
            logging.exception('Staff dispatch detail failed')
            return jsonify(success=False,error='档期详情暂时无法读取，请稍后重试。'),500
        finally:
            if cur: cur.close()
            if conn: conn.close()

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
                conn.commit()
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
