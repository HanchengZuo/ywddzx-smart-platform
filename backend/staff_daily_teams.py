"""Shared daily team snapshots and reproducible random student grouping."""
import json
import random
from collections import defaultdict
from datetime import timedelta
from schedule_common import ScheduleConflict
from driving_permits import require_field_driver, validate_driving_teams
from inspection_schedule_catalog import roster_position


def clean_assignments(assignments):
    return [{k: v for k, v in p.items() if k not in ('dispatch_locked', 'field_dispatched', 'lock_reason')}
            for p in assignments]


def join_unassigned(people, before, member_id, leader_id):
    person = next((p for p in people if p['id'] == member_id and p.get('available') is True), None)
    if not person or person.get('station_modes'):
        raise ValueError('只能加入今日有空、尚未编组且没有站点派工的人员。')
    mode = 'online' if leader_id is None else 'offline'
    if {m['mode'] for m in person.get('actual_modes', [])} - {mode}:
        raise ScheduleConflict('该人员已有另一种巡检实绩，不能调整到此组。')
    if person['position'] == '管理人员':
        if leader_id not in (None, member_id):
            raise ValueError('一个外勤组只能有一位管理人员；管理人员可移至内勤视频组或独立带队。')
        name = f"外勤{person['display_name']}组"
    else:
        leader = next((p for p in before if p['id'] == leader_id and p['position'] == '管理人员'
                       and p['mode'] == 'offline' and p['leader_id'] == p['id']), None)
        if leader_id is not None and not leader:
            raise ValueError('请选择已保存的外勤带队组或内勤视频组。')
        name = leader['group_name'] if leader else '内勤视频组'
    member = {key: person[key] for key in ('id', 'display_name', 'position')}
    member['has_driving_permit'] = person.get('has_driving_permit') is True
    return [dict(p) for p in before] + [dict(member, mode=mode, leader_id=leader_id,
                                           group_name=name if mode == 'offline' else '内勤视频组')]


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
    if 'online' in eligible.get('station_modes', []) and mode != 'online':
        raise ScheduleConflict('该学生已有视频站点派工，调整前请先撤销其视频安排。')
    if {m['mode'] for m in eligible.get('actual_modes', [])} - {mode}:
        raise ScheduleConflict('该学生已有另一种巡检实绩，不能改到此组。')
    person.update(mode=mode, leader_id=leader_id, group_name=leader['group_name'] if leader else '内勤视频组')
    return result


def without_member(before, member_id):
    """A departing field leader dissolves their group; students return to video."""
    departing = next((p for p in before if p['id'] == member_id), None)
    result = []
    for person in before:
        if person['id'] == member_id:
            continue
        person = dict(person)
        if (departing and departing['position'] == '管理人员' and departing['mode'] == 'offline'
                and person['mode'] == 'offline' and person['leader_id'] == member_id):
            person.update(mode='online', leader_id=None, group_name='内勤视频组')
        result.append(person)
    return result


def move_member(people, before, member_id, leader_id):
    """Apply a draft move using server-owned identities, including leader dissolution."""
    person = next((p for p in before if p['id'] == member_id), None)
    eligible = {p['id']: p for p in people if p.get('available') is True}
    if not person:
        return join_unassigned(people, before, member_id, leader_id)
    if member_id not in eligible:
        raise ValueError('只能调整今日有空且已参与方案的人员。')
    if person['position'] == '大学生':
        return move_student(people, before, member_id, leader_id)
    if leader_id not in (None, member_id):
        raise ValueError('一个外勤组只能有一位管理人员；管理人员可移至内勤视频组或独立带队。')
    result = without_member(before, member_id)
    mode = 'online' if leader_id is None else 'offline'
    # Restoring a leader does not dissolve an already unchanged group.
    if (person['mode'], person['leader_id']) == (mode, leader_id):
        return [dict(p) for p in before]
    result.append(dict(person, mode=mode, leader_id=leader_id,
                       group_name='内勤视频组' if leader_id is None else f"外勤{person['display_name']}组"))
    old = {p['id']: p for p in before}
    for changed in result:
        previous = old[changed['id']]
        if (previous['mode'], previous['leader_id']) != (changed['mode'], changed['leader_id']):
            source = eligible.get(changed['id'])
            if not source:
                raise ScheduleConflict('原组成员档期已变化，请重新载入方案。')
            if 'online' in source.get('station_modes', []):
                raise ScheduleConflict('相关人员已有今日站点派工，请先撤下全部今日排班。')
            if {m['mode'] for m in source.get('actual_modes', [])} - {changed['mode']}:
                raise ScheduleConflict('相关人员已有另一种巡检实绩，不能调整到此组。')
    return result


def adjust_members(people, assignments, moves):
    if not isinstance(moves, list) or len(moves) > 200:
        raise ValueError('方案调整数据不合法，请重新生成或载入。')
    for move in moves:
        if (not isinstance(move, dict) or set(move) != {'person_id', 'leader_id'}
                or type(move['person_id']) is not int or move['person_id'] < 1
                or (move['leader_id'] is not None and (type(move['leader_id']) is not int or move['leader_id'] < 1))):
            raise ValueError('方案中的人员或带队组不合法。')
        assignments = move_member(people, assignments, move['person_id'], move['leader_id'])
    return assignments


def propose_teams(people, before, manager_modes, seed):
    """Re-generate only undispatched people; dispatched teams remain intact."""
    managers = [p for p in people if p['position'] == '管理人员']
    if not isinstance(manager_modes, dict) or set(manager_modes) != {str(p['id']) for p in managers}:
        raise ValueError('请为每一位今日有空的管理人员选择现场或视频巡检。')
    frozen = [dict(p) for p in before if p.get('dispatch_locked') or p.get('field_dispatched')]
    for p in frozen:
        if p['position'] == '管理人员' and manager_modes.get(str(p['id'])) != p['mode']:
            raise ScheduleConflict(f"{p['display_name']}已有今日站点派工，不能更换分工。")
    ids = {p['id'] for p in frozen}
    free = [p for p in people if p['id'] not in ids]
    choices = {str(p['id']): manager_modes[str(p['id'])] for p in free if p['position'] == '管理人员'}
    return frozen + random_teams(free, choices, seed)


def validate_dispatched_teams(cur, day, assignments):
    groups = {g['leader_id']: {p['id'] for p in g['members']} for g in group_assignments(assignments) if g['mode']=='offline'}
    cur.execute("""SELECT DISTINCT plan_team FROM inspection_schedule_cells WHERE mode IN ('offline','annual')
      AND scheduled_date=%s AND inspector_ids<>'[]'::jsonb AND jsonb_typeof(plan_team)='object'""", (day,))
    for row in cur.fetchall():
        team = row['plan_team']
        if team['leader_id'] not in groups:
            raise ScheduleConflict('外勤带队组已有站点安排，请先撤下该组派工，再调整带队人员。')


def started_field_leaders(cur, day):
    """Only a planned member's post-dispatch record/issue locks field membership.

    Deliberately independent of the 17:00 staff-board actuals display window.
    A new issue can belong to a reused monthly record created before dispatch.
    """
    cur.execute('''SELECT DISTINCT (c.plan_team->>'leader_id')::int AS leader_id
      FROM inspection_schedule_cells c
      LEFT JOIN LATERAL (
        SELECT ev.created_at FROM inspection_schedule_events ev
        WHERE ev.mode=c.mode AND ev.year=c.year AND ev.period_number=c.period_number
          AND ev.station_id=c.station_id AND ev.column_key=c.column_key
          AND ev.after_date=c.scheduled_date AND ev.after_ids<>'[]'::jsonb
          AND ev.after_team->>'leader_id'=c.plan_team->>'leader_id'
          AND (ev.before_ids='[]'::jsonb OR ev.before_date IS DISTINCT FROM ev.after_date
            OR ev.before_team->>'leader_id' IS DISTINCT FROM ev.after_team->>'leader_id')
        ORDER BY ev.id DESC LIMIT 1
      ) dispatch ON TRUE
      JOIN inspection_schedule_tasks task
        ON task.mode='offline' AND task.year=c.year AND task.period_number=c.period_number
        AND task.station_id=c.station_id AND task.column_key=c.column_key
        AND task.scheduled_date=c.scheduled_date AND task.team_ids=c.inspector_ids
        AND task.status IN ('pending','completed','expired')
      WHERE c.mode IN ('offline','annual') AND c.scheduled_date=%s AND c.inspector_ids<>'[]'::jsonb
        AND jsonb_typeof(c.plan_team)='object'
        AND EXISTS(SELECT 1 FROM inspections ins WHERE ins.station_id=c.station_id AND ins.inspection_table_id=task.table_id
          AND ins.inspection_date>=make_date(c.year,CASE WHEN c.mode='annual' THEN 1 ELSE (c.period_number-1)*3+1 END,1)
          AND ins.inspection_date<make_date(c.year,CASE WHEN c.mode='annual' THEN 1 ELSE (c.period_number-1)*3+1 END,1)
            + CASE WHEN c.mode='annual' THEN INTERVAL '1 year' ELSE INTERVAL '3 months' END
          AND ((c.inspector_ids @> jsonb_build_array(ins.inspector_id) AND ins.created_at>=COALESCE(dispatch.created_at,c.updated_at))
            OR EXISTS(SELECT 1 FROM issues issue WHERE issue.inspection_id=ins.id
              AND c.inspector_ids @> jsonb_build_array(issue.inspector_id) AND issue.created_at>=COALESCE(dispatch.created_at,c.updated_at))))''',
                (day,))
    return {row['leader_id'] for row in cur.fetchall()}


def dispatched_members(cur, day):
    """Video assignees and field leaders stay bound to existing station intent."""
    cur.execute("""SELECT DISTINCT c.inspector_ids,c.plan_team,c.mode,s.region,s.station_name
      FROM inspection_schedule_cells c JOIN stations s ON s.id=c.station_id
      WHERE scheduled_date=%s AND inspector_ids<>'[]'::jsonb
        AND ((c.mode='online' AND s.include_online_plan) OR (c.mode IN ('offline','annual') AND s.include_offline_plan))""",(day,))
    ids,leaders=set(),set()
    for row in cur.fetchall():
        if not roster_position(row,row['mode']): continue
        if row['mode'] == 'online': ids.update(row['inspector_ids'])
        team=row['plan_team']
        if team:
            leaders.add(team['leader_id'])
    return ids,leaders


def annotate_dispatch_locks(cur,day,groups):
    ids,leaders=dispatched_members(cur,day)
    started = started_field_leaders(cur, day)
    for group in groups:
        field = group['mode'] == 'offline'
        assigned = field and group['leader_id'] in leaders
        locked = field and group['leader_id'] in started
        group['dispatch_locked']=locked
        group['has_dispatch']=assigned
        group['lock_reason']='派工后已有组员在分派站点登记对应巡检记录，组员已锁定。' if locked else ''
        for p in group['members']:
            leader_bound = assigned and p['id'] == group['leader_id']
            p['field_dispatched'] = assigned
            p['dispatch_locked']=bool(locked or p['id'] in ids or leader_bound)
            p['lock_reason'] = group['lock_reason'] if locked else (
                '已有视频站点派工，请先撤下该人员的视频排班。' if p['id'] in ids else
                '带队组已有站点派工，调整带队前请先撤下该组派工。' if leader_bound else '')
    return groups


def validate_team_changes(cur,day,before,after):
    """Field members lock on execution, while leaders/video retain dispatch ownership."""
    ids,leaders=dispatched_members(cur,day)
    started = started_field_leaders(cur, day)
    current={p['id']:p for p in before}
    proposed={p['id']:p for p in after}
    for group in group_assignments(before):
        if group['mode']=='offline' and group['leader_id'] in started:
            old={p['id'] for p in group['members']}
            new={p['id'] for p in after if p['mode']=='offline' and p['leader_id']==group['leader_id']}
            if old!=new:
                raise ScheduleConflict(f"{group['name']}派工后已有组员在分派站点登记巡检记录，不能调入或调出组员。")
    for leader in leaders:
        old, new = current.get(leader), proposed.get(leader)
        if old and (not new or new['mode'] != 'offline' or new['leader_id'] != leader):
            raise ScheduleConflict('外勤带队组已有站点安排，请先撤下该组派工，再调整带队人员。')
    for uid in ids:
        old=current.get(uid)
        new=proposed.get(uid)
        if old and (not new or (old['mode'],old['leader_id'])!=(new['mode'],new['leader_id'])):
            raise ScheduleConflict(f"{old['display_name']}已有今日站点派工，不能调整分组；请先撤下其全部今日排班。")


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
    assignments, before = clean_assignments(assignments), clean_assignments(before)
    cur.execute('''INSERT INTO staff_daily_teams(day,assignments,revision,updated_by) VALUES(%s,%s,1,%s)
      ON CONFLICT(day) DO UPDATE SET assignments=EXCLUDED.assignments,revision=staff_daily_teams.revision+1,
        updated_by=EXCLUDED.updated_by,updated_at=CURRENT_TIMESTAMP RETURNING revision''',
                (day, json.dumps(assignments, ensure_ascii=False), actor['id']))
    revision = cur.fetchone()['revision']
    cur.execute('''INSERT INTO staff_daily_team_events(day,before_value,after_value,actor_id,actor_name)
      VALUES(%s,%s,%s,%s,%s)''', (day, json.dumps(before, ensure_ascii=False), json.dumps(assignments, ensure_ascii=False),
        actor['id'], actor.get('real_name') or actor.get('username') or str(actor['id'])))
    return revision
