"""Read-only dispatch evidence and station/table coverage, independent of inspectors."""
from collections import defaultdict


def summarize_tasks(tasks):
    # Retired dispatch versions stay visible, but do not inflate the active denominator.
    active = {}
    for task in tasks:
        if task['status'] != 'cancelled':
            key = (task['station_id'], task['table_id'], task['column_key'])
            active[key] = task
    current = list(active.values())
    stations = defaultdict(list)
    modes = defaultdict(int)
    record_ids = defaultdict(set)
    names = set()
    for task in current:
        stations[(task['station_id'],task['station_name'])].append(task)
        if task['record_count']:
            modes[task['mode']] += task['record_count']
            record_ids[task['mode']].update(task.get('record_ids',[]))
        if task['plan_team']:
            names.add(task['plan_team']['name'])
    completed = sum(bool(t['record_count']) for t in current)
    exempted = sum(bool(t.get('exception_id')) and not t['record_count'] for t in current)
    return dict(total=len(current), completed=completed, exempted=exempted, resolved=completed+exempted,
                station_total=len(stations), station_completed=sum(all(t['record_count'] for t in group) for group in stations.values()),
                cancelled=sum(t['status']=='cancelled' for t in tasks),
                percent=round((completed+exempted)/len(current)*100) if current else 0,
                has_dispatch=bool(tasks), has_actual=bool(modes),
                modes=sorted({t['mode'] for t in current}), group_names=sorted(names),
                _actual_record_ids={mode:sorted(ids) for mode,ids in record_ids.items()},
                actual_modes=[dict(mode=mode,count=len(record_ids[mode]) or count) for mode,count in sorted(modes.items())])


def dispatch_history(cur, user_ids, start, end, as_of, *, details=False, defer_day=None):
    if not user_ids:
        return {}
    proof = """jsonb_agg(jsonb_build_object('id',m.id,'day',m.inspection_date::text,
      'inspector_name',COALESCE(NULLIF(TRIM(u.real_name),''),u.username,'未记录检查人'))
      ORDER BY m.inspection_date,m.id)""" if details else "'[]'::jsonb"
    cur.execute(f'''WITH selected AS MATERIALIZED (
      SELECT task.*,COALESCE(ev.actor_name,NULLIF(TRIM(actor.real_name),''),actor.username,'未记录') AS assigned_by_name
      FROM inspection_schedule_tasks task LEFT JOIN inspection_schedule_events ev ON ev.id=task.dispatch_event_id
      LEFT JOIN users actor ON actor.id=task.created_by
      WHERE task.user_id=ANY(%s) AND task.scheduled_date>=%s AND task.scheduled_date<%s
    ), keys AS MATERIALIZED (
      SELECT DISTINCT station_id,table_id,scheduled_date FROM selected
      WHERE status<>'cancelled' AND station_id IS NOT NULL AND table_id IS NOT NULL
    ), matched AS MATERIALIZED (
      SELECT k.station_id,k.table_id,k.scheduled_date,ins.id,ins.inspection_date,ins.inspector_id
      FROM keys k JOIN inspections ins ON ins.station_id=k.station_id AND ins.inspection_table_id=k.table_id
        AND ins.inspection_date>=k.scheduled_date AND ins.inspection_date<=%s
        AND (%s::date IS NULL OR k.scheduled_date<>%s OR ins.inspection_date<%s)
    ), coverage AS (
      SELECT m.station_id,m.table_id,m.scheduled_date,COUNT(*) AS record_count,
        array_agg(DISTINCT m.id) AS record_ids,
        MAX(m.inspection_date)::text AS last_inspection_date,{proof} AS records
      FROM matched m LEFT JOIN users u ON u.id=m.inspector_id
      GROUP BY m.station_id,m.table_id,m.scheduled_date
    ) SELECT task.id,task.user_id,task.mode,task.station_id,task.station_name,task.table_id,task.table_name,
      task.column_key,task.scheduled_date::text AS day,task.status,task.team_ids,task.plan_team,
      task.dispatch_event_id,task.assigned_by_name,
      waiver.id AS exception_id,waiver.reason AS exception_reason,waiver.reporter_name AS exception_reporter,
      to_char(task.created_at,'YYYY-MM-DD HH24:MI:SS') AS assigned_at,
      to_char(task.cancelled_at,'YYYY-MM-DD HH24:MI:SS') AS cancelled_at,
      CASE WHEN task.status='cancelled' THEN 0 ELSE COALESCE(c.record_count,0) END AS record_count,
      CASE WHEN task.status='cancelled' THEN '{{}}' ELSE COALESCE(c.record_ids,'{{}}') END AS record_ids,
      CASE WHEN task.status='cancelled' THEN NULL ELSE c.last_inspection_date END AS last_inspection_date,
      CASE WHEN task.status='cancelled' THEN '[]'::jsonb ELSE COALESCE(c.records,'[]'::jsonb) END AS records
    FROM selected task LEFT JOIN coverage c ON c.station_id=task.station_id AND c.table_id=task.table_id
      AND c.scheduled_date=task.scheduled_date
    LEFT JOIN inspection_schedule_video_exceptions waiver ON task.status<>'cancelled' AND task.mode='online'
      AND waiver.station_id=task.station_id AND waiver.year=task.year AND waiver.month=task.period_number
    ORDER BY task.id''', (user_ids,start,end,as_of,defer_day,defer_day,defer_day))
    result = defaultdict(list)
    for row in cur.fetchall():
        result[(row['user_id'],row['day'])].append(dict(row))
    return {key:dict(summary=summarize_tasks(tasks),tasks=[{k:v for k,v in task.items() if k!='record_ids'} for task in tasks])
            for key,tasks in result.items()}


def personal_records(cur, ids, day):
    if not ids:
        return []
    cur.execute('''SELECT ins.id,ins.inspection_date::text AS day,ins.station_id,
      COALESCE(s.station_name,'站点已删除') AS station_name,t.table_name,t.checklist_mode AS mode,
      COALESCE(NULLIF(TRIM(u.real_name),''),u.username,'未记录检查人') AS inspector_name
      FROM inspections ins JOIN inspection_tables t ON t.id=ins.inspection_table_id
      LEFT JOIN stations s ON s.id=ins.station_id LEFT JOIN users u ON u.id=ins.inspector_id
      WHERE ins.inspection_date=%s AND t.checklist_mode IN ('offline','online')
        AND (ins.inspector_id=ANY(%s) OR EXISTS(SELECT 1 FROM issues issue
          WHERE issue.inspection_id=ins.id AND issue.inspector_id=ANY(%s)))
      ORDER BY ins.inspection_date,ins.id''', (day,ids,ids))
    return [dict(row) for row in cur.fetchall()]


def cell_read_only_reason(value, day, as_of):
    if value.get('has_actual'):
        return '已有实际巡检记录，仅可查看实绩和原派工详情，不能修改档期。'
    if day < as_of:
        if value.get('available') is False:
            return '历史没空安排及原因已留存，不能修改。'
        if value.get('dispatch',{}).get('has_dispatch') or value.get('daily_assignment'):
            return '历史派工及分组已留存，完成进度按实际记录更新，不能修改原安排。'
    return ''
