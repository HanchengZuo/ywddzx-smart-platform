"""Review identity comes from immutable workflow evidence, not today's account."""
from roles import is_supervisor_role


def actor_department(actor_role, role_labels):
    if is_supervisor_role(actor_role):
        return '督导中心'
    return role_labels.get(actor_role, '').removesuffix('账号')


def attach_reviewers(cur, rows, role_labels):
    ids = []
    for row in rows:
        row.update(reviewer='', reviewer_name='', reviewer_department='', reviewer_user_id=None)
        if any(row.get(key) for key in ('review_at','review_result','review_note','review_photo')):
            row['reviewer'] = '历史未记录'
        if row.get('review_at'):
            ids.append(int(row['id']))
    if not ids:
        return rows
    # Exact transaction time ties the actor to this round, not a previous review
    # or a later administrative edit. Missing historical identities stay unknown.
    cur.execute("""
        SELECT DISTINCT ON (history.issue_id)
            history.issue_id, history.actor_user_id, history.actor_username,
            history.actor_name, history.actor_role
        FROM inspection_issue_flow_history AS history
        JOIN issues AS issue ON issue.id = history.issue_id
        WHERE issue.id = ANY(%s) AND issue.review_at IS NOT NULL
          AND history.action_type = 'review_submitted'
          AND history.created_at AT TIME ZONE 'Asia/Shanghai' = issue.review_at
        ORDER BY history.issue_id, history.created_at DESC, history.id DESC
    """, (sorted(set(ids)),))
    identities = {row['issue_id']: row for row in cur.fetchall()}
    for row in rows:
        identity = identities.get(row['id']) if row.get('review_at') else None
        if not identity:
            continue
        name = str(identity.get('actor_name') or '').strip() or str(identity.get('actor_username') or '').strip()
        department = actor_department(identity.get('actor_role'), role_labels)
        row.update(reviewer_name=name, reviewer_department=department,
                   reviewer_user_id=identity.get('actor_user_id'))
        if name:
            row['reviewer'] = ' · '.join(part for part in (department, name) if part)
    return rows
