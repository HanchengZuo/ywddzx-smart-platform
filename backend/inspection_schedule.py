"""Quarterly/monthly scheduling intent, with record-derived, read-only completion."""
import json
import hashlib
import logging
from collections import defaultdict
from datetime import timedelta

from flask import g, jsonify, request

from inspection_schedule_catalog import COLUMNS, normalized_region, roster_position
from roles import SUPERVISOR_ROLES
from scheduling_map import period
from station_plan_eligibility import plan_field
from schedule_common import ScheduleConflict, day_value, lock_schedule, require_workday, today, working_days
from staff_availability import available_people, roster_people, validate_people
from inspection_schedule_tasks import dispatch_tasks
from staff_daily_teams import field_team, group_assignments, team_days
from schedule_shelf_store import shelf_items, refresh_field_shelf, expire_shelf

VIEW_PERMISSION = 'view_inspection_schedule'
EDIT_PERMISSION = 'edit_inspection_schedule'


def person(row):
    return dict(id=row['id'], username=row.get('username') or '', role=row.get('role') or '',
                display_name=str(row.get('real_name') or '').strip() or row.get('username') or '未记录姓名')


def period_number(chosen):
    return chosen['quarter' if chosen['mode'] == 'offline' else 'month']


def table_columns(cur, mode, lock=False):
    names = [entry[2] for entry in COLUMNS[mode]]
    cur.execute('''SELECT t.id,t.table_name FROM inspection_tables t
        WHERE t.checklist_mode=%s AND t.is_active=TRUE AND t.table_name=ANY(%s)''' +
                (' FOR SHARE OF t' if lock else ''), [mode, names])
    by_name = defaultdict(list)
    for row in cur.fetchall():
        by_name[row['table_name']].append(row['id'])
    # Ambiguous or missing definitions must not silently attach to a different table.
    return [dict(key=key, label=label, full_name=name,
                 table_id=by_name[name][0] if len(by_name[name]) == 1 else None)
            for key, label, name in COLUMNS[mode]]


def eligible_stations(cur, chosen, station_id=None, lock=False):
    clauses = [f's.{plan_field(chosen["mode"])}=TRUE']
    params = []
    if station_id is not None:
        clauses.append('s.id=%s')
        params.append(station_id)
    cur.execute('SELECT s.id,s.station_name,s.region,s.address,s.longitude,s.latitude FROM stations s WHERE ' +
                ' AND '.join(clauses or ['TRUE']) + (' FOR SHARE OF s' if lock else ''), params)
    rows = [dict(row, sequence=roster_position(row, chosen['mode'])) for row in cur.fetchall()]
    return sorted((row for row in rows if row['sequence']), key=lambda row: (row['sequence'], row['id']))


def record_cells(cur, station_ids, table_ids, start, end):
    if not station_ids or not table_ids:
        return {}
    cur.execute('''WITH matched AS MATERIALIZED (
        SELECT id,station_id,inspection_table_id,inspector_id,inspection_date FROM inspections
        WHERE station_id=ANY(%s) AND inspection_table_id=ANY(%s)
          AND inspection_date >= %s AND inspection_date < %s
      ), participants AS (
        SELECT id AS inspection_id,inspector_id FROM matched WHERE inspector_id IS NOT NULL
        UNION
        SELECT i.inspection_id,i.inspector_id FROM issues i JOIN matched m ON m.id=i.inspection_id
        WHERE i.inspector_id IS NOT NULL
      ) SELECT m.station_id,m.inspection_table_id,COUNT(DISTINCT m.id) AS record_count,
        MAX(m.inspection_date)::text AS last_inspection_date,
        COALESCE(jsonb_agg(DISTINCT jsonb_build_object('id',u.id,'username',u.username,
          'display_name',COALESCE(NULLIF(TRIM(u.real_name),''),u.username),'role',u.role))
          FILTER(WHERE u.id IS NOT NULL),'[]') AS inspectors
      FROM matched m LEFT JOIN participants p ON p.inspection_id=m.id LEFT JOIN users u ON u.id=p.inspector_id
      GROUP BY m.station_id,m.inspection_table_id''', (station_ids, table_ids, start, end))
    return {(row['station_id'], row['inspection_table_id']): dict(row) for row in cur.fetchall()}


def read_board(cur, chosen, start, end):
    columns = table_columns(cur, chosen['mode'])
    stations = eligible_stations(cur, chosen)
    station_ids = [row['id'] for row in stations]
    complete = record_cells(cur, station_ids, [col['table_id'] for col in columns if col['table_id']], start, end)
    cur.execute('''SELECT c.*,COALESCE(NULLIF(TRIM(u.real_name),''),u.username,'未记录') AS updated_by_name,
      to_char(c.updated_at,'YYYY-MM-DD HH24:MI:SS') AS saved_at
      FROM inspection_schedule_cells c LEFT JOIN users u ON u.id=c.updated_by
      WHERE c.mode=%s AND c.year=%s AND c.period_number=%s AND c.station_id=ANY(%s)''',
                (chosen['mode'], chosen['year'], period_number(chosen), station_ids))
    saved = {(row['station_id'], row['column_key']): row for row in cur.fetchall()}
    saved_ids = sorted({int(uid) for row in saved.values() for uid in row['inspector_ids']})
    cur.execute('SELECT id,username,real_name,role FROM users WHERE id=ANY(%s)', (saved_ids,))
    people = {row['id']: person(row) for row in cur.fetchall()}
    roster = roster_people(cur)
    inspectors = [p for p in roster if p['id']]
    rows = []
    summary = dict(completed=0, assigned=0, unassigned=0)
    for station in stations:
        cells = {}
        for column in columns:
            existing = saved.get((station['id'], column['key'])) or {}
            record = complete.get((station['id'], column['table_id'])) or {}
            assignees = [people.get(uid, dict(id=uid, username='', role='', display_name='账号已删除'))
                         for uid in existing.get('inspector_ids', [])]
            status = 'unavailable' if not column['table_id'] else 'completed' if record else 'assigned' if assignees else 'unassigned'
            if status in summary:
                summary[status] += 1
            cells[column['key']] = dict(status=status, assignees=assignees,
                plan_team=existing.get('plan_team'),
                completed_inspectors=sorted(record.get('inspectors', []), key=lambda user: (user['display_name'], user['id'])),
                record_count=record.get('record_count', 0), last_inspection_date=record.get('last_inspection_date'),
                revision=existing.get('revision', 0), updated_by_name=existing.get('updated_by_name', ''),
                updated_at=existing.get('saved_at', ''),
                scheduled_date=existing['scheduled_date'].isoformat() if existing.get('scheduled_date') else None)
        rows.append(dict(station_id=station['id'], station_name=station['station_name'],
                         address=station.get('address') or '',
                         longitude=float(station['longitude']) if station.get('longitude') is not None else None,
                         latitude=float(station['latitude']) if station.get('latitude') is not None else None,
                         region=normalized_region(station['region']), sequence=station['sequence'], cells=cells))
    shelf = shelf_items(cur,chosen['mode'],start,end)
    evidence = dict(rows=[(r['station_id'],[(k,c['revision'],c['status']) for k,c in r['cells'].items()]) for r in rows],
                    shelf=[(s['id'],s['revision']) for s in shelf], day=today().isoformat())
    token=hashlib.sha256(json.dumps(evidence).encode()).hexdigest()
    return dict(period=chosen, columns=columns, rows=rows, inspectors=inspectors, summary=summary,
                shelf=shelf, board_token=token,
                today=today().isoformat(), workdays=working_days(cur, start, end),
                unmatched_people=[p['display_name'] for p in roster if not p['id']])


def integer(value, label, minimum=1):
    if type(value) is not int or value < minimum:
        raise ValueError(f'{label}不合法。')
    return value


def save_cell(cur, actor, data, chosen, start, end, availability_cache=None):
    station_id = integer(data.get('station_id'), '站点')
    key = data.get('column_key')
    if not isinstance(key, str) or key not in {entry[0] for entry in COLUMNS[chosen['mode']]}:
        raise ValueError('检查表列不合法。')
    revision = integer(data.get('revision'), '版本', 0)
    ids = data.get('inspector_ids')
    if not isinstance(ids, list) or len(ids) > 100:
        raise ValueError('请选择督导组检查人，最多100人。')
    ids = sorted({integer(value, '检查人') for value in ids})
    if chosen['mode'] == 'online' and len(ids) > 1:
        raise ValueError('视频检查每个站点只能安排一位检查人。')
    day = day_value(data.get('scheduled_date')) if ids else None
    if day:
        if not start <= day < end: raise ValueError('计划日期必须位于所选季度或月份内。')
        require_workday(cur, day)
    lock_schedule(cur)
    cell_key = (chosen['mode'], chosen['year'], period_number(chosen), station_id, key)
    # Cross-worker serialization plus a revision check avoids lost updates and ABA on clears.
    cur.execute('SELECT pg_advisory_xact_lock(9701,hashtext(%s))', (json.dumps(cell_key),))
    stations = eligible_stations(cur, chosen, station_id, lock=True)
    if len(stations) != 1:
        raise PermissionError('本站不在排班名单内，或已关闭对应计划纳入。')
    column = next(col for col in table_columns(cur, chosen['mode'], lock=True) if col['key'] == key)
    if not column['table_id']:
        raise PermissionError('检查表未启用或定义不唯一，不能安排。')
    if record_cells(cur, [station_id], [column['table_id']], start, end):
        raise ScheduleConflict('该站点本周期已有此检查表的巡检记录，单元格已完成，不能再分配。')
    cur.execute('''SELECT inspector_ids,revision,scheduled_date,plan_team FROM inspection_schedule_cells
      WHERE mode=%s AND year=%s AND period_number=%s AND station_id=%s AND column_key=%s FOR UPDATE''', cell_key)
    existing = cur.fetchone() or dict(inspector_ids=[], revision=0, scheduled_date=None, plan_team=None)
    if existing['revision'] != revision:
        raise ScheduleConflict('该单元格已被其他用户修改，请刷新最新排班后再调整。')
    if ids:
        cur.execute('''SELECT id FROM users WHERE id=ANY(%s) AND role=ANY(%s)
          AND COALESCE(account_status,'active')='active' ORDER BY id FOR SHARE''', (ids, list(SUPERVISOR_ROLES)))
        if {row['id'] for row in cur.fetchall()} != set(ids):
            raise ValueError('只能选择当前启用的督导组管理人员或督导组组员，请重新选择。')
        if availability_cache is not None and day not in availability_cache:
            availability_cache[day] = {p['id']: p for p in available_people(cur, day) if p['id']}
        validate_people(cur, ids, day, chosen['mode'], availability_cache.get(day) if availability_cache is not None else None)
    team = field_team(cur, day, ids) if ids and chosen['mode'] == 'offline' else None
    if existing['inspector_ids'] == ids and existing['scheduled_date'] == day and existing['plan_team'] == team:
        return existing['revision']
    cur.execute('''INSERT INTO inspection_schedule_cells
        (mode,year,period_number,station_id,column_key,inspector_ids,revision,updated_by,scheduled_date,plan_team)
      VALUES (%s,%s,%s,%s,%s,%s,1,%s,%s,%s) ON CONFLICT (mode,year,period_number,station_id,column_key)
      DO UPDATE SET inspector_ids=EXCLUDED.inspector_ids,revision=inspection_schedule_cells.revision+1,
        updated_by=EXCLUDED.updated_by,updated_at=CURRENT_TIMESTAMP,scheduled_date=EXCLUDED.scheduled_date,
        plan_team=EXCLUDED.plan_team RETURNING revision''',
                (*cell_key, json.dumps(ids), actor['id'], day, json.dumps(team, ensure_ascii=False)))
    saved_revision = cur.fetchone()['revision']
    cur.execute('''INSERT INTO inspection_schedule_events
      (mode,year,period_number,station_id,station_name,column_key,before_ids,after_ids,actor_id,actor_name,before_date,after_date,before_team,after_team)
      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
      (chosen['mode'], chosen['year'], period_number(chosen), station_id, stations[0]['station_name'], key,
       json.dumps(existing['inspector_ids']), json.dumps(ids), actor['id'], person(actor)['display_name'], existing['scheduled_date'], day,
       json.dumps(existing['plan_team'], ensure_ascii=False), json.dumps(team, ensure_ascii=False)))
    dispatch_event_id = cur.fetchone()['id']
    dispatch_tasks(cur, actor, chosen, stations[0], column, ids, day, start, team, dispatch_event_id)
    return saved_revision


def validate_edits(cur, edits, chosen, start, end):
    if not isinstance(edits, list) or not 1 <= len(edits) <= 1000:
        raise ValueError('请选择1至1000个排班单元格。')
    by_station = defaultdict(set)
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) - {'station_id', 'column_key', 'revision'}:
            raise ValueError('排班单元格不合法。')
        sid = integer(edit.get('station_id'), '站点')
        key = edit.get('column_key')
        if not isinstance(key, str) or key not in {c[0] for c in COLUMNS[chosen['mode']]}:
            raise ValueError('检查表列不合法。')
        integer(edit.get('revision'), '版本', 0)
        if key in by_station[sid]: raise ValueError('不能重复选择同一排班单元格。')
        by_station[sid].add(key)
    columns = table_columns(cur, chosen['mode'])
    actual = record_cells(cur, list(by_station), [c['table_id'] for c in columns if c['table_id']], start, end)
    for sid, keys in by_station.items():
        expected = {c['key'] for c in columns if c['table_id'] and (sid, c['table_id']) not in actual}
        if keys != expected:
            raise ScheduleConflict('请按站点整行安排所有尚未检查的检查表，已完成的实际记录保持不变。')


def apply_edits(cur, actor, data, chosen, start, end):
    """One transaction for row assignment or staged move, including task cancellation."""
    edits = data.get('cells')
    if edits is None:
        edits = [dict(station_id=data.get('station_id'), column_key=data.get('column_key'), revision=data.get('revision'))]
    lock_schedule(cur)
    validate_edits(cur, edits, chosen, start, end)
    source = data.get('source')
    cache = {}
    if source is not None:
        if not isinstance(source, dict) or not isinstance(source.get('cells'), list):
            raise ValueError('待选区来源不合法，请重新拖入。')
        validate_edits(cur, source['cells'], chosen, start, end)
        if len({e['station_id'] for e in source['cells']}) != 1 or len({e['station_id'] for e in edits}) != 1:
            raise ValueError('一次拖拽只能从一个站点改派到一个站点。')
        ids = data.get('inspector_ids')
        if not isinstance(ids, list) or not ids or len(ids)>100 or any(type(uid) is not int or uid<1 for uid in ids):
            raise ValueError('待选区检查人不合法，请重新拖入。')
        if {(e['station_id'], e['column_key']) for e in edits} & {(e['station_id'], e['column_key']) for e in source['cells']}:
            raise ValueError('目标位置不能与待选区来源相同。')
        # The client cannot use the shelf to clear somebody else's newer assignment.
        for edit in source['cells']:
            cur.execute('''SELECT inspector_ids,scheduled_date FROM inspection_schedule_cells
              WHERE mode=%s AND year=%s AND period_number=%s AND station_id=%s AND column_key=%s''',
              (chosen['mode'], chosen['year'], period_number(chosen), edit['station_id'], edit['column_key']))
            saved = cur.fetchone()
            if not saved or sorted(saved['inspector_ids']) != sorted(data.get('inspector_ids', [])) or str(saved['scheduled_date']) != data.get('scheduled_date'):
                raise ScheduleConflict('待选区原安排已经变化，请重新拖入。')
        for edit in source['cells']:
            save_cell(cur, actor, {**edit, 'inspector_ids': []}, chosen, start, end, cache)
    versions = [save_cell(cur, actor, {**data, **edit}, chosen, start, end, cache) for edit in edits]
    return dict(revision=versions[0], saved_count=len(versions), message='排班已保存，已同步检查人的巡检待办。')


def sync_field_team_plans(cur, actor, day):
    """A same-mode student transfer updates unfinished rows and tasks in the grouping transaction."""
    chosen, start, end = period(dict(mode='offline', year=day.year, quarter=(day.month-1)//3+1))
    saved = team_days(cur, day, day+timedelta(days=1)).get(day.isoformat(), {})
    groups = {g['leader_id']: g for g in group_assignments(saved.get('assignments', [])) if g['mode']=='offline'}
    board = read_board(cur, chosen, start, end)
    cache = {}
    for row in board['rows']:
        for column in board['columns']:
            cell = row['cells'][column['key']]
            team = cell['plan_team']
            if cell['status'] != 'assigned' or cell['scheduled_date'] != day.isoformat() or not team:
                continue
            group = groups.get(team['leader_id'])
            if not group: raise ScheduleConflict('已有派工的外勤带队组不能删除，请先撤销其站点安排。')
            if {p['id'] for p in cell['assignees']} == {p['id'] for p in group['members']}:
                continue
            save_cell(cur, actor, dict(station_id=row['station_id'],column_key=column['key'],revision=cell['revision'],
                      inspector_ids=[p['id'] for p in group['members']],scheduled_date=day.isoformat()), chosen,start,end,cache)
    refresh_field_shelf(cur,actor,day,groups,saved.get('revision',0))


def register_inspection_schedule(app, *, connect, has_permission):
    @app.route('/api/inspection-schedule', methods=['GET', 'PUT'])
    def inspection_schedule_board():
        actor = getattr(g, 'current_user', None)
        if not actor:
            return jsonify(success=False, error='请先登录。'), 401
        conn = cur = None
        try:
            conn = connect()
            cur = conn.cursor()
            if not has_permission(cur, actor, VIEW_PERMISSION):
                raise PermissionError('当前账号无权查看巡检排班。')
            can_edit = has_permission(cur, actor, EDIT_PERMISSION)
            if request.method == 'PUT' and not can_edit:
                raise PermissionError('当前账号只有查看权限，不能编辑排班。')
            data = request.get_json(silent=True) if request.method == 'PUT' else request.args
            if data is None or not hasattr(data, 'get'):
                raise ValueError('请提交有效的排班数据。')
            chosen, start, end = period(data)
            cur.execute("SET LOCAL statement_timeout = '10s'")
            cur.execute("SET LOCAL lock_timeout = '3s'")
            if request.method == 'PUT':
                result = apply_edits(cur, actor, data, chosen, start, end)
                conn.commit()
            else:
                expire_shelf(cur)
                result = read_board(cur, chosen, start, end)
                conn.commit()
            response = jsonify(success=True, can_edit=can_edit, current_user_id=actor['id'], **result)
            response.headers['Cache-Control'] = 'private, no-store'
            return response
        except (ValueError, PermissionError) as exc:
            if conn:
                conn.rollback()
            status = 409 if isinstance(exc, ScheduleConflict) else 403 if isinstance(exc, PermissionError) else 400
            return jsonify(success=False, error=str(exc)), status
        except Exception:
            if conn:
                conn.rollback()
            logging.exception('Inspection schedule request failed')
            return jsonify(success=False, error='排班数据暂时无法处理，请稍后重试。'), 500
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    @app.get('/api/inspection-schedule/available-people')
    def schedule_available_people():
        actor = getattr(g, 'current_user', None)
        if not actor: return jsonify(success=False, error='请先登录。'), 401
        conn = cur = None
        try:
            conn = connect(); cur = conn.cursor()
            if not has_permission(cur, actor, VIEW_PERMISSION): raise PermissionError('当前账号无权查看巡检排班。')
            day = day_value(request.args.get('day')); require_workday(cur, day)
            saved = team_days(cur, day, day + timedelta(days=1)).get(day.isoformat(), {})
            response = jsonify(success=True, day=day.isoformat(), people=available_people(cur, day),
                               groups=group_assignments(saved.get('assignments', [])), team_revision=saved.get('revision', 0))
            response.headers['Cache-Control'] = 'private, no-store'
            return response
        except (ValueError, PermissionError) as exc:
            return jsonify(success=False, error=str(exc)), 403 if isinstance(exc, PermissionError) else 400
        except Exception:
            logging.exception('Available schedule people failed')
            return jsonify(success=False, error='人员档期暂时无法读取。'), 500
        finally:
            if cur: cur.close()
            if conn: conn.close()
