"""Sparse personal overrides. Callers own authentication and transactions."""
from security_service import record_security_event


def merge_personal_permissions(base, overrides, exclusive_groups, normalize, role):
    merged = {key: overrides.get(key, value) for key, value in base.items()}
    # An explicit personal choice wins over an inherited, mutually exclusive one.
    for group in exclusive_groups:
        chosen = [key for key in group if overrides.get(key) is True and merged.get(key)]
        if chosen:
            for key in group:
                merged[key] = key == chosen[0]
    return normalize(merged, role)


def replace_personal_permissions(cur, target, overrides, actor, valid_keys, exclusive_groups):
    if not actor or actor.get('role') != 'root':
        raise PermissionError('仅 root 系统管理员可配置用户权限。')
    if not isinstance(overrides, dict):
        raise ValueError('个人权限配置格式不正确。')
    if any(key not in valid_keys or not isinstance(value, bool) for key, value in overrides.items()):
        raise ValueError('个人权限包含无效开关。')
    if target.get('role') == 'root' and overrides:
        raise ValueError('root 固定拥有全部权限，不需要个人配置。')
    if any(sum(overrides.get(key) is True for key in group) > 1 for group in exclusive_groups):
        raise ValueError('同一页面的数据范围只能单独开启一种。')
    cur.execute('DELETE FROM user_permissions WHERE user_id = %s', (target['id'],))
    for key, value in overrides.items():
        cur.execute('''INSERT INTO user_permissions (user_id, permission_key, is_allowed, updated_by)
                       VALUES (%s, %s, %s, %s)''', (target['id'], key, value, actor['id']))


def clear_personal_permissions(cur, actor, *, apply=False):
    """Keep area ownership and bound station identities, never alter role templates."""
    if not actor or actor.get('role') != 'root':
        raise PermissionError('仅 root 可清空个人权限覆盖。')
    cur.execute('LOCK TABLE users, user_permissions, user_inspection_table_scopes, user_station_region_scopes IN SHARE ROW EXCLUSIVE MODE')
    cur.execute('''SELECT u.id, u.username, u.role,
        (SELECT count(*) FROM user_permissions p WHERE p.user_id=u.id) AS switches,
        (SELECT count(*) FROM user_inspection_table_scopes s WHERE s.user_id=u.id) AS tables,
        (SELECT count(*) FROM user_station_region_scopes s WHERE s.user_id=u.id) AS regions
        FROM users u ORDER BY u.id FOR UPDATE OF u''')
    rows = [dict(row) for row in cur.fetchall()]
    affected = [row for row in rows if row['switches'] or row['tables'] or (row['regions'] and row['role'] != 'area_account')]
    if apply:
        cur.execute('DELETE FROM user_permissions')
        cur.execute('DELETE FROM user_inspection_table_scopes')
        cur.execute("DELETE FROM user_station_region_scopes s USING users u WHERE s.user_id=u.id AND u.role <> 'area_account'")
        for row in affected:
            cur.execute('''UPDATE users SET auth_version=COALESCE(auth_version,1)+1,
                           updated_at=CURRENT_TIMESTAMP WHERE id=%s''', (row['id'],))
            record_security_event(cur, actor, 'personal_permissions_cleared', 'success', target=row,
                                  details={'switches_removed': row['switches'], 'table_scopes_removed': row['tables'],
                                           'region_scopes_removed': 0 if row['role'] == 'area_account' else row['regions'],
                                           'area_ownership_preserved': row['role'] == 'area_account'})
    return {'accounts': len(rows), 'affected_accounts': len(affected),
            'switches': sum(row['switches'] for row in rows), 'table_scopes': sum(row['tables'] for row in rows),
            'region_scopes': sum(row['regions'] for row in rows if row['role'] != 'area_account'),
            'area_bindings_preserved': sum(row['regions'] for row in rows if row['role'] == 'area_account')}
