"""Multi-date station proposals with pure reservations and atomic adoption."""
import logging
from flask import g, jsonify, request
from inspection_schedule import VIEW_PERMISSION, EDIT_PERMISSION
from schedule_common import ScheduleConflict, lock_schedule, today
from schedule_dates import planning_days
from schedule_driving_routes import DrivingPlanNeeded
from driving_errors import DrivingUnavailable
from schedule_smart import apply_smart_plan
from schedule_quotas import read_quotas, save_quotas
from staff_actuals import actuals_window, assert_actuals_window


def register_batch_scheduling(app, *, connect, has_permission, driving_service, build_proposal):
    @app.post('/api/inspection-schedule/auto/batch')
    def batch_schedule():
        actor = getattr(g, 'current_user', None)
        if not actor: return jsonify(success=False, error='请先登录。'), 401
        conn = cur = None

        def open_context():
            nonlocal conn, cur
            conn = connect(); cur = conn.cursor()
            if not has_permission(cur, actor, VIEW_PERMISSION) or not has_permission(cur, actor, EDIT_PERMISSION):
                raise PermissionError('当前账号不能自动排班。')
            cur.execute("SET LOCAL lock_timeout='3s'; SET LOCAL statement_timeout='10s'")

        def close_context():
            nonlocal conn, cur
            if conn: conn.rollback()
            if cur: cur.close(); cur = None
            if conn: conn.close(); conn = None

        try:
            open_context()
            data = request.get_json(silent=True)
            if not isinstance(data, dict) or data.get('action') not in ('preview', 'confirm'):
                raise ValueError('请选择生成或采用批量智能排班。')
            days = planning_days(data.get('dates'), earliest=today())
            if driving_service is None: raise DrivingUnavailable('路网排班服务尚未初始化。')
            options = dict(strategy='replace_today', offline_count=data.get('offline_count'),
                           online_count=data.get('online_count'), quota_revision=data.get('quota_revision'), replace_days=days)
            current_quotas = read_quotas(cur)
            if options['quota_revision'] != current_quotas['revision']:
                raise ScheduleConflict('站数配置已变化，请重新打开后计算。')
            results, reservations = [], []
            if data['action'] == 'preview':
                for day in days:
                    try:
                        build_proposal(cur, actor, day, options, reserved=reservations)
                    except DrivingPlanNeeded as needed:
                        route_request = needed.request
                    # No business writes, global lock or transaction while solving routes.
                    close_context()
                    driving = driving_service.prepare(route_request)
                    open_context()
                    result, _ = build_proposal(cur, actor, day, options, driving_plan=driving, reserved=reservations)
                    results.append(result)
                    reservations.extend(dict(group, day=day.isoformat()) for group in result['groups'])
                    driving_service.remember(result['token'], actor['id'], day, driving)
            else:
                if data.get('replace_confirmed') is not True:
                    raise ValueError('请确认替换所选日期尚未开始的排班。')
                tokens = data.get('tokens')
                if not isinstance(tokens, dict) or set(tokens) != {day.isoformat() for day in days}:
                    raise ValueError('请先为全部所选日期生成有效方案。')
                close_context()
                driving = {day: driving_service.recall(tokens[day.isoformat()], actor['id'], day) for day in days}
                open_context()
                lock_schedule(cur)
                cur.execute('LOCK TABLE inspections, issues IN SHARE MODE')
                window = actuals_window(today())
                # Validate every snapshot before changing any date. Reservations
                # are rebuilt server-side and cannot be supplied by the client.
                pending = []
                for day in days:
                    result, periods = build_proposal(cur, actor, day, options, driving_plan=driving[day], reserved=reservations)
                    if result['token'] != tokens[day.isoformat()]:
                        raise ScheduleConflict(f'{day}的人员、档期或排班已变化，请重新生成整批方案。')
                    if not result['groups']: raise ValueError(f'{day}没有可安排任务，请取消该日期后重新生成。')
                    pending.append((day,result,periods))
                    reservations.extend(dict(group, day=day.isoformat()) for group in result['groups'])
                if (data['offline_count'], data['online_count']) != (current_quotas['offline_count'], current_quotas['online_count']):
                    current_quotas = save_quotas(cur, actor, dict(offline_count=data['offline_count'], online_count=data['online_count'],
                                                               quota_revision=data['quota_revision']))
                for day, result, periods in pending:
                    result['replaced_cell_count'] = apply_smart_plan(cur, actor, result, periods, day)
                    results.append(result)
                assert_actuals_window(window, today())
                conn.commit()
            response = jsonify(success=True, results=results, quota_settings=current_quotas)
            response.headers['Cache-Control'] = 'private, no-store'
            return response
        except DrivingUnavailable as exc:
            return jsonify(success=False, error=str(exc)), 503
        except (ValueError, PermissionError) as exc:
            return jsonify(success=False, error=str(exc)), 409 if isinstance(exc, ScheduleConflict) else 403 if isinstance(exc, PermissionError) else 400
        except Exception:
            logging.exception('Multi-date scheduling failed')
            return jsonify(success=False, error='批量排班未完成，未保存本批次任何安排，请重新核对。'), 500
        finally:
            close_context()
