"""Shared daily team snapshots and reproducible random student grouping."""
import json
import random
from collections import defaultdict


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


def random_teams(people, manager_modes, seed):
    """Managers are explicit; student split and team sizes differ by at most one when feasible."""
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
    field_students = fixed['offline'] + flexible[:target - len(fixed['offline'])]
    video_students = fixed['online'] + flexible[target - len(fixed['offline']):]
    rng.shuffle(leaders)
    for index, p in enumerate(field_students):
        leader = leaders[index % len(leaders)]
        result.append(dict(id=p['id'], display_name=p['display_name'], position=p['position'], mode='offline',
                           leader_id=leader['id'], group_name=f"外勤{leader['display_name']}组"))
    for p in video_students:
        result.append(dict(id=p['id'], display_name=p['display_name'], position=p['position'], mode='online',
                           leader_id=None, group_name='内勤视频组'))
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
