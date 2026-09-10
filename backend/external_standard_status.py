"""Availability applies to new registrations only, never historical lookups."""


def disabled_standard_ids(cur):
    cur.execute('SELECT standard_id FROM external_standard_status WHERE NOT is_active')
    return {int(row['standard_id']) for row in cur.fetchall()}


def require_active_standards(cur, identifiers):
    ids = sorted({int(value) for value in identifiers})
    # Serialize availability changes with registrations, including multi-standard paths.
    for identifier in ids:
        cur.execute('SELECT pg_advisory_xact_lock(%s)', (identifier,))
    cur.execute('SELECT standard_id FROM external_standard_status WHERE standard_id = ANY(%s) AND NOT is_active', (ids,))
    disabled = [str(row['standard_id']) for row in cur.fetchall()]
    if disabled:
        raise ValueError('外部规范已停用，不能用于登记新问题：' + '、'.join(disabled))
