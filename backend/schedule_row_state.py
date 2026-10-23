"""Row-level execution locks and a read-only view of today's saved dispatch."""
from inspection_schedule_catalog import COLUMNS


def linked_started_stations(cur, chosen, station_ids):
    if chosen['mode']=='online' or not station_ids:
        return set()
    # Only the same saved team/day links the two field boards. Independent plans
    # must not inherit one another's locks, nor may linked plans evade a start.
    cur.execute('''SELECT DISTINCT src.station_id
      FROM inspection_schedule_cells src JOIN inspection_schedule_cells linked
        ON linked.station_id=src.station_id AND linked.mode<>src.mode
        AND linked.mode IN ('offline','annual') AND linked.scheduled_date=src.scheduled_date
        AND linked.inspector_ids=src.inspector_ids
      JOIN stations s ON s.id=src.station_id
      JOIN inspections ins ON ins.station_id=linked.station_id
      JOIN inspection_tables t ON t.id=ins.inspection_table_id
      WHERE src.mode=%s AND src.year=%s AND src.period_number=%s
        AND src.station_id=ANY(%s) AND jsonb_array_length(src.inspector_ids)>0
        AND linked.year=EXTRACT(YEAR FROM linked.scheduled_date)::int
        AND linked.period_number=CASE WHEN linked.mode='annual' THEN 1
          ELSE EXTRACT(QUARTER FROM linked.scheduled_date)::int END
        AND t.is_active=TRUE AND (SELECT COUNT(*) FROM inspection_tables definition
          WHERE definition.table_name=t.table_name AND definition.checklist_mode=t.checklist_mode AND definition.is_active=TRUE)=1 AND (
          (linked.mode='offline' AND t.checklist_mode='offline' AND t.table_name=ANY(%s)) OR
          (linked.mode='annual' AND ((t.checklist_mode='offline' AND t.table_name=%s) OR
            (t.checklist_mode='online' AND t.table_name=%s AND s.monitoring_status='未运行'))))
        AND ins.inspection_date>=date_trunc(CASE WHEN linked.mode='annual' THEN 'year' ELSE 'quarter' END,linked.scheduled_date)
        AND ins.inspection_date<date_trunc(CASE WHEN linked.mode='annual' THEN 'year' ELSE 'quarter' END,linked.scheduled_date)
          +CASE WHEN linked.mode='annual' THEN INTERVAL '1 year' ELSE INTERVAL '3 months' END''',
      (chosen['mode'],chosen['year'],1 if chosen['mode']=='annual' else chosen['quarter'],station_ids,
       [c[2] for c in COLUMNS['offline']],COLUMNS['annual'][0][2],COLUMNS['annual'][1][2]))
    return {r['station_id'] for r in cur.fetchall()}


def today_assignments(boards, day):
    """Saved plans, including completed items; never infer dispatch from a preview."""
    grouped={}
    for board in boards:
        mode='online' if board['period']['mode']=='online' else 'offline'
        for row in board['rows']:
            for col in board['columns']:
                cell=row['cells'][col['key']]
                if cell['scheduled_date']!=day.isoformat() or not cell['assignees']:
                    continue
                ids=tuple(sorted(p['id'] for p in cell['assignees']))
                team=cell['plan_team']
                key=(mode,ids,team['leader_id'] if team else None)
                group=grouped.setdefault(key,dict(mode=mode,name=team['name'] if team else '、'.join(p['display_name'] for p in cell['assignees']),
                    people=team['members'] if team else cell['assignees'],stations={}))
                station=group['stations'].setdefault(row['station_id'],dict(station_id=row['station_id'],station_name=row['station_name'],
                    region=row['region'],locked=False,cells=[]))
                station['locked']=station['locked'] or row.get('locked',False)
                if cell.get('video_exception'):
                    station['video_exception']=cell['video_exception']
                station['cells'].append(dict(key=f"{board['period']['mode']}:{col['key']}",
                    label=('计量' if board['period']['mode']=='annual' else '')+col['label'],
                    status=cell['status'],record_count=cell['record_count']))
    result=[]
    for index,group in enumerate(grouped.values()):
        stations=list(group['stations'].values())
        cells=[c for s in stations for c in s['cells'] if c['status']!='unavailable']
        result.append(dict(group,key=str(index),stations=stations,completed=sum(c['status']=='completed' for c in cells),
                           exempted=sum(c['status']=='exception' for c in cells),total=len(cells)))
    return result
