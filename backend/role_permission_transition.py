"""Transactional permission transition and explicitly targeted role changes.

Callers own commit/rollback. No application import, scheduler or connection is
created here; existing administrator choices are never overwritten.
"""
from security_service import record_security_event


def split_permission_templates(cur):
    cur.execute("""
        INSERT INTO role_permissions (role, permission_key, is_allowed, updated_by)
        SELECT 'supervisor_manager', permission_key, is_allowed, updated_by
        FROM role_permissions WHERE role = 'supervisor'
        ON CONFLICT DO NOTHING
    """)
    for table, value_column in (
        ('role_inspection_table_scopes', 'inspection_table_id'),
        ('role_station_region_scopes', 'station_region'),
    ):
        cur.execute(f"""
            INSERT INTO {table} (role, scope_key, {value_column}, updated_by)
            SELECT 'supervisor_manager', scope_key, {value_column}, updated_by
            FROM {table} WHERE role = 'supervisor'
            ON CONFLICT DO NOTHING
        """)
    for table, identity_column in (('role_permissions', 'role'), ('user_permissions', 'user_id')):
        cur.execute(f"""
            INSERT INTO {table} ({identity_column}, permission_key, is_allowed, updated_by)
            SELECT {identity_column}, 'view_expert_qa', is_allowed, updated_by
            FROM {table} WHERE permission_key = 'view_operations_overview'
            ON CONFLICT DO NOTHING
        """)


def promote_supervisor_managers(cur, targets, actor, *, apply=False):
    """Validate every id/name before changing any role; row locks serialize edits."""
    if not actor or actor.get('role') != 'root':
        raise PermissionError('仅 root 可执行督导组角色调整。')
    targets = dict(targets)
    if not targets:
        raise ValueError('请明确指定要调整的账号。')
    cur.execute('SELECT id, username, role FROM users WHERE id = ANY(%s) ORDER BY id FOR UPDATE', (list(targets),))
    rows = [dict(row) for row in cur.fetchall()]
    if len(rows) != len(targets) or any(
        targets.get(row['id']) != row['username'] or row['role'] not in ('supervisor', 'supervisor_manager')
        for row in rows
    ):
        raise ValueError('账号 ID、用户名或原角色不一致，未修改任何账号。')
    if apply:
        for row in rows:
            if row['role'] == 'supervisor_manager':
                continue
            cur.execute("""UPDATE users SET role = 'supervisor_manager',
                auth_version = COALESCE(auth_version, 1) + 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s""", (row['id'],))
            record_security_event(cur, actor, 'supervisor_role_split', 'success', target=row,
                                  details={'previous_role': row['role'], 'new_role': 'supervisor_manager'})
    return rows
