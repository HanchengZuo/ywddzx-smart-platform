"""Station appeal transactions. All identity and scope come from the authenticated session."""
from types import SimpleNamespace
from flask import g, jsonify, request

ACTIVE = ('area_pending', 'quality_pending')
APPEAL_LABELS = {
    'appeal_submitted': '站点发起申诉',
    'appeal_area_approved': '片区通过申诉，转质安部终审',
    'appeal_area_rejected': '片区驳回申诉，恢复整改',
    'appeal_quality_approved': '质安部通过申诉，问题已销毁',
    'appeal_quality_rejected': '质安部驳回申诉，恢复整改',
    'appeal_cancelled': '申诉取消',
}


def appeal_table_allowed(core, name, mode):
    return (core.normalize_checklist_scope_name(name), core.normalize_checklist_mode(mode)) in core.QUALITY_SAFETY_DEFAULT_CHECKLIST_SCOPE


def area_regions(core, cur, user):
    # Force regional scoping even when unrelated issue-view permissions are unrestricted.
    return core.get_effective_station_region_scope_values(
        cur, user, 'limit_issue_station_region_scope', {'limit_issue_station_region_scope': True}
    ) or set()


def can_decide(core, cur, user, appeal):
    if appeal['status'] == 'area_pending':
        return user.get('role') == 'area_account' and core.normalize_station_region_value(appeal['region']) in area_regions(core, cur, user)
    return (appeal['status'] == 'quality_pending' and user.get('role') == 'quality_safety'
            and core.has_permission(cur, user, 'review_quality_appeals'))


def appeal_scope(core, cur, user):
    if user.get('role') == 'station_manager':
        return ['i.station_id = %s'], [user.get('station_id')]
    if user.get('role') == 'area_account':
        return ["COALESCE(NULLIF(TRIM(s.region), ''), '未填写片区') = ANY(%s)"], [list(area_regions(core, cur, user))]
    if core.is_root_user(user) or user.get('role') == 'quality_safety':
        return [], []
    return core.build_issue_list_visibility_scope(cur, user)


def record_event(cur, user, issue_id, kind, old, new, reason):
    cur.execute("""INSERT INTO inspection_issue_flow_history
      (issue_id,action_type,from_status,to_status,result,note,actor_user_id,actor_username,actor_name,actor_role)
      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
      (issue_id, kind, old, new, APPEAL_LABELS[kind], reason, user['id'], user.get('username'), user.get('real_name'), user['role']))


def register_issue_appeals(app, namespace):
    core = SimpleNamespace(**namespace)

    def run(operation):
        conn = cur = None
        try:
            user = getattr(g, 'current_user', None)
            if not user:
                return jsonify(success=False, error='请先登录。'), 401
            conn = core.get_db_connection()
            cur = conn.cursor()
            result = operation(cur, user)
            conn.commit()
            return result
        except ValueError as exc:
            if conn:
                conn.rollback()
            return jsonify(success=False, error=str(exc)), 400
        except Exception:
            if conn:
                conn.rollback()
            app.logger.exception('Issue appeal operation failed')
            return jsonify(success=False, error='申诉处理失败，请稍后重试。如仍失败请联系管理员检查数据库升级。'), 500
        finally:
            core.close_db_resources(cur, conn)

    @app.get('/api/issue-appeals')
    def list_issue_appeals():
        def operation(cur, user):
            page = max(1, int(request.args.get('page', 1)))
            size = 20
            where, params = appeal_scope(core, cur, user)
            archive = request.args.get('archive') == '1'
            where.append("a.status NOT IN ('area_pending','quality_pending')" if archive else "a.status IN ('area_pending','quality_pending')")
            keyword = request.args.get('keyword', '').strip()[:200]
            if keyword:
                where.append('(i.id::text = %s OR s.station_name ILIKE %s OR i.description ILIKE %s)')
                params += [keyword, f'%{keyword}%', f'%{keyword}%']
            joins = 'FROM inspection_issue_appeals a JOIN issues i ON i.id=a.issue_id JOIN stations s ON s.id=i.station_id JOIN inspections ins ON ins.id=i.inspection_id JOIN inspection_tables t ON t.id=i.inspection_table_id'
            predicate = ' AND '.join(where) or 'TRUE'
            cur.execute(f'SELECT count(*) AS total {joins} WHERE {predicate}', params)
            total = cur.fetchone()['total']
            cur.execute(f"""SELECT a.*, i.description, i.standard_id, i.photo_path, i.status AS issue_status,
              s.station_name, s.region, t.table_name,
              to_char(i.created_at,'YYYY-MM-DD HH24:MI') AS inspection_time
              {joins} WHERE {predicate} ORDER BY a.id DESC LIMIT %s OFFSET %s""", params + [size, (page-1)*size])
            rows = cur.fetchall()
            for row in rows:
                row['can_decide'] = can_decide(core, cur, user, row)
                for field in ('created_at', 'updated_at', 'area_at', 'quality_at'):
                    if row.get(field):
                        row[field] = row[field].astimezone(core.BEIJING_TZ).strftime('%Y-%m-%d %H:%M')
            return jsonify(items=rows, total=total, page=page, page_size=size)
        return run(operation)

    @app.post('/api/issues/<int:issue_id>/appeals')
    def submit_issue_appeal(issue_id):
        def operation(cur, user):
            if user['role'] != 'station_manager':
                return jsonify(error='只有站点账号可以发起申诉。'), 403
            reason = str((request.get_json(silent=True) or {}).get('reason') or '').strip()
            if not 1 <= len(reason) <= 4000:
                raise ValueError('请填写申诉理由，最多4000字。')
            # Lock the inspection first, matching inspection reset lock order.
            cur.execute('SELECT inspection_id FROM issues WHERE id=%s', (issue_id,))
            ref = cur.fetchone()
            if not ref:
                return jsonify(error='问题不存在。'), 404
            cur.execute('SELECT id FROM inspections WHERE id=%s FOR UPDATE', (ref['inspection_id'],))
            cur.execute("""SELECT i.*, ins.sign_status, t.table_name, t.checklist_mode FROM issues i
              JOIN inspections ins ON ins.id=i.inspection_id JOIN inspection_tables t ON t.id=i.inspection_table_id
              WHERE i.id=%s FOR UPDATE OF i""", (issue_id,))
            issue = cur.fetchone()
            if not issue:
                return jsonify(error='问题不存在或已被删除。'), 404
            if issue['station_id'] != user.get('station_id'):
                return jsonify(error='只能申诉本账号所属站点的问题。'), 403
            if not appeal_table_allowed(core, issue['table_name'], issue['checklist_mode']):
                raise ValueError('该检查表不支持申诉。')
            if issue['status'] != '待整改' or issue['audit_status'] != 'approved' or issue['sign_status'] != '已签名确认':
                return jsonify(error='仅已签名验收、审核通过且待整改的问题可以申诉，请刷新列表。'), 409
            cur.execute("INSERT INTO inspection_issue_appeals (issue_id,status,reason,submitted_by) VALUES (%s,'area_pending',%s,%s) RETURNING id", (issue_id, reason, user['id']))
            appeal_id = cur.fetchone()['id']
            cur.execute("UPDATE issues SET status='申诉中' WHERE id=%s", (issue_id,))
            record_event(cur, user, issue_id, 'appeal_submitted', '待整改', '申诉中', reason)
            return jsonify(success=True, id=appeal_id, message='问题已进入申诉空间，等待所属片区审核反馈。')
        return run(operation)

    @app.post('/api/issue-appeals/<int:appeal_id>/decision')
    def decide_issue_appeal(appeal_id):
        def operation(cur, user):
            data = request.get_json(silent=True) or {}
            reason = str(data.get('reason') or '').strip()
            decision = data.get('decision')
            stage = data.get('stage')
            if decision not in ('approve', 'reject') or not 1 <= len(reason) <= 4000:
                raise ValueError('请选择通过或拒绝，并填写原因（最多4000字）。')
            cur.execute('SELECT issue_id FROM inspection_issue_appeals WHERE id=%s', (appeal_id,))
            ref = cur.fetchone()
            if not ref:
                return jsonify(error='申诉不存在。'), 404
            cur.execute('SELECT status FROM issues WHERE id=%s FOR UPDATE', (ref['issue_id'],))
            issue = cur.fetchone()
            if not issue:
                return jsonify(error='问题不存在或已被删除。'), 404
            cur.execute('SELECT a.*, s.region FROM inspection_issue_appeals a JOIN issues i ON i.id=a.issue_id JOIN stations s ON s.id=i.station_id WHERE a.id=%s FOR UPDATE OF a', (appeal_id,))
            appeal = cur.fetchone()
            if not appeal:
                return jsonify(error='申诉不存在或已被删除。'), 404
            if appeal['status'] not in ACTIVE or issue['status'] != '申诉中' or stage != appeal['status']:
                return jsonify(error='申诉已处理或阶段已变化，请刷新后查看。'), 409
            if not can_decide(core, cur, user, appeal):
                return jsonify(error='当前账号无权审核此阶段或此片区的申诉。'), 403
            area = appeal['status'] == 'area_pending'
            prefix = 'area' if area else 'quality'
            approved = decision == 'approve'
            next_state = 'quality_pending' if area and approved else 'approved' if approved else 'rejected'
            cur.execute(f"UPDATE inspection_issue_appeals SET status=%s,{prefix}_by=%s,{prefix}_reason=%s,{prefix}_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=%s", (next_state, user['id'], reason, appeal_id))
            new_status = '申诉中' if next_state == 'quality_pending' else '已销毁' if approved else '待整改'
            if next_state == 'approved':
                cur.execute("""UPDATE issues SET status='已销毁',audit_status='rejected',audited_by=%s,
                  audited_at=CURRENT_TIMESTAMP,audit_source='manual',is_excellent=FALSE,
                  auto_audit_rule_id=NULL,auto_audit_rule_name=NULL,auto_audit_match_summary=NULL WHERE id=%s""", (user['id'], appeal['issue_id']))
            elif next_state == 'rejected':
                cur.execute("UPDATE issues SET status='待整改' WHERE id=%s", (appeal['issue_id'],))
            kind = f'appeal_{prefix}_{"approved" if approved else "rejected"}'
            record_event(cur, user, appeal['issue_id'], kind, '申诉中', new_status, reason)
            return jsonify(success=True, message=APPEAL_LABELS[kind])
        return run(operation)
