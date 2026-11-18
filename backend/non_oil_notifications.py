"""Non-oil routing notices are persisted in the same transaction as the review."""
from web_push_outbox import enqueue_business

STAGE_ROLES = {'area': ('area_account', 'area_non_oil'), 'area_return': ('area_account', 'area_non_oil'),
               'department': ('non_oil',), 'field': ('supervisor', 'supervisor_manager'),
               'station': ('station_manager',)}
STAGE_LABELS = {'area': '待片区复核', 'area_return': '非油事业部驳回，待片区退回站点',
                'department': '待非油事业部终审', 'field': '待盛大现场复核', 'station': '待站点重新整改'}


def current_issue(cur, issue_id):
    cur.execute("""SELECT i.id,i.station_id,i.inspection_table_id,i.status,i.audit_status,
            i.non_oil_review_stage,i.non_oil_review_event_id,s.region AS station_region,
            s.station_name,t.table_name,t.checklist_mode,
            (SELECT max(id) FROM inspection_issue_flow_history WHERE issue_id=i.id) AS latest_event
        FROM issues i JOIN stations s ON s.id=i.station_id JOIN inspection_tables t ON t.id=i.inspection_table_id
        WHERE i.id=%s""", (issue_id,))
    return cur.fetchone()


def recipients(cur, issue, stage, policy):
    cur.execute("SELECT id,role,station_id FROM users WHERE account_status='active' AND role=ANY(%s)",
                (list(STAGE_ROLES[stage]),))
    users = cur.fetchall()
    allowed = []
    for user in users:
        if stage == 'station':
            valid = (user['station_id'] == issue['station_id']
                     and policy['can_view_rectification_queue'](cur, user)
                     and policy['has_permission'](cur, user, 'submit_my_rectification'))
        else:
            valid = (policy['can_view_review_queue'](cur, user)
                     and policy['has_permission'](cur, user, 'submit_my_issue_reviews')
                     and policy['issue_in_review_queue_scope'](cur, user, issue))
        if valid:
            allowed.append(user['id'])
    return allowed


def notify_stage(cur, issue_id, event_id, stage, policy):
    issue = current_issue(cur, issue_id)
    if not issue:
        return
    label = STAGE_LABELS[stage]
    enqueue_business(cur, event_key=f'non_oil_review:{event_id}:{stage}', source='non_oil_review',
        entity_id=issue_id, title=label,
        body=f"{issue['station_name']} · {issue['table_name']} · 问题 #{issue_id} 已流转：{label}。请查看复核意见与流转记录。",
        recipients=recipients(cur, issue, stage, policy),
        action_path='/inspection/my-rectifications' if stage == 'station' else '/inspection/my-reviews',
        push_hint=label + '，请登录查看并处理。')


def delivery_allowed(cur, message, user_id, policy):
    parts = str(message.get('event_key') or '').split(':')
    if len(parts) != 3 or parts[0] != 'non_oil_review' or not parts[1].isdigit() or parts[2] not in STAGE_ROLES:
        return False
    stage, event_id = parts[2], int(parts[1])
    issue = current_issue(cur, message['entity_id'])
    if not issue or issue['audit_status'] != 'approved':
        return False
    if stage == 'station':
        live = issue['status'] == '待整改' and issue['latest_event'] == event_id
    else:
        live = (issue['status'] == '待复核' and issue['non_oil_review_stage'] == stage
                and issue['non_oil_review_event_id'] == event_id)
    return bool(live and user_id in recipients(cur, issue, stage, policy))
