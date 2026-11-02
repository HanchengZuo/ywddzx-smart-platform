"""Availability applies to new registrations only, never historical lookups."""


def disabled_standard_ids(cur):
    cur.execute('SELECT standard_id FROM external_standard_status WHERE NOT is_active')
    result = {int(row['standard_id']) for row in cur.fetchall()}
    from checklist_versions import available
    if available(cur):
        cur.execute('''SELECT r.standard_id FROM checklist_standard_registry r JOIN inspection_tables t ON t.id=r.inspection_table_id
            WHERE r.is_deleted OR NOT t.is_active OR r.checklist_version_id IS DISTINCT FROM t.active_version_id''')
        result.update(int(row['standard_id']) for row in cur.fetchall())
    return result


def require_active_standards(cur, identifiers):
    ids = sorted({int(value) for value in identifiers})
    # Serialize availability changes with registrations, including multi-standard paths.
    for identifier in ids:
        cur.execute('SELECT pg_advisory_xact_lock(%s)', (identifier,))
    from checklist_versions import available
    if available(cur):
        cur.execute('''SELECT t.id FROM inspection_tables t WHERE t.id IN
            (SELECT inspection_table_id FROM checklist_standard_registry WHERE standard_id=ANY(%s))
            ORDER BY t.id FOR SHARE''', (ids,))
        cur.fetchall()
        blocked = disabled_standard_ids(cur).intersection(ids)
        if blocked:
            raise ValueError('外部规范或其检查表版本已停用，不能用于登记新问题：'+'、'.join(map(str,sorted(blocked))))
    cur.execute('SELECT standard_id FROM external_standard_status WHERE standard_id = ANY(%s) AND NOT is_active', (ids,))
    disabled = [str(row['standard_id']) for row in cur.fetchall()]
    if disabled:
        raise ValueError('外部规范已停用，不能用于登记新问题：' + '、'.join(disabled))
