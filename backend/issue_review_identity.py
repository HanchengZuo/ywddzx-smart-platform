"""Review identity comes from immutable workflow evidence, not today's account."""
from roles import is_supervisor_role

REVIEW_ACTIONS = ('review_submitted', 'non_oil_area_review_passed', 'non_oil_field_review_passed',
                 'non_oil_field_review_returned', 'non_oil_department_returned', 'non_oil_area_returned_to_station')
ROLE_REVIEW_GROUPS = (('area', '片区'), ('department', '非油事业部'), ('field', '盛大'))
ROLE_REVIEW_COLUMNS = [(f'{label}问题复核{title}', f'{group}_review_{key}')
                       for group, label in ROLE_REVIEW_GROUPS
                       for key, title in (('result', '结果'), ('note', '说明'), ('reviewer', '人员'),
                                          ('at', '时间'), ('photo', '照片'))]
ROLE_REVIEW_KEYS = {key for _, key in ROLE_REVIEW_COLUMNS}


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
          AND history.action_type = ANY(%s)
          AND history.created_at AT TIME ZONE 'Asia/Shanghai' = issue.review_at
        ORDER BY history.issue_id, history.created_at DESC, history.id DESC
    """, (sorted(set(ids)), list(REVIEW_ACTIONS)))
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


def attach_role_reviews(cur, rows, user, role_labels):
    if user.get('role') != 'non_oil' or not rows:
        return rows
    for row in rows:
        row.update({key: '' for key in ROLE_REVIEW_KEYS})
    cur.execute("""SELECT DISTINCT ON (issue_id, review_group) issue_id, result, note, photo_path,
            id AS event_id, created_at, actor_role, actor_name, actor_username, review_group,
            id > COALESCE((SELECT max(r.id) FROM inspection_issue_flow_history r
                WHERE r.issue_id=evidence.issue_id AND r.action_type='rectification_submitted'),0) AS current_round,
            TO_CHAR(created_at AT TIME ZONE 'Asia/Shanghai','YYYY-MM-DD HH24:MI') AS review_at
        FROM (SELECT *, CASE WHEN actor_role IN ('area_account','area_non_oil') THEN 'area'
              WHEN actor_role='non_oil' THEN 'department'
              WHEN actor_role IN ('supervisor','supervisor_manager') THEN 'field' END AS review_group
              FROM inspection_issue_flow_history WHERE issue_id=ANY(%s) AND action_type=ANY(%s)
              AND result IS NOT NULL) evidence
        WHERE review_group IS NOT NULL ORDER BY issue_id,review_group,created_at DESC,id DESC""",
        ([int(row['id']) for row in rows], list(REVIEW_ACTIONS)))
    by_id = {int(row['id']): row for row in rows}
    evidence_rows = cur.fetchall()
    latest = {}
    for evidence in evidence_rows:
        row = by_id[evidence['issue_id']]
        prefix = evidence['review_group'] + '_review_'
        name = evidence.get('actor_name') or evidence.get('actor_username') or '历史未记录'
        department = actor_department(evidence['actor_role'], role_labels)
        row.update({prefix + 'result': evidence['result'], prefix + 'note': evidence['note'] or '',
                    prefix + 'at': evidence['review_at'], prefix + 'photo': evidence['photo_path'] or '',
                    prefix + 'reviewer': ' · '.join(filter(None, (department, name)))})
        previous = latest.get(evidence['issue_id'])
        if evidence['current_round'] and (not previous or (evidence['created_at'],evidence['event_id']) > (previous['created_at'],previous['event_id'])):
            latest[evidence['issue_id']] = evidence
    # Old releases kept preliminary evidence only in history. Display it without
    # rewriting the database or reviving a review from a prior rectification round.
    for issue_id, evidence in latest.items():
        row = by_id[issue_id]
        if not row.get('review_at'):
            prefix = evidence['review_group'] + '_review_'
            row.update({key: row[prefix + suffix] for key,suffix in
                        (('review_result','result'),('review_note','note'),('review_at','at'),
                         ('review_photo','photo'),('reviewer','reviewer'))})
    return rows
