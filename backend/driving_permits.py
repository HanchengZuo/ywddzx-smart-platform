"""Account-owned driving eligibility; never trust client team snapshots."""
from roles import SUPERVISOR_ROLES


def permit_value(data, role, current=False):
    if role not in SUPERVISOR_ROLES:
        return False
    value = data.get('has_driving_permit', current)
    if type(value) is not bool:
        raise ValueError('是否拥有准驾证必须选择是或否。')
    return value


def save_user_permit(cur, user_id, data):
    cur.execute('SELECT role,has_driving_permit FROM users WHERE id=%s FOR UPDATE', (user_id,))
    before = cur.fetchone()
    if not before:
        raise LookupError('用户不存在。')
    value = permit_value(data, before['role'], before['has_driving_permit'])
    if value == before['has_driving_permit']:
        return None
    cur.execute('UPDATE users SET has_driving_permit=%s WHERE id=%s', (value, user_id))
    return dict(before=before['has_driving_permit'], after=value)


def validate_driving_teams(people, assignments):
    eligible = {p['id'] for p in people if p.get('has_driving_permit') is True}
    groups = {}
    for person in assignments:
        if person['mode'] == 'offline':
            groups.setdefault(person['group_name'], set()).add(person['id'])
    missing = [name for name, ids in groups.items() if not ids & eligible]
    if missing:
        raise ValueError('、'.join(missing) + '没有持准驾证成员。每个外勤组至少需要1人拥有准驾证，请调整分工或成员。')


def require_field_driver(cur, ids):
    cur.execute('''SELECT id FROM users WHERE id=ANY(%s) AND has_driving_permit=TRUE
      AND role=ANY(%s) AND COALESCE(account_status,'active')='active' ORDER BY id FOR SHARE''',
                (list(ids), list(SUPERVISOR_ROLES)))
    ids = {row['id'] for row in cur.fetchall()}
    if not ids:
        raise ValueError('该外勤组当前没有持准驾证的启用成员，不能派现场任务，请先调整今日分组。')
    return ids
