"""Shared daily team snapshots and reproducible random student grouping."""
import json
import random
from collections import defaultdict
from datetime import timedelta
from schedule_common import ScheduleConflict
from driving_permits import require_field_driver, validate_driving_teams


def team_days(cur, start, end):
    cur.execute('''SELECT d.day::text,d.assignments,d.revision,
      COALESCE(NULLIF(TRIM(u.real_name),''),u.username,'未记录') AS updated_by_name,
      to_char(d.updated_at,'YYYY-MM-DD HH24:MI') AS updated_at
      FROM staff_daily_teams d LEFT JOIN users u ON u.id=d.updated_by
      WHERE d.day >= %s AND d.day < %s ORDER BY d.day''', (start, end))
    return {r['day']: dict(r) for r in cur.fetchall()}


def team_members(days):
    return {(a['id'], day): a for day, record in days.items() for a in record['assignments']}


def group_assignments(assignments):
    groups = {}
    for assignment in assignments:
        key = assignment['group_name']
        if key not in groups:
            groups[key] = dict(name=key, mode=assignment['mode'], leader_id=assignment['leader_id'], members=[])
        groups[key]['members'].append(assignment)
    return list(groups.values())


def field_team(cur, day, ids):
    saved = team_days(cur, day, day + timedelta(days=1)).get(day.isoformat(), {})
    for group in group_assignments(saved.get('assignments', [])):
        if group['mode'] == 'offline' and group['leader_id'] and set(ids) == {p['id'] for p in group['members']}:
            drivers = require_field_driver(cur, ids)
            return dict(name=group['name'], leader_id=group['leader_id'], day=day.isoformat(),
                        revision=saved['revision'], members=[dict(p, has_driving_permit=p['id'] in drivers) for p in group['members']])
    raise ValueError('现场排班必须选择该日期已保存的完整外勤组，请先在人员档期安排分组。')


def move_student(people, before, student_id, leader_id):
    """Only students move; managers and the saved roster are never supplied by the client."""
    result = [dict(p) for p in before]
    person = next((p for p in result if p['id'] == student_id and p['position'] == '大学生'), None)
    eligible = next((p for p in people if p['id'] == student_id and p['available'] is True), None)
    if not person or not eligible:
        raise ValueError('只能移动今日有空且已分组的大学生。')
    leader = next((p for p in result if p['id'] == leader_id and p['position'] == '管理人员'
                   and p['mode'] == 'offline' and p['leader_id'] == p['id']), None)
    if leader_id is not None and (not leader or not any(p['id']==leader_id and p['available'] is True for p in people)):
        raise ValueError('请选择已保存的外勤带队组或内勤视频组。')
    if person['leader_id'] == leader_id and person['mode'] == ('offline' if leader else 'online'):
        return result
    mode = 'offline' if leader else 'online'
    if eligible.get('station_modes') and (mode != 'offline' or set(eligible['station_modes']) != {'offline'}):
        raise ScheduleConflict('该学生已有站点派工，跨现场/视频调组前请先撤销其原站点安排。')
    if {m['mode'] for m in eligible.get('actual_modes', [])} - {mode}:
        raise ScheduleConflict('该学生已有另一种巡检实绩，不能改到此组。')
    person.update(mode=mode, leader_id=leader_id, group_name=leader['group_name'] if leader else '内勤视频组')
    return result


def validate_dispatched_teams(cur, day, assignments):
    groups = {g['leader_id']: {p['id'] for p in g['members']} for g in group_assignments(assignments) if g['mode']=='offline'}
    cur.execute("""SELECT DISTINCT plan_team FROM inspection_schedule_cells WHERE mode IN ('offline','annual')
      AND scheduled_date=%s AND inspector_ids<>'[]'::jsonb AND jsonb_typeof(plan_team)='object'""", (day,))
    for row in cur.fetchall():
        team = row['plan_team']
        if groups.get(team['leader_id']) != {p['id'] for p in team['members']}:
            raise ScheduleConflict('外勤组已派站点，请先撤销相关站点安排，再调整成员或重新分组。')


def adjust_preview(people, assignments, student_leaders):
    """Apply only student/leader choices to a server-rebuilt, verified preview."""
    if not isinstance(student_leaders, dict) or len(student_leaders) > len(people):
        raise ValueError('预览调组数据不合法，请重新预览。')
    for key, leader in sorted(student_leaders.items()):
        if not isinstance(key, str) or not key.isascii() or not key.isdecimal() or str(int(key)) != key:
            raise ValueError('预览中的学生编号不合法。')
        if leader is not None and (type(leader) is not int or leader < 1):
            raise ValueError('请选择外勤带队组或内勤视频组。')
        assignments = move_student(people, assignments, int(key), leader)
    validate_driving_teams(people, assignments)
    return assignments


def random_teams(people, manager_modes, seed):
    """Keep manager choices; prioritize driver coverage, then balance student workloads."""
    managers = [p for p in people if p['position'] == '管理人员']
    students = [p for p in people if p['position'] == '大学生']
    if not isinstance(manager_modes, dict) or set(manager_modes) != {str(p['id']) for p in managers}:
        raise ValueError('请为每一位今日有空的管理人员选择现场或视频巡检。')
    rng = random.Random(seed)
    result, leaders = [], []
    for p in managers:
        mode = manager_modes[str(p['id'])]
        if mode not in ('offline', 'online'):
            raise ValueError('管理人员分工只能选择现场或视频巡检。')
        locked = set(p.get('station_modes', [])) | {m['mode'] for m in p.get('actual_modes', [])}
        if locked - {mode}:
            raise ValueError(f"{p['display_name']}已有另一种站点排班或巡检实绩，不能更换检查方式。")
        if mode == 'offline': leaders.append(p)
        result.append(dict(id=p['id'], display_name=p['display_name'], position=p['position'], mode=mode,
                           has_driving_permit=p.get('has_driving_permit') is True,
                           leader_id=p['id'] if mode == 'offline' else None,
                           group_name=f"外勤{p['display_name']}组" if mode == 'offline' else '内勤视频组'))
    rng.shuffle(students)
    fixed, flexible = defaultdict(list), []
    for p in students:
        modes = set(p.get('station_modes', [])) | {m['mode'] for m in p.get('actual_modes', [])}
        if len(modes) > 1:
            raise ValueError(f"{p['display_name']}当日已有混合巡检记录，请先核对，不能自动安排。")
        if modes: fixed[next(iter(modes))].append(p)
        else: flexible.append(p)
    if not leaders and fixed['offline']:
        raise ValueError('已有现场安排的大学生需要至少一位现场带队管理人员。')
    target = len(students) // 2 + (rng.randrange(2) if len(students) % 2 else 0)
    target = max(len(fixed['offline']), min(target, len(students) - len(fixed['online']))) if leaders else 0
    drivers = [p for p in flexible if p.get('has_driving_permit') is True]
    fixed_drivers = sum(p.get('has_driving_permit') is True for p in fixed['offline'])
    minimum = sum(p.get('has_driving_permit') is not True for p in leaders)
    if len(drivers) + fixed_drivers < minimum:
        raise ValueError(f'现场带队分工需要至少{minimum}名持准驾证的大学生，目前可安排现场的仅{len(drivers)+fixed_drivers}名。请维护准驾证资料或调整管理人员现场/视频分工。')
    # Driver coverage outranks an exact 50/50 split. Prefer two per team when possible.
    preferred = sum(2 - int(p.get('has_driving_permit') is True) for p in leaders)
    selected_drivers = drivers[:max(0, preferred - fixed_drivers)]
    target = max(target, len(fixed['offline']) + len(selected_drivers))
    remaining = [p for p in flexible if p not in selected_drivers]
    take = target - len(fixed['offline']) - len(selected_drivers)
    field_students = fixed['offline'] + selected_drivers + remaining[:take]
    video_students = fixed['online'] + remaining[take:]
    rng.shuffle(leaders)
    sizes = {p['id']: 0 for p in leaders}
    driver_counts = {p['id']: int(p.get('has_driving_permit') is True) for p in leaders}
    field_students.sort(key=lambda p: p.get('has_driving_permit') is not True)
    for p in field_students:
        licensed = p.get('has_driving_permit') is True
        leader = min(leaders, key=lambda lead: (min(driver_counts[lead['id']], 2) if licensed else 2,
                                               sizes[lead['id']]))
        sizes[leader['id']] += 1
        driver_counts[leader['id']] += int(licensed)
        result.append(dict(id=p['id'], display_name=p['display_name'], position=p['position'], mode='offline',
                           has_driving_permit=licensed,
                           leader_id=leader['id'], group_name=f"外勤{leader['display_name']}组"))
    for p in video_students:
        result.append(dict(id=p['id'], display_name=p['display_name'], position=p['position'], mode='online',
                           has_driving_permit=p.get('has_driving_permit') is True,
                           leader_id=None, group_name='内勤视频组'))
    validate_driving_teams(people, result)
    return result


def save_teams(cur, actor, day, assignments, before):
    cur.execute('''INSERT INTO staff_daily_teams(day,assignments,revision,updated_by) VALUES(%s,%s,1,%s)
      ON CONFLICT(day) DO UPDATE SET assignments=EXCLUDED.assignments,revision=staff_daily_teams.revision+1,
        updated_by=EXCLUDED.updated_by,updated_at=CURRENT_TIMESTAMP RETURNING revision''',
                (day, json.dumps(assignments, ensure_ascii=False), actor['id']))
    revision = cur.fetchone()['revision']
    cur.execute('''INSERT INTO staff_daily_team_events(day,before_value,after_value,actor_id,actor_name)
      VALUES(%s,%s,%s,%s,%s)''', (day, json.dumps(before, ensure_ascii=False), json.dumps(assignments, ensure_ascii=False),
        actor['id'], actor.get('real_name') or actor.get('username') or str(actor['id'])))
    return revision
