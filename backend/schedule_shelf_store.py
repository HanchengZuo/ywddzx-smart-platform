"""Durable waiting assignments and their audit trail. No HTTP or app imports."""
import json


def shelf_items(cur, mode, start, end):
    cur.execute('''SELECT id,revision,mode,scheduled_date::text AS day,inspector_ids AS ids,
      plan_team,name,source_station_name AS "sourceName",source_station_id,source_column_key,
      to_char(updated_at,'YYYY-MM-DD HH24:MI:SS') AS updated_at
      FROM inspection_schedule_shelf WHERE mode=%s AND status='waiting'
        AND scheduled_date>=%s AND scheduled_date<%s ORDER BY scheduled_date,id''', (mode,start,end))
    return [dict(row,key=f"shelf:{row['id']}") for row in cur.fetchall()]


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
