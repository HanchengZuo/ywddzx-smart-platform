"""Excluded issue IDs only; never modifies the underlying inspection records."""
TABLE = 'inspection_report_equipment_issue_selections'


def available(cur):
    cur.execute('SELECT to_regclass(%s) AS name', (TABLE,))
    return bool(cur.fetchone()['name'])


def exclusions(cur, issue_ids):
    if not issue_ids or not available(cur):
        return set()
    cur.execute(f'SELECT issue_id FROM {TABLE} WHERE issue_id=ANY(%s)', (list(issue_ids),))
    return {int(row['issue_id']) for row in cur.fetchall()}


def save_exclusions(cur, eligible, excluded, actor):
    if not available(cur):
        raise ValueError('设备设施报告问题库尚未完成数据库迁移，请执行数据库升级。')
    if not isinstance(excluded, list) or any(type(value) is not int for value in excluded):
        raise ValueError('请提交有效的问题ID清单。')
    eligible, excluded = set(eligible), set(excluded)
    if not excluded.issubset(eligible):
        raise ValueError('所选问题不属于当前设备设施报告问题库。')
    cur.execute(f'DELETE FROM {TABLE} WHERE issue_id=ANY(%s)', (sorted(eligible-excluded),))
    for issue_id in sorted(excluded):
        cur.execute(f'''INSERT INTO {TABLE}(issue_id,updated_by) VALUES(%s,%s)
            ON CONFLICT(issue_id) DO UPDATE SET updated_by=EXCLUDED.updated_by,updated_at=CURRENT_TIMESTAMP''',
            (issue_id, actor))
    return excluded
