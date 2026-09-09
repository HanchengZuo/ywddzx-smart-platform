"""Highlights deliberately have no inspection, standard or rectification foreign keys."""
import logging
from datetime import datetime
from types import SimpleNamespace
from flask import jsonify, request

LABELS = {'pending': '待审核', 'approved': '已确认亮点', 'rejected': '审核未通过'}
# Compatibility alias for the shared issue visibility predicate, not an inspection record.
JOINS = '''FROM inspection_highlights i
 JOIN stations s ON s.id=i.station_id
 JOIN inspection_tables t ON t.id=i.inspection_table_id
 JOIN users u ON u.id=i.inspector_id
 CROSS JOIN LATERAL (SELECT i.inspector_id) ins
 LEFT JOIN users auditor ON auditor.id=i.audited_by'''


def can_list(core, cur, user):
    return any(core.has_permission(cur, user, key) for key in (
        'view_all_inspection_issues', 'limit_issue_station_region_scope',
        'view_own_inspection_issues', 'submit_inspections'))


def can_audit(core, cur, user, row):
    return (core.can_audit_inspection_issues(cur, user)
            and (core.can_view_all_inspection_issues(cur, user)
                 or core.can_view_region_inspection_issues(cur, user)
                 or (core.can_view_own_inspection_issues(cur, user) and user.get('station_id') == row['station_id']))
            and core.is_inspection_table_allowed_for_user(cur, user, row['inspection_table_id'], 'limit_issue_inspection_table_scope')
            and core.is_station_region_allowed_for_user(cur, user, row['region'], 'limit_issue_station_region_scope'))


def filters(core, cur, user, source):
    where, params = core.build_issue_list_visibility_scope(cur, user)
    for key, column in [('region', 's.region'), ('station', 's.station_name'),
                        ('table', 't.table_name'), ('status', 'i.audit_status')]:
        value = str(source.get(key) or '').strip()
        if value:
            where.append(f'{column} = %s'); params.append(value)
    for key, column in [('description', 'i.description'), ('manager', 's.station_manager_name'), ('inspector', 'u.real_name')]:
        value = str(source.get(key) or '').strip()
        if value and not (key == 'inspector' and core.should_hide_inspector_contact_info(cur, user)):
            where.append(f'{column} ILIKE %s'); params.append('%' + value + '%')
    if source.get('id'):
        where.append("('HL' || i.id::text) = %s")
        params.append(str(source['id']).strip().upper())
    start, end = source.get('date_from'), source.get('date_to')
    if start: datetime.strptime(start, '%Y-%m-%d')
    if end: datetime.strptime(end, '%Y-%m-%d')
    if start and end and start > end: raise ValueError('开始日期不能晚于结束日期。')
    if start: where.append('i.created_at >= %s::date'); params.append(start)
    if end: where.append("i.created_at < %s::date + INTERVAL '1 day'"); params.append(end)
    return ' AND '.join(where) or 'TRUE', params


def register_highlights(app, namespace):
    core = SimpleNamespace(**namespace)

    @app.route('/api/highlights', methods=['GET', 'POST'])
    def highlights():
        conn = cur = None
        saved_photo = None
        try:
            user = core.get_current_request_user()
            conn = core.get_db_connection(); cur = conn.cursor()
            if request.method == 'POST':
                if not core.has_permission(cur, user, 'submit_inspections'):
                    return jsonify(error='当前账号无权登记亮点。'), 403
                station = request.form.get('station_id', '')
                table = request.form.get('inspection_table_id', '')
                description = request.form.get('description', '').strip()
                photo = request.files.get('photo')
                if not station.isdigit() or not table.isdigit() or not description or len(description) > 10000 or not photo or not photo.filename:
                    return jsonify(error='请选择站点和检查表，填写亮点描述（不超过10000字）并上传照片。'), 400
                cur.execute('SELECT id, region FROM stations WHERE id=%s', (station,))
                row = cur.fetchone()
                cur.execute('SELECT id FROM inspection_tables WHERE id=%s', (table,))
                if not row or not cur.fetchone(): return jsonify(error='站点或检查表不存在。'), 400
                if not core.is_station_region_allowed_for_user(cur, user, row['region'], 'limit_issue_station_region_scope') or not core.is_inspection_table_allowed_for_user(cur, user, int(table), 'limit_issue_inspection_table_scope'):
                    return jsonify(error='当前账号无权登记该站点或检查表的亮点。'), 403
                path = core.save_uploaded_file(photo, 'issues')
                saved_photo = path
                cur.execute('''INSERT INTO inspection_highlights (station_id, inspector_id, inspection_table_id, description, photo_path)
                    VALUES (%s,%s,%s,%s,%s) RETURNING id''', (station, user['id'], table, description, path))
                identifier = cur.fetchone()['id']; conn.commit(); saved_photo = None
                return jsonify(success=True, id=f'HL{identifier}', message=f'亮点 HL{identifier} 已登记，请到亮点列表查看审核结果。')
            if not can_list(core, cur, user): return jsonify(error='当前账号无权查看亮点列表。'), 403
            where, params = filters(core, cur, user, request.args)
            page, size = core.normalize_page_args(request.args.get('page'), request.args.get('page_size') or 20)
            cur.execute(f'SELECT COUNT(*) AS total {JOINS} WHERE {where}', params)
            total = cur.fetchone()['total']; page = min(page, max(1, (total + size - 1) // size))
            cur.execute(f'''SELECT i.*, 'HL' || i.id::text AS display_id,
                to_char(i.created_at, 'YYYY-MM') AS month, to_char(i.created_at, 'YYYY-MM-DD HH24:MI') AS time,
                s.region, s.station_name AS station, s.station_manager_name AS station_manager,
                s.station_manager_phone, u.real_name AS inspector, u.phone AS inspector_phone,
                t.table_name AS inspection_table_name, auditor.real_name AS audited_by_name,
                to_char(i.audited_at, 'YYYY-MM-DD HH24:MI:SS') AS audited_at
                {JOINS} WHERE {where} ORDER BY i.id DESC LIMIT %s OFFSET %s''', [*params, size, (page-1)*size])
            rows = [dict(row) for row in cur.fetchall()]
            hide = core.should_hide_inspector_contact_info(cur, user)
            audit_allowed = core.can_audit_inspection_issues(cur, user)
            audit_all = core.can_view_all_inspection_issues(cur, user) or core.can_view_region_inspection_issues(cur, user)
            audit_own = core.can_view_own_inspection_issues(cur, user)
            for row in rows:
                row['status_label'] = LABELS[row['audit_status']]
                # Rows have already passed the shared table and region SQL scope.
                row['can_audit'] = bool(audit_allowed and (audit_all or (audit_own and user.get('station_id') == row['station_id'])))
                if hide:
                    row['inspector'] = row['inspector_phone'] = ''
                    row.pop('inspector_id', None)
            return jsonify(success=True, items=rows, total=total, page=page, page_size=size)
        except ValueError as exc:
            if conn: conn.rollback()
            return jsonify(error=str(exc)), 400
        except Exception:
            if conn: conn.rollback()
            logging.exception('Highlight request failed')
            return jsonify(error='亮点操作失败，请稍后重试。'), 500
        finally:
            if saved_photo: core.remove_storage_file(saved_photo)
            core.close_db_resources(cur, conn)

    @app.route('/api/highlights/filter-options')
    def highlight_options():
        conn = cur = None
        try:
            user = core.get_current_request_user(); conn = core.get_db_connection(); cur = conn.cursor()
            if not can_list(core, cur, user): return jsonify(error='无权查看亮点。'), 403
            where, params = filters(core, cur, user, {})
            cur.execute(f'''SELECT array_agg(DISTINCT s.region) AS regions, array_agg(DISTINCT s.station_name) AS stations,
                array_agg(DISTINCT t.table_name) AS tables {JOINS} WHERE {where}''', params)
            row = cur.fetchone()
            return jsonify({k: sorted(v for v in row[k] or [] if v) for k in ('regions','stations','tables')})
        except Exception:
            logging.exception('Highlight options failed'); return jsonify(error='筛选项读取失败。'), 500
        finally: core.close_db_resources(cur, conn)

    @app.route('/api/highlights/<int:highlight_id>/audit', methods=['POST'])
    def audit_highlight(highlight_id):
        conn = cur = None
        try:
            user = core.get_current_request_user(); conn = core.get_db_connection(); cur = conn.cursor()
            data = request.get_json(silent=True) or {}
            target = {'approve':'approved','reject':'rejected','reset':'pending'}.get(data.get('action'))
            note = str(data.get('note') or '').strip()
            if not target or len(note) > 2000: return jsonify(error='审核操作或说明不正确。'), 400
            cur.execute('''SELECT i.*, s.region FROM inspection_highlights i JOIN stations s ON s.id=i.station_id
                WHERE i.id=%s FOR UPDATE OF i''', (highlight_id,))
            row = cur.fetchone()
            if not row: return jsonify(error='亮点不存在。'), 404
            if not can_audit(core, cur, user, row): return jsonify(error='无权审核该亮点。'), 403
            if data.get('expected_status') != row['audit_status']:
                return jsonify(error='审核状态已变化，请刷新后重试。'), 409
            if target != row['audit_status']:
                cur.execute('''INSERT INTO inspection_highlight_audits (highlight_id,actor_id,from_status,to_status,note)
                    VALUES (%s,%s,%s,%s,%s)''', (highlight_id,user['id'],row['audit_status'],target,note))
                cur.execute('''UPDATE inspection_highlights SET audit_status=%s,audited_by=%s,audited_at=CURRENT_TIMESTAMP,
                    audit_note=%s WHERE id=%s''', (target,user['id'],note,highlight_id))
            conn.commit()
            return jsonify(success=True, audit_status=target, audited_by_name=user.get('real_name') or user.get('username'), audited_at=core.beijing_now().isoformat())
        except Exception:
            if conn: conn.rollback()
            logging.exception('Highlight audit failed'); return jsonify(error='审核失败，请稍后重试。'), 500
        finally: core.close_db_resources(cur, conn)
