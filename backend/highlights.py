"""Highlights deliberately have no inspection, standard or rectification foreign keys."""
import logging
import json
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


def operation_permissions(core, cur, user, row, *, scoped=False, caps=None):
    caps = caps or {
        'edit': core.can_edit_inspection_issues(cur, user),
        'delete': core.can_delete_inspection_issues(cur, user),
        'change': core.can_change_issue_inspector(cur, user),
    }
    allowed = scoped or (
        (core.can_view_all_inspection_issues(cur, user) or core.can_view_region_inspection_issues(cur, user)
         or core.issue_created_by_user(user, row)
         or (core.can_view_own_inspection_issues(cur, user) and user.get('station_id') == row['station_id']))
        and core.is_inspection_table_allowed_for_user(cur, user, row['inspection_table_id'], 'limit_issue_inspection_table_scope')
        and core.is_station_region_allowed_for_user(cur, user, row['region'], 'limit_issue_station_region_scope'))
    # Highlights never enter inspection signing or rectification; only the audit lock applies.
    creator = core.can_user_use_creator_issue_controls(user, dict(row, status='待整改'))
    return dict(can_edit=bool(allowed and (caps['edit'] or creator)),
                can_delete=bool(allowed and (caps['delete'] or creator)),
                can_change_inspector=bool(allowed and caps['change']))


def filters(core, cur, user, source):
    where, params = core.build_issue_list_visibility_scope(cur, user)
    def selections(key):
        value = source.get(key) or ''
        if isinstance(value, str) and value.startswith('['):
            try:
                value = json.loads(value)
            except ValueError:
                raise ValueError('筛选条件格式不正确。') from None
        if not isinstance(value, list): value = [value]
        if any(not isinstance(item, str) for item in value): raise ValueError('筛选条件格式不正确。')
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))
    for key, column in [('region', 's.region'), ('station', 's.station_name'),
                        ('table', 't.table_name')]:
        value = selections(key)
        if value:
            where.append(f'{column} = ANY(%s)'); params.append(value)
    if source.get('status'):
        where.append('i.audit_status = %s'); params.append(source['status'])
    for key, column in [('description', 'i.description'), ('manager', 's.station_manager_name')]:
        value = str(source.get(key) or '').strip()
        if value:
            where.append(f'{column} ILIKE %s'); params.append('%' + value + '%')
    if not core.should_hide_inspector_contact_info(cur, user):
        inspectors = selections('inspectors')
        if inspectors:
            where.append("(u.real_name = ANY(%s) OR u.username = ANY(%s) OR u.phone = ANY(%s))")
            params.extend([inspectors] * 3)
        elif source.get('inspector'):
            where.append('u.real_name ILIKE %s'); params.append('%' + str(source['inspector']) + '%')
    if source.get('id'):
        where.append("('HL' || i.id::text) = %s")
        params.append(str(source['id']).strip().upper())
    start, end = source.get('date_from'), source.get('date_to')
    if source.get('month'):
        first = datetime.strptime(source['month'], '%Y-%m')
        start = first.strftime('%Y-%m-%d')
        where.append("i.created_at < %s::date + INTERVAL '1 month'"); params.append(start)
        end = None
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
            cur.execute(f'''SELECT i.*,i.xmin::text AS revision, 'HL' || i.id::text AS display_id,
                to_char(i.created_at, 'YYYY-MM') AS month, to_char(i.created_at, 'YYYY-MM-DD HH24:MI') AS time,
                s.region, s.station_name AS station, s.station_manager_name AS station_manager,
                s.station_manager_phone, COALESCE(NULLIF(u.real_name,''),u.username) AS inspector, u.phone AS inspector_phone,
                t.table_name AS inspection_table_name, auditor.real_name AS audited_by_name,
                to_char(i.audited_at, 'YYYY-MM-DD HH24:MI:SS') AS audited_at
                {JOINS} WHERE {where} ORDER BY i.id DESC LIMIT %s OFFSET %s''', [*params, size, (page-1)*size])
            rows = [dict(row) for row in cur.fetchall()]
            hide = core.should_hide_inspector_contact_info(cur, user)
            audit_allowed = core.can_audit_inspection_issues(cur, user)
            audit_all = core.can_view_all_inspection_issues(cur, user) or core.can_view_region_inspection_issues(cur, user)
            audit_own = core.can_view_own_inspection_issues(cur, user)
            caps = {'edit': core.can_edit_inspection_issues(cur,user), 'delete': core.can_delete_inspection_issues(cur,user), 'change': core.can_change_issue_inspector(cur,user)}
            for row in rows:
                row.update(operation_permissions(core,cur,user,row,scoped=True,caps=caps))
                row['status_label'] = LABELS[row['audit_status']]
                # Rows have already passed the shared table and region SQL scope.
                row['can_audit'] = bool(audit_allowed and (audit_all or (audit_own and user.get('station_id') == row['station_id'])))
                if hide:
                    row['inspector'] = row['inspector_phone'] = ''
                    row.pop('inspector_id', None)
            return jsonify(success=True, items=rows, total=total, page=page, page_size=size,
                           can_manage=bool(any(caps.values()) or core.has_permission(cur,user,'submit_inspections')))
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
                array_agg(DISTINCT t.table_name) AS tables,
                array_agg(DISTINCT s.station_manager_name) AS managers,
                array_agg(DISTINCT COALESCE(NULLIF(u.real_name,''),u.username)) AS inspectors
                {JOINS} WHERE {where}''', params)
            row = cur.fetchone()
            result = {k: sorted(v for v in row[k] or [] if v) for k in ('regions','stations','tables','managers','inspectors')}
            result['hide_inspector_contact'] = core.should_hide_inspector_contact_info(cur, user)
            if result['hide_inspector_contact']: result['inspectors'] = []
            return jsonify(result)
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
            cur.execute('''SELECT i.*,i.xmin::text AS revision, s.region FROM inspection_highlights i JOIN stations s ON s.id=i.station_id
                WHERE i.id=%s FOR UPDATE OF i''', (highlight_id,))
            row = cur.fetchone()
            if not row: return jsonify(error='亮点不存在。'), 404
            if not can_audit(core, cur, user, row): return jsonify(error='无权审核该亮点。'), 403
            if data.get('expected_status') != row['audit_status']:
                return jsonify(error='审核状态已变化，请刷新后重试。'), 409
            if data.get('expected_revision') is not None and str(data['expected_revision']) != row['revision']:
                return jsonify(error='亮点内容已被更新，请重新查看后审核。'), 409
            if target != row['audit_status']:
                cur.execute('''INSERT INTO inspection_highlight_audits (highlight_id,actor_id,from_status,to_status,note)
                    VALUES (%s,%s,%s,%s,%s)''', (highlight_id,user['id'],row['audit_status'],target,note))
                cur.execute('''UPDATE inspection_highlights SET audit_status=%s,audited_by=%s,audited_at=CURRENT_TIMESTAMP,
                    audit_note=%s WHERE id=%s''', (target,user['id'],note,highlight_id))
            cur.execute('SELECT xmin::text AS revision FROM inspection_highlights WHERE id=%s',(highlight_id,))
            revision = cur.fetchone()['revision']
            permissions = operation_permissions(core,cur,user,dict(row,audit_status=target))
            conn.commit()
            return jsonify(success=True, revision=revision, **permissions, audit_status=target, audited_by_name=user.get('real_name') or user.get('username'), audited_at=core.beijing_now().isoformat())
        except Exception:
            if conn: conn.rollback()
            logging.exception('Highlight audit failed'); return jsonify(error='审核失败，请稍后重试。'), 500
        finally: core.close_db_resources(cur, conn)

    @app.route('/api/highlights/<int:highlight_id>', methods=['PUT','DELETE'])
    def manage_highlight(highlight_id):
        conn = cur = None
        saved_photo = None
        try:
            user = core.get_current_request_user()
            conn = core.get_db_connection(); cur = conn.cursor()
            cur.execute('''SELECT i.*,i.xmin::text AS revision,s.region FROM inspection_highlights i
              JOIN stations s ON s.id=i.station_id WHERE i.id=%s FOR UPDATE OF i''',(highlight_id,))
            row = cur.fetchone()
            if not row: return jsonify(error='亮点不存在或已被删除。'),404
            permissions = operation_permissions(core,cur,user,row)
            allowed = permissions['can_delete'] if request.method == 'DELETE' else permissions['can_edit'] or permissions['can_change_inspector']
            if not allowed: return jsonify(error='无权操作该亮点；已审核记录需相应管理权限。'),403
            data = request.form if request.form else request.get_json(silent=True) or {}
            if str(data.get('expected_revision') or '') != row['revision']:
                return jsonify(error='亮点已更新，请重新加载后再操作。'),409
            if request.method == 'DELETE':
                cur.execute('DELETE FROM inspection_highlights WHERE id=%s',(highlight_id,))
                conn.commit()
                return jsonify(success=True)
            if set(data) - {'description','target_inspector_id','expected_revision'} or set(request.files) - {'photo'}:
                return jsonify(error='亮点仅允许编辑描述、照片或调整检查人。'),400
            description = str(data.get('description',row['description'])).strip()
            photo = request.files.get('photo')
            if not permissions['can_edit'] and (description != row['description'] or photo):
                return jsonify(error='当前账号只能调整检查人，不能修改亮点内容。'),403
            if not description or len(description)>10000: return jsonify(error='请填写亮点描述，不超过10000字。'),400
            inspector = int(data.get('target_inspector_id') or row['inspector_id'])
            if inspector != row['inspector_id']:
                if not permissions['can_change_inspector']: return jsonify(error='无权调整检查人。'),403
                target = core.get_user_by_id(cur,inspector)
                if not target or not (core.is_supervisor_like(target) or core.has_permission(cur,target,'submit_inspections')):
                    return jsonify(error='目标检查人必须具备巡检登记权限。'),400
            path = row['photo_path']
            if photo and photo.filename:
                path = saved_photo = core.save_uploaded_file(photo,'issues')
            cur.execute('''UPDATE inspection_highlights SET description=%s,photo_path=%s,inspector_id=%s WHERE id=%s''',
                        (description,path,inspector,highlight_id))
            cur.execute('''INSERT INTO inspection_highlight_audits(highlight_id,actor_id,from_status,to_status,note)
              VALUES(%s,%s,%s,%s,%s)''',(highlight_id,user['id'],row['audit_status'],row['audit_status'],
              '编辑亮点内容' + (f"；检查人ID {row['inspector_id']} → {inspector}" if inspector != row['inspector_id'] else '')))
            conn.commit(); saved_photo = None
            return jsonify(success=True)
        except (TypeError,ValueError):
            if conn: conn.rollback()
            return jsonify(error='提交参数不正确。'),400
        except Exception:
            if conn: conn.rollback()
            logging.exception('Highlight management failed')
            return jsonify(error='亮点操作失败，请稍后重试。'),500
        finally:
            if saved_photo: core.remove_storage_file(saved_photo)
            core.close_db_resources(cur,conn)

    @app.get('/api/highlights/<int:highlight_id>/inspector-options')
    def highlight_inspector_options(highlight_id):
        conn = cur = None
        try:
            user = core.get_current_request_user(); conn = core.get_db_connection(); cur = conn.cursor()
            cur.execute('SELECT i.*,s.region FROM inspection_highlights i JOIN stations s ON s.id=i.station_id WHERE i.id=%s',(highlight_id,))
            row = cur.fetchone()
            if not row or not operation_permissions(core,cur,user,row)['can_change_inspector']:
                return jsonify(error='无权调整该亮点检查人。'),403
            cur.execute("SELECT id,username,real_name,role FROM users ORDER BY id")
            users = cur.fetchall()
            return jsonify(items=[{'id':u['id'],'name':u.get('real_name') or u['username']} for u in users
                if core.is_supervisor_like(u) or core.has_permission(cur,u,'submit_inspections')])
        except Exception:
            logging.exception('Highlight inspector options failed')
            return jsonify(error='检查人员读取失败。'),500
        finally: core.close_db_resources(cur,conn)
