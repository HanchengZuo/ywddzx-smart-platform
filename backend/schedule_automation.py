"""Deterministic, review-before-save balancing. No AI calls or daily background jobs."""
import hashlib
import json
import logging
from collections import Counter, defaultdict
from datetime import timedelta
from flask import g, jsonify, request
from inspection_schedule import EDIT_PERMISSION, VIEW_PERMISSION, read_board, save_cell
from schedule_common import ScheduleConflict, day_value, lock_schedule, require_workday, today
from schedule_period import period
from annual_metering_plan import plan_state
from schedule_row_state import today_assignments
from schedule_smart import planning_board, replacement_summary, protected_daily_counts, apply_smart_plan
from schedule_quotas import read_quotas, save_quotas
from staff_availability import available_people, excluded_reason
from staff_actuals import actuals_window, assert_actuals_window
from staff_daily_teams import group_assignments, team_days
from schedule_routes import ORIGIN_ADDRESS, ORIGIN_POINT, coordinate, regional_coverage, regional_targets
from schedule_driving_routes import DrivingPlanNeeded, driving_request, resolve_driving_plan
from driving_errors import DrivingUnavailable


def workload(cur, ids, start, end, *, include_plans=True):
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
      WHERE %s AND task.user_id=ANY(%s) AND task.status='pending' AND task.station_id IS NOT NULL AND task.table_id IS NOT NULL
        AND task.scheduled_date >= %s AND task.scheduled_date < %s
        AND (task.mode='online' OR task.scheduled_date>=%s)
      AND NOT EXISTS(SELECT 1 FROM inspections ins WHERE ins.station_id=task.station_id
        AND ins.inspection_table_id=task.table_id
        AND ins.inspection_date>=task.period_start AND ins.inspection_date<=%s)
    ) SELECT uid,mode,COUNT(*) AS n FROM units GROUP BY uid,mode''', (start, end, start, end, ids, today(), include_plans, ids, start, end, today(), today()))
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


def proposal(cur, actor, day, options=None, *, driving_plan=None):
    require_workday(cur, day)
    if day != today(): raise ValueError('一键排班只安排今天，请刷新日期。')
    options = options or {}
    if options.get('strategy') not in (None,'replace_today'):
        raise ValueError('请选择有效的排班策略。')
    smart=options.get('strategy')=='replace_today'
    quota_settings=read_quotas(cur)
    if smart and 'quota_revision' in options and (type(options['quota_revision']) is not int or options['quota_revision']!=quota_settings['revision']):
        raise ScheduleConflict('站数配置已被其他用户修改，请重新打开智能排班后调整。')
    quotas = {mode: options.get(key, default) for mode, key, default in
              [('offline', 'offline_count', quota_settings['offline_count'] if smart else 2),
               ('online', 'online_count', quota_settings['online_count'] if smart else 3)]}
    if any(type(v) is not int or not 1 <= v <= 10 for v in quotas.values()):
        raise ValueError('每组或每人的站点数量请设置为1至10。')
    origin = ORIGIN_POINT
    people = available_people(cur, day)
    eligible = [p for p in people if p['id'] and p['available'] is True and not p['station_modes'] and not p['actual_modes']]
    if smart:
        eligible=[p for p in people if p['id'] and p['available'] is True and p['daily_assignment']
                  and not ({m['mode'] for m in p['actual_modes']}-{p['daily_assignment']['mode']})]
    demands, periods, board_tokens, boards = {}, {}, {}, {}
    coverage = []
    quarter = (day.month - 1) // 3 + 1
    for mode in ('offline', 'online'):
        chosen, start, end = period(dict(mode=mode, year=day.year, **({'quarter': quarter} if mode == 'offline' else {'month': day.month})))
        periods[mode] = (chosen, start, end)
        board = read_board(cur, chosen, start, end)
        boards[mode]=board
        board_tokens[mode] = board['board_token']
        if smart: board=planning_board(board,day)
        if mode == 'offline': coverage = regional_coverage(board['rows'],day)
        demands[mode] = []
        for row in board['rows']:
            if row.get('locked'): continue
            cells = [dict(station_id=row['station_id'], column_key=c['key'], revision=row['cells'][c['key']]['revision'], label=c['label'])
                     for c in board['columns'] if row['cells'][c['key']]['status'] == 'unassigned']
            if cells and not any(c['status']=='assigned' for c in row['cells'].values()):
                demands[mode].append(dict(station_id=row['station_id'], station_name=row['station_name'],
                  region=row['region'], address=row['address'], longitude=row['longitude'], latitude=row['latitude'], cells=cells,
                  covered=any(c['status']=='completed' for c in row['cells'].values())))
    _, start, end = periods['offline']
    loads = workload(cur, [p['id'] for p in eligible], start, end,include_plans=not smart)
    groups = []
    eligible_by_id = {p['id']: p for p in eligible}
    # Keep a saved leader/student team together when converting personnel plans to station tasks.
    saved_team = team_days(cur, day, day + timedelta(days=1)).get(day.isoformat(), {})
    field_teams = []
    unlicensed_teams = []
    for team in group_assignments(saved_team.get('assignments', [])):
        ids = [p['id'] for p in team['members']]
        if (team['mode'] == 'offline' and all(uid in eligible_by_id for uid in ids)
                and any(eligible_by_id[uid].get('has_driving_permit') is True for uid in ids)):
            field_teams.append(team)
        elif team['mode'] == 'offline' and all(uid in eligible_by_id for uid in ids):
            unlicensed_teams.append(team['name'])
    field_teams.sort(key=lambda t: (loads[t['leader_id']]['offline'], t['leader_id']))
    warnings = []
    if unlicensed_teams:
        warnings.append('以下外勤组当前无人拥有准驾证，未派现场任务，请先调整：'+'、'.join(unlicensed_teams))
    missing = [s['station_name'] for s in demands['offline'] if not coordinate(s)]
    if missing: warnings.append('以下站点缺少有效坐标，未自动派现场任务：'+'、'.join(missing))
    if not field_teams: warnings.append('请先在人员档期保存今日外勤组，现场排班只按完整且至少1人拥有准驾证的外勤组安排。')
    valid = [s for s in demands['offline'] if coordinate(s)]
    metering = plan_state(cur,day.year,day.month,ignore_plan_day=day if smart else None)
    annual_period = period(dict(mode='annual',year=day.year))
    periods['annual']=annual_period
    annual_board=read_board(cur,*annual_period)
    boards['annual']=annual_board
    board_tokens['annual']=annual_board['board_token']
    if smart: annual_board=planning_board(annual_board,day)
    ordinary=planning_board(boards['offline'],day) if smart else read_board(cur,*periods['offline'])
    quarter_rows={r['station_id']:r for r in ordinary['rows']}
    by_id={s['station_id']:s for s in valid}
    priority=[]
    for row in annual_board['rows']:
        site=row['cells']['metering_site']
        qrow=quarter_rows.get(row['station_id'])
        if not qrow or row.get('locked') or qrow.get('locked') or site['status'] not in ('assigned','unassigned') or any(c['status']=='assigned' and (c.get('scheduled_date') or '')>=day.isoformat() for c in row['cells'].values()): continue
        if any(c['status']=='assigned' for c in qrow['cells'].values()) or not coordinate(row): continue
        annual_cells=[dict(station_id=row['station_id'],column_key=c['key'],revision=row['cells'][c['key']]['revision'],label='计量'+c['label'])
                      for c in annual_board['columns'] if row['cells'][c['key']]['status'] in ('assigned','unassigned')]
        if not annual_cells: continue
        candidate=by_id.get(row['station_id']) or dict(station_id=row['station_id'],station_name=row['station_name'],region=row['region'],
            address=row['address'],longitude=row['longitude'],latitude=row['latitude'],cells=[dict(station_id=row['station_id'],column_key=c['key'],revision=qrow['cells'][c['key']]['revision'],label=c['label'])
              for c in ordinary['columns'] if qrow['cells'][c['key']]['status']=='unassigned'],covered=any(c['status']=='completed' for c in qrow['cells'].values()))
        priority.append(dict(candidate,metering_cells=annual_cells,metering_priority=True))
    limits={r['region']:r['remaining'] for r in metering['regions']}
    required=[]
    used=defaultdict(int)
    protected=protected_daily_counts(boards.values(),day) if smart else {}
    field_teams=[t for t in field_teams if protected.get(('offline',tuple(sorted(p['id'] for p in t['members']))),0)<quotas['offline']]
    capacities=[quotas['offline']-protected.get(('offline',tuple(sorted(p['id'] for p in t['members']))),0) for t in field_teams]
    capacity=sum(capacities)
    while len(required)<capacity:
        choices=[s for s in priority if s['station_id'] not in {r['station_id'] for r in required} and used[s['region']]<limits.get(s['region'],0)]
        if not choices: break
        station=min(choices,key=lambda s:(used[s['region']]/max(1,limits[s['region']]),s['station_id']))
        required.append(station);used[station['region']]+=1
    required_ids={s['station_id'] for s in required}
    valid=[s for s in valid if s['station_id'] not in required_ids]+required
    _,coverage = regional_targets(valid,capacity,coverage)
    driving = resolve_driving_plan(driving_request(valid, len(field_teams), quotas['offline'], coverage,
                                                 required_ids, capacities), driving_plan)
    by_id = {s['station_id']: s for s in valid}
    routes = [[by_id[sid] for sid in trip['station_ids']] for trip in driving['trips']]
    selected=Counter(s['region'] for route in routes for s in route)
    newly_covered=Counter(s['region'] for route in routes for s in route if not s['covered'])
    for r in coverage:
        r['selected']=selected[r['region']]
        r['newly_covered']=newly_covered[r['region']]
        r['projected_rate']=round(100*(r['checked']+r['reserved']+r['newly_covered'])/max(1,r['total']),1)
    for r in metering['regions']:
        r['proposed']=used[r['region']]
        if r['remaining']>r['proposed']:
            warnings.append(f"计量月度计划：{r['region']}尚缺{r['remaining']}站，本次安排{r['proposed']}站；受可派工人数、坐标或已排班站点限制，剩余任务仍保留。")
    for team, route, trip in zip(field_teams, routes, driving['trips']):
        representative = eligible_by_id[team['leader_id']]
        before = dict(loads[representative['id']])
        for index, station in enumerate(route):
            after = dict(before); after['offline'] += 1
            groups.append(dict(**station, mode='offline', person=representative, before=before, after=after,
                inspector_ids=[p['id'] for p in team['members']], group_name=team['name'], team_members=team['members'],
                route_order=index+1, driving_seconds=trip['seconds'], driving_meters=trip['meters'],
                driving_legs=trip['legs']))
            before = after
    video_people = [p for p in eligible if not p['daily_assignment'] or p['daily_assignment']['mode']=='online']
    if smart: video_people=[p for p in video_people if p['daily_assignment'] and p['daily_assignment']['mode']=='online']
    video_people.sort(key=lambda p: (loads[p['id']]['online'], p['sequence']))
    # Round robin shares scarce remaining stations before giving anyone a second station.
    for index in range(quotas['online']):
        for p in video_people:
            if index>=quotas['online']-protected.get(('online',(p['id'],)),0): continue
            if not demands['online']: break
            station = demands['online'].pop(0)
            before = dict(loads[p['id']]); after = dict(before); after['online'] += 1
            groups.append(dict(**station, mode='online', person=p, before=before, after=after,
                               inspector_ids=[p['id']], group_name=p['display_name']))
            loads[p['id']] = after
    evidence = dict(actor=actor['id'], day=day.isoformat(), groups=groups, quotas=quotas, coverage=coverage,
                    board_tokens=board_tokens, metering=metering, algorithm='metering-coverage-driving-v3',
                    team_revision=saved_team.get('revision', 0),strategy=options.get('strategy'),quota_revision=quota_settings['revision'])
    token = hashlib.sha256(json.dumps(evidence, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return dict(day=day.isoformat(), quarter=f'{day.year}年第{quarter}季度', groups=groups, token=token,
        offline_count=quotas['offline'], online_count=quotas['online'], quota_settings=quota_settings, origin=origin, origin_address=ORIGIN_ADDRESS,
        warnings=warnings, regional_coverage=coverage, metering_plan=metering,
        current_assignments=today_assignments(boards.values(),day),
        strategy=options.get('strategy'),replacement=replacement_summary(boards.values(),day),
        personnel=dict(groups=group_assignments(saved_team.get('assignments',[])),
                       revision=saved_team.get('revision',0),updated_by_name=saved_team.get('updated_by_name',''),updated_at=saved_team.get('updated_at','')),
        driving=dict(provider='amap', applicable=any(trip['legs'] for trip in driving['trips']),
                     calculated_at=driving['calculated_at'], cache_reused=driving['cache_reused'],
                     api_requests=0, source='database', dataset_id=driving.get('dataset_id')),
        route_method='先补齐当月计量年度计划配额，再均衡片区季度覆盖率，最后优先组合预计驾车时间短的站点；同耗时时参考行驶距离，不使用直线距离。只读取每周更新的路网数据库，每对站点采一个方向、往返共用估算。仅统计组内站间行车，不包含办公室出发、返程或现场检查耗时，实际出行请以导航为准。',
        available_count=len(eligible), cell_count=sum(len(g['cells'])+len(g.get('metering_cells',[])) for g in groups),
        excluded=[dict(name=p['display_name'], reason=excluded_reason(p) or ('尚未保存今日巡检分组或分工与实绩冲突' if smart else '当天已有站点安排或巡检实绩'))
                  for p in people if p not in eligible]), periods


def register_schedule_automation(app, *, connect, has_permission, driving_service=None):
    @app.get('/api/inspection-schedule/quotas')
    def schedule_station_quotas():
        actor=getattr(g,'current_user',None)
        if not actor: return jsonify(success=False,error='请先登录。'),401
        conn=cur=None
        try:
            conn=connect();cur=conn.cursor()
            if not has_permission(cur,actor,VIEW_PERMISSION): raise PermissionError('当前账号无权查看巡检排班。')
            result=read_quotas(cur)
            conn.commit()
            response=jsonify(success=True,**result)
            response.headers['Cache-Control']='private, no-store'
            return response
        except PermissionError as exc:
            if conn: conn.rollback()
            return jsonify(success=False,error=str(exc)),403
        except Exception:
            if conn: conn.rollback()
            logging.exception('Schedule station quotas failed')
            return jsonify(success=False,error='站数配置暂时无法读取，请稍后重试。'),500
        finally:
            if cur: cur.close()
            if conn: conn.close()

    @app.get('/api/inspection-schedule/today')
    def saved_daily_dispatch():
        actor=getattr(g,'current_user',None)
        if not actor: return jsonify(success=False,error='请先登录。'),401
        conn=cur=None
        try:
            conn=connect();cur=conn.cursor()
            if not has_permission(cur,actor,VIEW_PERMISSION):
                raise PermissionError('当前账号无权查看巡检排班。')
            cur.execute("SET LOCAL statement_timeout='10s'")
            day=today()
            boards=[read_board(cur,*period(dict(mode=mode,year=day.year,**extra))) for mode,extra in (
                ('offline',dict(quarter=(day.month-1)//3+1)),('annual',{}),('online',dict(month=day.month)))]
            result=today_assignments(boards,day)
            conn.commit()
            response=jsonify(success=True,day=day.isoformat(),groups=result)
            response.headers['Cache-Control']='private, no-store'
            return response
        except PermissionError as exc:
            if conn: conn.rollback()
            return jsonify(success=False,error=str(exc)),403
        except Exception:
            if conn: conn.rollback()
            logging.exception('Saved daily dispatch failed')
            return jsonify(success=False,error='今日已确认排班暂时无法读取，请稍后重试。'),500
        finally:
            if cur: cur.close()
            if conn: conn.close()

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
            if 'save_quotas' in data and type(data['save_quotas']) is not bool:
                raise ValueError('站数配置保存选项不合法。')
            if data.get('save_quotas') and (data['action'] != 'preview' or data.get('strategy') != 'replace_today'):
                raise ValueError('请在计算智能方案时保存站数配置。')
            if driving_service is None:
                raise DrivingUnavailable('驾车排班服务尚未初始化，请联系管理员。')
            if data['action'] == 'preview':
                # Gather authorized inputs without saving quotas or taking the
                # global dispatch lock. Planning reads only the road database.
                try:
                    proposal(cur, actor, day, data)
                except DrivingPlanNeeded as needed:
                    route_request = needed.request
                conn.rollback()
                cur.close(); cur = None
                conn.close(); conn = None
                driving_plan = driving_service.prepare(route_request)
                conn = connect(); cur = conn.cursor()
                if not has_permission(cur, actor, VIEW_PERMISSION) or not has_permission(cur, actor, EDIT_PERMISSION):
                    raise PermissionError('当前账号不能自动排班。')
                cur.execute("SET LOCAL lock_timeout='3s'; SET LOCAL statement_timeout='10s'")
            else:
                # Confirmation is pinned to the preview, including its dataset.
                driving_plan = driving_service.recall(data.get('token'), actor['id'], day)
            if data['action'] == 'confirm' or data.get('save_quotas'): lock_schedule(cur)
            if data.get('save_quotas'):
                if data['action']!='preview' or data.get('strategy')!='replace_today':
                    raise ValueError('请在计算智能方案时保存站数配置。')
                current=save_quotas(cur,actor,data)
                data=dict(data,quota_revision=current['revision'])
            window = actuals_window(today())
            result, periods = proposal(cur, actor, day, data, driving_plan=driving_plan)
            if data['action'] == 'confirm':
                if result['token'] != data.get('token'): raise ScheduleConflict('档期、实绩或排班已变化，请重新预览后确认。')
                if not result['groups']: raise ValueError('当前没有可派工人员或待排班单元格。')
                if result['strategy']=='replace_today':
                    if data.get('replace_confirmed') is not True:
                        raise ValueError('请先确认替换今日未开始的排班，已开始及其他日期计划将保留。')
                    result['replaced_cell_count']=apply_smart_plan(cur,actor,result,periods,day)
                cache = {}
                for group in ([] if result['strategy']=='replace_today' else result['groups']):
                    if group.get('metering_cells'):
                        annual,annual_start,annual_end=periods['annual']
                        # Annual-first atomically fills the corresponding quarterly row.
                        for cell in group['metering_cells']:
                            save_cell(cur,actor,dict(**cell,inspector_ids=group['inspector_ids'],scheduled_date=day.isoformat()),annual,annual_start,annual_end,cache)
                        continue
                    chosen, start, end = periods[group['mode']]
                    for cell in group['cells']:
                        save_cell(cur, actor, dict(station_id=cell['station_id'], column_key=cell['column_key'], revision=cell['revision'],
                          inspector_ids=group.get('inspector_ids', [group['person']['id']]), scheduled_date=day.isoformat()), chosen, start, end, cache)
                assert_actuals_window(window,today())
                result['current_assignments']=today_assignments([read_board(cur,*p) for p in periods.values()],day)
            if data['action'] == 'preview':
                driving_service.remember(result['token'], actor['id'], day, driving_plan)
            conn.commit()
            response = jsonify(success=True, **result)
            response.headers['Cache-Control'] = 'private, no-store'
            return response
        except DrivingUnavailable as exc:
            if conn: conn.rollback()
            return jsonify(success=False, error=str(exc)), 503
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
