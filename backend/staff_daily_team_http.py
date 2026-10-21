"""Two-stage daily personnel allocation; does not invent station/checklist tasks."""
import hashlib
import json
import logging
import re
import secrets
from datetime import timedelta
from flask import g, jsonify, request
from schedule_common import ScheduleConflict, day_value, lock_schedule, require_workday, today
from staff_availability import STAFF, VIEW, EDIT, available_people, excluded_reason
from staff_actuals import actuals_window, assert_actuals_window
from inspection_schedule import sync_field_team_plans
from staff_daily_teams import adjust_preview, group_assignments, move_student, random_teams, save_teams, team_days, validate_dispatched_teams


def context(cur, day):
    people = available_people(cur, day)
    saved = team_days(cur, day, day + timedelta(days=1)).get(day.isoformat(), {})
    cur.execute('SELECT working FROM quality_work_calendar WHERE day=%s', (day,))
    calendar = cur.fetchone()
    eligible = [p for p in people if p['id'] and p['available'] is True]
    unconfirmed = [p['display_name'] for p in people if p['available'] is None]
    return dict(day=day.isoformat(), working=bool(calendar and calendar['working']), people=eligible,
                unconfirmed=unconfirmed, confirmed_count=len(people)-len(unconfirmed), total_count=len(people),
                revision=saved.get('revision', 0), groups=group_assignments(saved.get('assignments', [])),
                updated_by_name=saved.get('updated_by_name', ''), updated_at=saved.get('updated_at', ''),
                excluded=[dict(name=p['display_name'], reason=excluded_reason(p))
                          for p in people if p not in eligible])


def register_staff_daily_teams(app, *, connect, has_permission):
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
            day = today()
            window = actuals_window(day)
            if request.method == 'GET':
                result = context(cur, day)
            else:
                if not can_edit: raise PermissionError('当前账号不能安排今日巡检。')
                data = request.get_json(silent=True)
                if not isinstance(data, dict) or data.get('action') not in ('preview', 'confirm', 'move'):
                    raise ValueError('请选择预览、确认或调整今日分组。')
                if day_value(data.get('day')) != day:
                    raise ScheduleConflict('日期已变化，请重新打开今日巡检安排。')
                if data['action'] != 'preview':
                    lock_schedule(cur)
                    cur.execute('SELECT id FROM users WHERE TRIM(real_name)=ANY(%s) ORDER BY id FOR SHARE', ([name for name, _ in STAFF],))
                    cur.fetchall()
                result = context(cur, day)
                if type(data.get('revision')) is not int or data['revision'] != result['revision']:
                    raise ScheduleConflict('今日分组已被修改，请重新载入后安排。')
                if data['action'] == 'move':
                    require_workday(cur, day)
                    if type(data.get('student_id')) is not int or (data.get('leader_id') is not None and type(data['leader_id']) is not int):
                        raise ValueError('分组人员不合法。')
                    before = [p for group in result['groups'] for p in group['members']]
                    assignments = move_student(result['people'], before, data['student_id'], data.get('leader_id'))
                    if assignments != before:
                        result['revision'] = save_teams(cur, actor, day, assignments, before)
                        sync_field_team_plans(cur, actor, day)
                    result['groups'] = group_assignments(assignments)
                else:
                    require_workday(cur, day)
                    if result['unconfirmed']:
                        raise ScheduleConflict('今日人员档期尚未全部确认，请先为以下人员选择有空或没空：'+'、'.join(result['unconfirmed']))
                    seed = data.get('seed') or secrets.token_hex(16)
                    if not isinstance(seed, str) or not re.fullmatch('[0-9a-f]{32}', seed):
                        raise ValueError('随机预览标识不合法，请重新预览。')
                    if not result['people']: raise ValueError('今天没有已确认有空且匹配账号的人员。')
                    assignments = random_teams(result['people'], data.get('manager_modes'), seed)
                    evidence = dict(actor=actor['id'], context=result, assignments=assignments, seed=seed)
                    token = hashlib.sha256(json.dumps(evidence, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
                    if data['action'] == 'confirm':
                        if token != data.get('token'): raise ScheduleConflict('档期、站点排班或实绩已变化，请重新预览。')
                        assignments = adjust_preview(result['people'], assignments, data.get('student_leaders', {}))
                        validate_dispatched_teams(cur, day, assignments)
                        before = [p for group in result['groups'] for p in group['members']]
                        result['revision'] = save_teams(cur, actor, day, assignments, before)
                    result.update(groups=group_assignments(assignments), token=token, seed=seed)
            if request.method == 'POST' and data['action'] != 'preview': assert_actuals_window(window,today())
            conn.commit()
            response = jsonify(success=True, can_edit=can_edit, **result)
            response.headers['Cache-Control'] = 'private, no-store'
            return response
        except (ValueError, PermissionError) as exc:
            if conn: conn.rollback()
            return jsonify(success=False, error=str(exc)), 409 if isinstance(exc, ScheduleConflict) else 403 if isinstance(exc, PermissionError) else 400
        except Exception:
            if conn: conn.rollback()
            logging.exception('Daily staff team request failed')
            return jsonify(success=False, error='今日巡检安排暂时无法处理，请稍后重试。'), 500
        finally:
            if cur: cur.close()
            if conn: conn.close()
