"""Durable waiting assignments and their audit trail. No HTTP or app imports."""
import json
from schedule_common import today
from inspection_schedule_catalog import roster_position
from schedule_quotas import read_quotas


def shelf_items(cur, mode, start, end, *, quotas=None):
    start = max(start, today())
    if start >= end:
        return []
    cur.execute('''SELECT id,revision,mode,scheduled_date::text AS day,inspector_ids AS ids,
      plan_team,name,source_station_name AS "sourceName",source_station_id,source_column_key,
      to_char(updated_at,'YYYY-MM-DD HH24:MI:SS') AS updated_at
      FROM inspection_schedule_shelf WHERE mode=%s AND status='waiting'
        AND scheduled_date>=%s AND scheduled_date<%s ORDER BY scheduled_date,id''', (mode,start,end))
    cards=list(cur.fetchall())
    if not cards: return []
    quotas=quotas or read_quotas(cur)
    # Quarterly and annual field plans share station capacity; count a station
    # once even when all six/nine checklist cells contain the same assignment.
    cur.execute('''SELECT c.mode,c.station_id,c.inspector_ids,c.scheduled_date::text AS day,s.region,s.station_name
      FROM inspection_schedule_cells c JOIN stations s ON s.id=c.station_id
      WHERE c.scheduled_date>=%s AND c.scheduled_date<%s
        AND c.year=EXTRACT(YEAR FROM c.scheduled_date) AND jsonb_array_length(c.inspector_ids)>0
        AND ((%s='online' AND c.mode='online' AND c.period_number=EXTRACT(MONTH FROM c.scheduled_date) AND s.include_online_plan)
          OR (%s='offline' AND c.mode IN ('offline','annual') AND s.include_offline_plan
            AND c.period_number=CASE WHEN c.mode='annual' THEN 1 ELSE EXTRACT(QUARTER FROM c.scheduled_date) END))''',
      (start,end,mode,mode))
    used={}
    for row in cur.fetchall():
        if not roster_position(row,row['mode']): continue
        key=(row['day'],tuple(sorted(row['inspector_ids'])))
        used.setdefault(key,set()).add(row['station_id'])
    unique={}
    for row in cards:
        key=(row['day'],tuple(sorted(row['ids'])))
        # Prefer an explicit parked record; the reusable personnel card remains
        # durable underneath. Source evidence stays in storage, never on the UI.
        if key not in unique or (unique[key]['source_column_key']=='personnel' and row['source_column_key']!='personnel'):
            unique[key]=row
    target=quotas['offline_count' if mode=='offline' else 'online_count']
    return [dict(row,key=f"shelf:{row['id']}",target=target,assigned=len(used.get(ids,set())),
                 remaining=target-len(used.get(ids,set()))) for ids,row in unique.items()
            if len(used.get(ids,set())) < target]


def expire_shelf(cur, *, already_locked=False):
    """Lazy daily cleanup; reads never wait behind an ongoing dispatch."""
    if not already_locked:
        cur.execute('SELECT pg_try_advisory_xact_lock(9801,1) AS acquired')
        if not cur.fetchone()['acquired']:
            return
    cur.execute('''UPDATE inspection_schedule_shelf SET status='discarded',revision=revision+1,
      updated_by=NULL,updated_at=CURRENT_TIMESTAMP WHERE status='waiting' AND scheduled_date<%s
      RETURNING id,scheduled_date,name''', (today(),))
    for row in cur.fetchall():
        event(cur, dict(id=None, real_name='系统自动清理'), row['id'], 'expired',
              dict(day=row['scheduled_date'].isoformat(), name=row['name'], reason='过期待选安排自动清理，未来安排保留'))


def event(cur, actor, shelf_id, action, details):
    cur.execute('''INSERT INTO inspection_schedule_shelf_events(shelf_id,action,details,actor_id,actor_name)
      VALUES(%s,%s,%s,%s,%s)''', (shelf_id,action,json.dumps(details,ensure_ascii=False),actor['id'],
          actor.get('real_name') or actor.get('username') or str(actor['id'])))


def park_item(cur, actor, mode, row, column_key, cells, action='parked'):
    """The server builds a card from the saved plan, never from submitted member IDs."""
    first=cells[0]
    ids=[p['id'] for p in first['assignees']]
    team=first['plan_team']
    name=team['name'] if team else '、'.join(p['display_name'] for p in first['assignees'])
    cur.execute('''INSERT INTO inspection_schedule_shelf(mode,scheduled_date,inspector_ids,plan_team,name,
      source_station_id,source_station_name,source_column_key,created_by,updated_by)
      VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
      (mode,first['scheduled_date'],json.dumps(ids),json.dumps(team,ensure_ascii=False),name,
       row['station_id'],row['station_name'],column_key,actor['id'],actor['id']))
    sid=cur.fetchone()['id']
    event(cur,actor,sid,action,dict(name=name,inspector_ids=ids,day=first['scheduled_date'],
          station_id=row['station_id'],station_name=row['station_name'],column_key=column_key,plan_team=team))
    return sid


def refresh_field_shelf(cur,actor,day,groups,team_revision):
    cur.execute("SELECT * FROM inspection_schedule_shelf WHERE mode='offline' AND scheduled_date=%s AND status='waiting' AND jsonb_typeof(plan_team)='object' FOR UPDATE",(day,))
    for saved in cur.fetchall():
        group=groups.get(saved['plan_team']['leader_id'])
        if not group: continue
        ids=sorted(p['id'] for p in group['members'])
        if ids==sorted(saved['inspector_ids']): continue
        team=dict(name=group['name'],leader_id=group['leader_id'],day=day.isoformat(),revision=team_revision,members=group['members'])
        cur.execute('''UPDATE inspection_schedule_shelf SET inspector_ids=%s,plan_team=%s,name=%s,
          revision=revision+1,updated_by=%s,updated_at=CURRENT_TIMESTAMP WHERE id=%s''',
          (json.dumps(ids),json.dumps(team,ensure_ascii=False),group['name'],actor['id'],saved['id']))
        event(cur,actor,saved['id'],'team_updated',dict(before_ids=saved['inspector_ids'],after_ids=ids))


def seed_daily_shelf(cur, actor, day, groups, revision):
    """Explicit grouping confirmation publishes reusable manual-dispatch cards, once per group."""
    valid = {('offline', tuple(sorted(p['id'] for p in g['members']))) for g in groups if g['mode']=='offline'}
    valid.update(('online', (p['id'],)) for g in groups if g['mode']=='online' for p in g['members'])
    cur.execute("SELECT id,mode,inspector_ids,source_column_key FROM inspection_schedule_shelf WHERE scheduled_date=%s AND status='waiting' FOR UPDATE",(day,))
    # Parked old groups must not survive dissolution and reappear beside the
    # replacement personnel cards. Keep their audit trail, retire only intent.
    old=[r['id'] for r in cur.fetchall() if r['source_column_key']=='personnel'
         or (r['mode'],tuple(sorted(r['inspector_ids']))) not in valid]
    if old:
        cur.execute("UPDATE inspection_schedule_shelf SET status='discarded',revision=revision+1,updated_by=%s WHERE id=ANY(%s)",(actor['id'],old))
        for sid in old: event(cur,actor,sid,'personnel_refreshed',dict(day=day.isoformat()))
    for group in groups:
        members = [group['members']] if group['mode']=='offline' else [[p] for p in group['members']]
        for people in members:
            ids=sorted(p['id'] for p in people)
            team=dict(name=group['name'],leader_id=group['leader_id'],members=people,day=day.isoformat(),revision=revision) if group['mode']=='offline' else None
            name=team['name'] if team else people[0]['display_name']
            cur.execute('''INSERT INTO inspection_schedule_shelf(mode,scheduled_date,inspector_ids,plan_team,name,
              source_station_name,source_column_key,created_by,updated_by) VALUES(%s,%s,%s,%s,%s,'人员分组','personnel',%s,%s) RETURNING id''',
              (group['mode'],day,json.dumps(ids),json.dumps(team,ensure_ascii=False),name,actor['id'],actor['id']))
            event(cur,actor,cur.fetchone()['id'],'personnel_ready',dict(inspector_ids=ids,day=day.isoformat(),name=name))
