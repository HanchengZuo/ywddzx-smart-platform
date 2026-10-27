"""Two-stage daily personnel allocation; does not invent station/checklist tasks."""
import hashlib
import json
import logging
import re
import secrets
from datetime import timedelta
from flask import g, jsonify, request
from schedule_common import ScheduleConflict, day_value, lock_schedule, require_workday, today
from staff_availability import STAFF, VIEW, EDIT, available_people, excluded_reason, ensure_today_availability
from staff_actuals import actuals_window, assert_actuals_window
from inspection_schedule import sync_field_team_plans
from staff_daily_teams import (adjust_preview, adjust_members, clean_assignments, group_assignments, move_student, propose_teams, save_teams,
                              team_days, validate_dispatched_teams, validate_team_changes, annotate_dispatch_locks)
from driving_permits import validate_driving_teams
from schedule_dates import planning_days, eligible_dates
from schedule_shelf_store import seed_daily_shelf


def stored_assignments(result):
    return clean_assignments([p for group in result['groups'] for p in group['members']])


def proposal_token(actor, result, assignments, seed=None):
    evidence = dict(actor=actor['id'], context=result, assignments=assignments, seed=seed)
    return hashlib.sha256(json.dumps(evidence, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def context(cur, day):
    people = available_people(cur, day)
    saved = team_days(cur, day, day + timedelta(days=1)).get(day.isoformat(), {})
    cur.execute('SELECT working FROM quality_work_calendar WHERE day=%s', (day,))
    calendar = cur.fetchone()
    eligible = [p for p in people if p['id'] and p['available'] is True]
    permits = {p['id']: p.get('has_driving_permit') is True for p in people if p['id']}
    assignments = [dict(p, has_driving_permit=permits.get(p['id'], False)) for p in saved.get('assignments', [])]
    assigned_ids = {p['id'] for p in assignments}
    unconfirmed = [p['display_name'] for p in people if p['available'] is None]
    return dict(day=day.isoformat(), working=bool(calendar and calendar['working']), people=eligible,
                unassigned_people=[p for p in eligible if p['id'] not in assigned_ids and not p['station_modes']],
                unconfirmed=unconfirmed, confirmed_count=len(people)-len(unconfirmed), total_count=len(people),
                revision=saved.get('revision', 0), groups=annotate_dispatch_locks(cur,day,group_assignments(assignments)),
                updated_by_name=saved.get('updated_by_name', ''), updated_at=saved.get('updated_at', ''),
                excluded=[dict(name=p['display_name'], reason=excluded_reason(p))
                          for p in people if p not in eligible])


def process_day(cur, actor, data, can_edit):
    if day_value(data.get('day')) < today():
        raise ScheduleConflict('排班日期已过去，请重新选择今天或未来日期。')
    day = planning_days([data.get('day')], earliest=today())[0]
    window = actuals_window(today())
    if not can_edit: raise PermissionError('当前账号不能安排所选日期巡检。')
    if not isinstance(data, dict) or data.get('action') not in ('preview', 'confirm', 'move', 'apply'):
        raise ValueError('请选择预览、确认或调整该日分组。')
    if data['action'] != 'preview':
        lock_schedule(cur)
        # Short, bounded write transaction: do not let a record be
        # inserted between execution validation and member/task sync.
        cur.execute('LOCK TABLE inspections, issues IN SHARE MODE')
        cur.execute('SELECT id FROM users WHERE TRIM(real_name)=ANY(%s) ORDER BY id FOR SHARE', ([name for name, _ in STAFF],))
        cur.fetchall()
    result = context(cur, day)
    if day > today() and result['unconfirmed']:
        raise ScheduleConflict('该日期人员档期尚未全部确认，请先完成全部有空/没空设置。')
    if type(data.get('revision')) is not int or data['revision'] != result['revision']:
        raise ScheduleConflict('该日分组已被修改，请重新载入后安排。')
    if data['action'] == 'move':
        require_workday(cur, day)
        if type(data.get('student_id')) is not int or (data.get('leader_id') is not None and type(data['leader_id']) is not int):
            raise ValueError('分组人员不合法。')
        before = stored_assignments(result)
        assignments = move_student(result['people'], before, data['student_id'], data.get('leader_id'))
        validate_team_changes(cur,day,before,assignments)
        validate_driving_teams(result['people'], assignments)
        if assignments != before:
            result['revision'] = save_teams(cur, actor, day, assignments, before)
        result['groups'] = group_assignments(assignments)
    elif data['action'] == 'apply' and data.get('source') == 'current':
        require_workday(cur, day)
        before = stored_assignments(result)
        if proposal_token(actor, result, before) != data.get('token'):
            raise ScheduleConflict('档期、分组或站点派工已变化，请重新载入当前安排后调整。')
        assignments = adjust_members(result['people'], before, data.get('moves', []))
        validate_team_changes(cur, day, before, assignments)
        validate_driving_teams(result['people'], assignments)
        result['revision'] = save_teams(cur, actor, day, assignments, before)
        result['groups'] = group_assignments(assignments)
    else:
        require_workday(cur, day)
        if result['unconfirmed']:
            raise ScheduleConflict('该日人员档期尚未全部确认，请先为以下人员选择有空或没空：'+'、'.join(result['unconfirmed']))
        seed = data.get('seed') or secrets.token_hex(16)
        if not isinstance(seed, str) or not re.fullmatch('[0-9a-f]{32}', seed):
            raise ValueError('随机预览标识不合法，请重新预览。')
        if not result['people']: raise ValueError('所选日期没有已确认有空且匹配账号的人员。')
        annotated = [p for group in result['groups'] for p in group['members']]
        assignments = propose_teams(result['people'], annotated, data.get('manager_modes'), seed)
        token = proposal_token(actor, result, assignments, seed)
        if data['action'] in ('confirm', 'apply'):
            if data['action'] == 'apply' and data.get('source') != 'generated':
                raise ValueError('请选择智能生成方案或当前安排进行调整。')
            if token != data.get('token'): raise ScheduleConflict('档期、站点排班或实绩已变化，请重新预览。')
            assignments = adjust_preview(result['people'], assignments, data.get('student_leaders', {}))
            assignments = adjust_members(result['people'], assignments, data.get('moves', []))
            assignments = clean_assignments(assignments)
            validate_dispatched_teams(cur, day, assignments)
            before = stored_assignments(result)
            validate_team_changes(cur,day,before,assignments)
            validate_driving_teams(result['people'], assignments)
            result['revision'] = save_teams(cur, actor, day, assignments, before)
        result.update(groups=annotate_dispatch_locks(cur,day,group_assignments(assignments)),
                      unassigned_people=[p for p in result['unassigned_people']
                                         if p['id'] not in {a['id'] for a in assignments}],
                      token=token, seed=seed, source='generated', manager_modes=data.get('manager_modes'))
    if data['action'] != 'preview':
        sync_field_team_plans(cur, actor, day)
        fresh = context(cur, day)
        fresh['current_token'] = proposal_token(actor, fresh, stored_assignments(fresh))
        result.update(fresh)
        seed_daily_shelf(cur,actor,day,group_assignments(stored_assignments(result)),result['revision'])
        assert_actuals_window(window,today())
    return result


def register_staff_daily_teams(app, *, connect, has_permission):
    @app.get('/api/staff-availability/inspection-dates')
    def staff_planning_dates():
        actor = getattr(g, 'current_user', None)
        if not actor: return jsonify(success=False, error='请先登录。'), 401
        conn = cur = None
        try:
            conn = connect(); cur = conn.cursor()
            if not has_permission(cur, actor, VIEW): raise PermissionError('当前账号无权查看人员档期。')
            ensure_today_availability(cur)
            dates = eligible_dates(cur, [name for name, _ in STAFF], as_of=today())
            conn.commit()
            response = jsonify(success=True, dates=dates, today=today().isoformat())
            response.headers['Cache-Control'] = 'private, no-store'
            return response
        except PermissionError as exc:
            if conn: conn.rollback()
            return jsonify(success=False, error=str(exc)), 403
        except Exception:
            if conn: conn.rollback()
            logging.exception('Staff planning dates failed')
            return jsonify(success=False, error='可安排日期暂时无法读取。'), 500
        finally:
            if cur: cur.close()
            if conn: conn.close()

    @app.route('/api/staff-availability/today-inspection', methods=['GET', 'POST'])
    def daily_team_endpoint():
        actor = getattr(g, 'current_user', None)
        if not actor: return jsonify(success=False, error='请先登录。'), 401
        conn = cur = None
        try:
            conn = connect(); cur = conn.cursor()
            cur.execute("SET LOCAL lock_timeout='3s'; SET LOCAL statement_timeout='10s'")
            if not has_permission(cur, actor, VIEW): raise PermissionError('当前账号无权查看人员档期。')
            can_edit = has_permission(cur, actor, EDIT)
            if request.method == 'GET':
                batch = request.args.get('dates')
                days = planning_days(batch if batch is not None else [request.args.get('day', today().isoformat())], earliest=today())
                results = []
                for day in days:
                    result = context(cur, day)
                    result['current_token'] = proposal_token(actor, result, stored_assignments(result))
                    results.append(dict(result, can_edit=can_edit))
            else:
                if not can_edit: raise PermissionError('当前账号不能安排巡检。')
                data = request.get_json(silent=True)
                if not isinstance(data, dict): raise ValueError('请提交有效的巡检分组方案。')
                batch = data.get('plans')
                if batch is not None:
                    if data.get('action') not in ('preview', 'apply') or not isinstance(batch, list) or any(not isinstance(p, dict) for p in batch):
                        raise ValueError('批量请选择生成或采用巡检方案。')
                    days = planning_days([p.get('day') for p in batch], earliest=today())
                    by_day = {p['day']: p for p in batch}
                    plans = [dict(by_day[day.isoformat()], action=data['action']) for day in days]
                else:
                    plans = [data]
                # Each date uses its own revision/token; the outer transaction commits all or none.
                window = actuals_window(today())
                results = []
                for plan in plans:
                    try:
                        results.append(dict(process_day(cur, actor, plan, can_edit), can_edit=can_edit))
                    except (ValueError, PermissionError) as exc:
                        if len(plans) > 1: raise type(exc)(f"{plan['day']}：{exc}") from exc
                        raise
                if data['action'] != 'preview': assert_actuals_window(window, today())
            conn.commit()
            response = jsonify(success=True, results=results) if batch is not None else jsonify(success=True, **results[0])
            response.headers['Cache-Control'] = 'private, no-store'
            return response
        except (ValueError, PermissionError) as exc:
            if conn: conn.rollback()
            return jsonify(success=False, error=str(exc)), 409 if isinstance(exc, ScheduleConflict) else 403 if isinstance(exc, PermissionError) else 400
        except Exception:
            if conn: conn.rollback()
            logging.exception('Staff team request failed')
            return jsonify(success=False, error='巡检安排暂时无法处理，请稍后重试。'), 500
        finally:
            if cur: cur.close()
            if conn: conn.close()
