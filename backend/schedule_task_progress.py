"""Self-only inbox coverage, matching the matrix's [period_start, period_end) records."""
import math


def coverage_end_sql(alias):
    return f"""({alias}.period_start + CASE
      WHEN {alias}.column_key IN ('metering_site','metering_video') THEN INTERVAL '1 year'
      WHEN {alias}.mode='offline' THEN INTERVAL '3 months' ELSE INTERVAL '1 month' END)"""


PROGRESS_SQL = f"""WITH candidates AS MATERIALIZED (
  SELECT task.*, {coverage_end_sql('task')}::date AS coverage_end
  FROM inspection_schedule_tasks task
  WHERE task.user_id=%s AND task.scheduled_date<=%s
    AND task.station_id IS NOT NULL AND task.table_id IS NOT NULL
    AND (task.status IN ('pending','completed') OR (task.status='expired' AND task.mode='offline'
      AND EXISTS(SELECT 1 FROM inspection_schedule_cells c WHERE c.year=task.year
        AND c.mode=CASE WHEN task.column_key IN ('metering_site','metering_video') THEN 'annual' ELSE task.mode END
        AND c.period_number=task.period_number AND c.station_id=task.station_id
        AND c.column_key=task.column_key AND c.scheduled_date=task.scheduled_date
        AND c.inspector_ids @> jsonb_build_array(task.user_id)
        AND c.inspector_ids @> task.team_ids AND c.inspector_ids <@ task.team_ids)))
    AND NOT EXISTS(SELECT 1 FROM inspection_schedule_tasks newer
      WHERE newer.user_id=task.user_id AND newer.mode=task.mode AND newer.year=task.year
        AND newer.period_number=task.period_number AND newer.station_id=task.station_id
        AND newer.column_key=task.column_key AND newer.id>task.id
        AND newer.status IN ('pending','completed'))
), progress AS MATERIALIZED (
  SELECT task.*, matches.record_count,matches.inspection_id,matches.inspection_date,
    CASE WHEN matches.record_count>0 THEN 'completed' ELSE 'pending' END AS effective_status,
    CASE WHEN task.scheduled_date=%s THEN 'today_' ELSE 'history_' END || task.mode AS bucket,
    MAX(CASE WHEN matches.record_count=0 THEN 1 ELSE 0 END)
      OVER(PARTITION BY task.scheduled_date,task.mode,task.station_id) AS group_pending
  FROM candidates task
  LEFT JOIN LATERAL (
    SELECT COUNT(*)::int AS record_count,(array_agg(ins.id ORDER BY ins.inspection_date DESC,ins.id DESC))[1] AS inspection_id,
      MAX(ins.inspection_date) AS inspection_date
    FROM inspections ins WHERE ins.station_id=task.station_id AND ins.inspection_table_id=task.table_id
      AND ins.inspection_date>=task.period_start AND ins.inspection_date<task.coverage_end
      AND EXISTS(SELECT 1 FROM inspection_tables definition WHERE definition.id=task.table_id AND definition.is_active=TRUE
        AND definition.table_name=task.table_name
        AND definition.checklist_mode=CASE WHEN task.column_key='metering_video' THEN 'online' ELSE task.mode END
        AND 1=(SELECT COUNT(*) FROM inspection_tables other WHERE other.table_name=definition.table_name
          AND other.checklist_mode=definition.checklist_mode AND other.is_active=TRUE))
  ) matches ON TRUE
), visible AS MATERIALIZED (
  SELECT * FROM progress WHERE scheduled_date=%s OR group_pending=1
) """

BUCKETS=('today_offline','today_online','history_offline','history_online')


def params(user_id,day):
    return (user_id,day,day,day)


def inbox_summary(cur,user_id,day):
    cur.execute(PROGRESS_SQL+'''SELECT bucket,COUNT(*)::int AS total,
      COUNT(*) FILTER(WHERE effective_status='pending')::int AS pending,
      COUNT(*) FILTER(WHERE effective_status='completed')::int AS completed,
      COUNT(DISTINCT (scheduled_date,station_id))::int AS stations
      FROM visible GROUP BY bucket''',params(user_id,day))
    buckets={key:dict(total=0,pending=0,completed=0,stations=0) for key in BUCKETS}
    for row in cur.fetchall():
        buckets[row['bucket']]={key:row[key] for key in ('total','pending','completed','stations')}
    return dict(buckets=buckets,count=sum(r['pending'] for r in buckets.values()))


def inbox_page(cur,user_id,day,bucket,page,page_size):
    summary=inbox_summary(cur,user_id,day)
    total_groups=sum(r['stations'] for key,r in summary['buckets'].items() if bucket=='all' or key==bucket)
    page=min(page,max(1,math.ceil(total_groups/page_size)))
    cur.execute(PROGRESS_SQL+''' , selected_groups AS (
      SELECT scheduled_date,mode,station_id FROM visible WHERE (%s='all' OR bucket=%s)
      GROUP BY scheduled_date,mode,station_id
      ORDER BY (scheduled_date=%s) DESC,scheduled_date,mode,station_id LIMIT %s OFFSET %s
    ) SELECT p.id,p.mode,p.station_id,p.station_name,p.table_id,p.table_name,p.column_key,p.plan_team,
      p.scheduled_date::text,p.effective_status AS status,p.record_count,
      p.inspection_id AS completion_inspection_id,p.inspection_date::text AS last_inspection_date,
      p.period_start::text AS coverage_from,(p.coverage_end-1)::text AS coverage_to,p.bucket
      FROM visible p JOIN selected_groups g USING(scheduled_date,mode,station_id)
      ORDER BY (p.scheduled_date=%s) DESC,p.scheduled_date,p.mode,p.station_id,p.id''',
      (*params(user_id,day),bucket,bucket,day,page_size,(page-1)*page_size,day))
    return dict(**summary,tasks=[dict(r) for r in cur.fetchall()],page=page,page_size=page_size,
                total_groups=total_groups,has_more=page*page_size<total_groups)
