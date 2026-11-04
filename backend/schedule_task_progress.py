"""Shared inbox coverage, matching the matrix's [period_start, period_end) records."""
import math
from schedule_completion import completed_record_sql, task_checklist_mode_sql


def coverage_end_sql(alias):
    return f"""({alias}.period_start + CASE
      WHEN {alias}.column_key IN ('metering_site','metering_video') THEN INTERVAL '1 year'
      WHEN {alias}.mode='offline' THEN INTERVAL '3 months' ELSE INTERVAL '1 month' END)"""


def progress_sql(*, all_people=False):
    owner_filter = 'TRUE' if all_people else 'task.user_id=%s'
    mode = task_checklist_mode_sql()
    return f"""WITH candidates AS MATERIALIZED (
  SELECT task.*, {coverage_end_sql('task')}::date AS coverage_end
  FROM inspection_schedule_tasks task
  WHERE {owner_filter} AND task.scheduled_date<=%s
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
  SELECT task.*, matches.record_count,matches.unconfirmed_count,matches.inspection_id,matches.inspection_date,
    waiver.id AS exception_id,waiver.reason AS exception_reason,waiver.reporter_name AS exception_reporter,
    to_char(waiver.created_at AT TIME ZONE 'Asia/Shanghai','YYYY-MM-DD HH24:MI:SS') AS exception_reported_at,
    CASE WHEN waiver.id IS NOT NULL THEN 'exception' WHEN matches.record_count>0 THEN 'completed' ELSE 'pending' END AS effective_status,
    CASE WHEN task.scheduled_date=%s THEN 'today_' ELSE 'history_' END || task.mode AS bucket,
    MAX(CASE WHEN matches.record_count=0 AND waiver.id IS NULL THEN 1 ELSE 0 END)
      OVER(PARTITION BY task.user_id,task.scheduled_date,task.mode,task.station_id) AS group_pending
  FROM candidates task
  LEFT JOIN inspection_schedule_video_exceptions waiver ON task.mode='online'
    AND waiver.year=task.year AND waiver.month=task.period_number AND waiver.station_id=task.station_id
  LEFT JOIN LATERAL (
    SELECT COUNT(*) FILTER(WHERE completed)::int AS record_count,
      COUNT(*) FILTER(WHERE NOT completed)::int AS unconfirmed_count,
      (array_agg(id ORDER BY inspection_date DESC,id DESC) FILTER(WHERE completed))[1] AS inspection_id,
      MAX(inspection_date) FILTER(WHERE completed) AS inspection_date
    FROM (SELECT ins.id,ins.inspection_date,({completed_record_sql(mode)}) IS TRUE AS completed
    FROM inspections ins WHERE ins.station_id=task.station_id AND ins.inspection_table_id=task.table_id
      AND ins.inspection_date>=task.period_start AND ins.inspection_date<task.coverage_end
      AND EXISTS(SELECT 1 FROM inspection_tables definition WHERE definition.id=task.table_id AND definition.is_active=TRUE
        AND definition.table_name=task.table_name
        AND definition.checklist_mode={mode}
        AND 1=(SELECT COUNT(*) FROM inspection_tables other WHERE other.table_name=definition.table_name
          AND other.checklist_mode=definition.checklist_mode AND other.is_active=TRUE))) evidence
  ) matches ON TRUE
), visible AS MATERIALIZED (
  SELECT * FROM progress WHERE scheduled_date=%s OR group_pending=1
) """

PROGRESS_SQL = progress_sql()
ALL_PEOPLE_PROGRESS_SQL = progress_sql(all_people=True)
BUCKETS=('today_offline','today_online','history_offline','history_online')

SUMMARY_COLUMNS = """COUNT(*)::int AS total,
  COUNT(*) FILTER(WHERE effective_status='pending')::int AS pending,
  COUNT(*) FILTER(WHERE effective_status='completed')::int AS completed,
  COUNT(*) FILTER(WHERE effective_status='exception')::int AS exempted,
  COUNT(DISTINCT (scheduled_date,station_id))::int AS stations"""


def params(user_id,day):
    return (user_id,day,day,day)


def inbox_summary(cur,user_id,day):
    cur.execute(PROGRESS_SQL+f'SELECT bucket,{SUMMARY_COLUMNS} FROM visible GROUP BY bucket',
                params(user_id,day))
    buckets={key:dict(total=0,pending=0,completed=0,stations=0) for key in BUCKETS}
    exception_counts={key:0 for key in BUCKETS}
    for row in cur.fetchall():
        buckets[row['bucket']]={key:row[key] for key in ('total','pending','completed','stations')}
        exception_counts[row['bucket']]=row['exempted']
    return dict(buckets=buckets,exception_counts=exception_counts,count=sum(r['pending'] for r in buckets.values()))


def inbox_page(cur,user_id,day,bucket,page,page_size):
    summary=inbox_summary(cur,user_id,day)
    total_groups=sum(r['stations'] for key,r in summary['buckets'].items() if bucket=='all' or key==bucket)
    page=min(page,max(1,math.ceil(total_groups/page_size)))
    cur.execute(PROGRESS_SQL+''' , selected_groups AS (
      SELECT scheduled_date,mode,station_id FROM visible WHERE (%s='all' OR bucket=%s)
      GROUP BY scheduled_date,mode,station_id
      ORDER BY (scheduled_date=%s) DESC,scheduled_date,mode,station_id LIMIT %s OFFSET %s
    ) SELECT p.id,p.mode,p.station_id,p.station_name,p.table_id,p.table_name,p.column_key,p.plan_team,
      p.scheduled_date::text,p.effective_status AS status,p.record_count,p.unconfirmed_count,
      p.exception_id,p.exception_reason,p.exception_reporter,p.exception_reported_at,
      p.inspection_id AS completion_inspection_id,p.inspection_date::text AS last_inspection_date,
      p.period_start::text AS coverage_from,(p.coverage_end-1)::text AS coverage_to,p.bucket
      FROM visible p JOIN selected_groups g USING(scheduled_date,mode,station_id)
      ORDER BY (p.scheduled_date=%s) DESC,p.scheduled_date,p.mode,p.station_id,p.id''',
      (*params(user_id,day),bucket,bucket,day,page_size,(page-1)*page_size,day))
    return dict(**summary,tasks=[dict(r) for r in cur.fetchall()],page=page,page_size=page_size,
                total_groups=total_groups,has_more=page*page_size<total_groups)
