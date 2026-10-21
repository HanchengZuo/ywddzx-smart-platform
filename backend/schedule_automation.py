"""Deterministic, review-before-save balancing. No AI calls or daily background jobs."""
import hashlib
import json
import logging
from collections import defaultdict
from datetime import timedelta
from flask import g, jsonify, request
from inspection_schedule import EDIT_PERMISSION, VIEW_PERMISSION, read_board, save_cell
from schedule_common import ScheduleConflict, day_value, lock_schedule, require_workday, today
from scheduling_map import period
from staff_availability import available_people, excluded_reason
from staff_daily_teams import group_assignments, team_days
from schedule_routes import ORIGIN_ADDRESS, ORIGIN_POINT, coordinate, field_routes, cluster_diameter, regional_coverage, regional_targets


def workload(cur, ids, start, end):
    cur.execute('''WITH participants AS (
      SELECT id AS inspection_id,inspector_id FROM inspections WHERE inspection_date >= %s AND inspection_date < %s
      UNION SELECT i.inspection_id,i.inspector_id FROM issues i JOIN inspections ins ON ins.id=i.inspection_id
        WHERE ins.inspection_date >= %s AND ins.inspection_date < %s
    ), units AS (
      SELECT p.inspector_id AS uid,t.checklist_mode AS mode,ins.inspection_date AS day,ins.station_id
      FROM participants p JOIN inspections ins ON ins.id=p.inspection_id
      JOIN inspection_tables t ON t.id=ins.inspection_table_id
      WHERE p.inspector_id=ANY(%s) AND t.checklist_mode IN ('offline','online') AND ins.inspection_date<=%s
      UNION
      SELECT task.user_id,task.mode,task.scheduled_date,task.station_id FROM inspection_schedule_tasks task
      WHERE task.user_id=ANY(%s) AND task.status='pending' AND task.station_id IS NOT NULL AND task.table_id IS NOT NULL
        AND task.scheduled_date >= %s AND task.scheduled_date < %s
        AND (task.mode='online' OR task.scheduled_date>=%s)
      AND NOT EXISTS(SELECT 1 FROM inspections ins WHERE ins.station_id=task.station_id
        AND ins.inspection_table_id=task.table_id
        AND ins.inspection_date>=task.period_start AND ins.inspection_date<=%s)
    ) SELECT uid,mode,COUNT(*) AS n FROM units GROUP BY uid,mode''', (start, end, start, end, ids, today(), ids, start, end, today(), today()))
    result = {uid: dict(offline=0, online=0) for uid in ids}
    for r in cur.fetchall(): result[r['uid']][r['mode']] = r['n']
    return result


def balanced_allocation(people, demands, loads):
    """One person/day/station bundle; prefer their underrepresented quarterly mode."""
    queues = {mode: list(demands.get(mode, [])) for mode in ('offline', 'online')}
    total = {mode: sum(loads.get(p['id'], {}).get(mode, 0) for p in people) for mode in queues}
    result = []
    for p in sorted(people, key=lambda p: (sum(loads.get(p['id'], {}).values()), p['sequence'])):
        before = dict(loads.get(p['id'], dict(offline=0, online=0)))
        choices = [mode for mode, groups in queues.items() if groups]
        if not choices: break
        def score(mode):
            diff = before['offline'] - before['online'] + (1 if mode == 'offline' else -1)
            return (abs(diff), total[mode], 0 if mode == 'offline' else 1)
        mode = min(choices, key=score)
        group = queues[mode].pop(0)
        after = dict(before); after[mode] += 1; total[mode] += 1
        result.append(dict(**group, mode=mode, person=p, before=before, after=after))
    return result


def proposal(cur, actor, day, options=None):
    require_workday(cur, day)
    if day != today(): raise ValueError('一键排班只安排今天，请刷新日期。')
    options = options or {}
    quotas = {mode: options.get(key, default) for mode, key, default in
              [('offline', 'offline_count', 2), ('online', 'online_count', 3)]}
    if any(type(v) is not int or not 1 <= v <= 10 for v in quotas.values()):
        raise ValueError('每组或每人的站点数量请设置为1至10。')
    origin = ORIGIN_POINT
    people = available_people(cur, day)
    eligible = [p for p in people if p['id'] and p['available'] is True and not p['station_modes'] and not p['actual_modes']]
    demands, periods, board_tokens = {}, {}, {}
    coverage = []
    quarter = (day.month - 1) // 3 + 1
    for mode in ('offline', 'online'):
        chosen, start, end = period(dict(mode=mode, year=day.year, **({'quarter': quarter} if mode == 'offline' else {'month': day.month})))
        periods[mode] = (chosen, start, end)
        board = read_board(cur, chosen, start, end)
        board_tokens[mode] = board['board_token']
        if mode == 'offline': coverage = regional_coverage(board['rows'],day)
        demands[mode] = []
        for row in board['rows']:
            cells = [dict(station_id=row['station_id'], column_key=c['key'], revision=row['cells'][c['key']]['revision'], label=c['label'])
                     for c in board['columns'] if row['cells'][c['key']]['status'] == 'unassigned']
            if cells and not any(c['status']=='assigned' for c in row['cells'].values()):
                demands[mode].append(dict(station_id=row['station_id'], station_name=row['station_name'],
                  region=row['region'], address=row['address'], longitude=row['longitude'], latitude=row['latitude'], cells=cells,
                  covered=any(c['status']=='completed' for c in row['cells'].values())))
    _, start, end = periods['offline']
    loads = workload(cur, [p['id'] for p in eligible], start, end)
    groups = []
    eligible_by_id = {p['id']: p for p in eligible}
    # Keep a saved leader/student team together when converting personnel plans to station tasks.
    saved_team = team_days(cur, day, day + timedelta(days=1)).get(day.isoformat(), {})
    field_teams = []
    for team in group_assignments(saved_team.get('assignments', [])):
        ids = [p['id'] for p in team['members']]
        if team['mode'] == 'offline' and all(uid in eligible_by_id for uid in ids): field_teams.append(team)
    field_teams.sort(key=lambda t: (loads[t['leader_id']]['offline'], t['leader_id']))
    warnings = []
    missing = [s['station_name'] for s in demands['offline'] if not coordinate(s)]
    if missing: warnings.append('以下站点缺少有效坐标，未自动派现场任务：'+'、'.join(missing))
    if not field_teams: warnings.append('请先在人员档期保存今日外勤组，现场排班只按完整外勤组安排。')
    valid = [s for s in demands['offline'] if coordinate(s)]
    _,coverage = regional_targets(valid,len(field_teams)*quotas['offline'],coverage)
    routes = field_routes(valid, len(field_teams), quotas['offline'],coverage=coverage)
    for team, route in zip(field_teams, routes):
        representative = eligible_by_id[team['leader_id']]
        before = dict(loads[representative['id']])
        for index, station in enumerate(route):
            after = dict(before); after['offline'] += 1
            groups.append(dict(**station, mode='offline', person=representative, before=before, after=after,
                inspector_ids=[p['id'] for p in team['members']], group_name=team['name'], team_members=team['members'],
                route_order=index+1, cluster_max_km=round(cluster_diameter(route),1)))
            before = after
    video_people = [p for p in eligible if not p['daily_assignment'] or p['daily_assignment']['mode']=='online']
    video_people.sort(key=lambda p: (loads[p['id']]['online'], p['sequence']))
    # Round robin shares scarce remaining stations before giving anyone a second station.
    for _ in range(quotas['online']):
        for p in video_people:
            if not demands['online']: break
            station = demands['online'].pop(0)
            before = dict(loads[p['id']]); after = dict(before); after['online'] += 1
            groups.append(dict(**station, mode='online', person=p, before=before, after=after,
                               inspector_ids=[p['id']], group_name=p['display_name']))
            loads[p['id']] = after
    evidence = dict(actor=actor['id'], day=day.isoformat(), groups=groups, quotas=quotas, coverage=coverage,
                    board_tokens=board_tokens, algorithm='coverage-compact-v1',
                    team_revision=saved_team.get('revision', 0))
    token = hashlib.sha256(json.dumps(evidence, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return dict(day=day.isoformat(), quarter=f'{day.year}年第{quarter}季度', groups=groups, token=token,
        offline_count=quotas['offline'], online_count=quotas['online'], origin=origin, origin_address=ORIGIN_ADDRESS,
        warnings=warnings, regional_coverage=coverage,
        route_method='先均衡片区季度站点覆盖率（含今日及未来计划预留），再缩小同组站点之间的直线距离；不以出发点、行车顺路或往返路线选站。',
        available_count=len(eligible), cell_count=sum(len(g['cells']) for g in groups),
        excluded=[dict(name=p['display_name'], reason=excluded_reason(p) or '当天已有站点安排或巡检实绩')
                  for p in people if p not in eligible]), periods


def register_schedule_automation(app, *, connect, has_permission):
    @app.post('/api/inspection-schedule/auto')
    def auto_schedule():
        actor = getattr(g, 'current_user', None)
        if not actor: return jsonify(success=False, error='请先登录。'), 401
        conn = cur = None
        try:
            conn = connect(); cur = conn.cursor()
            if not has_permission(cur, actor, VIEW_PERMISSION) or not has_permission(cur, actor, EDIT_PERMISSION):
                raise PermissionError('当前账号不能自动排班。')
            data = request.get_json(silent=True)
            if not isinstance(data, dict) or data.get('action') not in ('preview', 'confirm'):
                raise ValueError('请选择预览或确认排班。')
            day = day_value(data.get('day', today().isoformat()))
            cur.execute("SET LOCAL lock_timeout='3s'; SET LOCAL statement_timeout='10s'")
            if data['action'] == 'confirm': lock_schedule(cur)
            result, periods = proposal(cur, actor, day, data)
            if data['action'] == 'confirm':
                if result['token'] != data.get('token'): raise ScheduleConflict('档期、实绩或排班已变化，请重新预览后确认。')
                if not result['groups']: raise ValueError('当前没有可派工人员或待排班单元格。')
                cache = {}
                for group in result['groups']:
                    chosen, start, end = periods[group['mode']]
                    for cell in group['cells']:
                        save_cell(cur, actor, dict(station_id=cell['station_id'], column_key=cell['column_key'], revision=cell['revision'],
                          inspector_ids=group.get('inspector_ids', [group['person']['id']]), scheduled_date=day.isoformat()), chosen, start, end, cache)
            conn.commit()
            response = jsonify(success=True, **result)
            response.headers['Cache-Control'] = 'private, no-store'
            return response
        except (ValueError, PermissionError) as exc:
            if conn: conn.rollback()
            return jsonify(success=False, error=str(exc)), 409 if isinstance(exc, ScheduleConflict) else 403 if isinstance(exc, PermissionError) else 400
        except Exception:
            if conn: conn.rollback()
            logging.exception('Automatic scheduling failed')
            return jsonify(success=False, error='自动排班暂时无法处理，请稍后重试。'), 500
        finally:
            if cur: cur.close()
            if conn: conn.close()
