"""Shared per-group/person daily station targets; no dispatch limits or startup work."""
import json
from schedule_common import ScheduleConflict


def read_quotas(cur):
    cur.execute('''SELECT q.offline_count,q.online_count,q.revision,
      COALESCE(NULLIF(TRIM(u.real_name),''),u.username,'系统默认') AS updated_by_name,
      to_char(q.updated_at,'YYYY-MM-DD HH24:MI:SS') AS updated_at
      FROM inspection_schedule_quotas q LEFT JOIN users u ON u.id=q.updated_by WHERE q.id=1''')
    return dict(cur.fetchone())


def save_quotas(cur,actor,data):
    before=read_quotas(cur)
    values={key:data.get(key) for key in ('offline_count','online_count')}
    if any(type(n) is not int or not 1<=n<=10 for n in values.values()):
        raise ValueError('每组或每人的站点数量请设置为1至10。')
    if type(data.get('quota_revision')) is not int or data['quota_revision']!=before['revision']:
        raise ScheduleConflict('站数配置已被其他用户修改，请重新打开智能排班后调整。')
    if all(values[key]==before[key] for key in values): return before
    cur.execute('''UPDATE inspection_schedule_quotas SET offline_count=%s,online_count=%s,
      revision=revision+1,updated_by=%s,updated_at=CURRENT_TIMESTAMP WHERE id=1''',
      (values['offline_count'],values['online_count'],actor['id']))
    cur.execute('''INSERT INTO inspection_schedule_quota_events(before_value,after_value,actor_id,actor_name)
      VALUES(%s,%s,%s,%s)''',(json.dumps(before),json.dumps(values),actor['id'],
        actor.get('real_name') or actor.get('username') or str(actor['id'])))
    return read_quotas(cur)
