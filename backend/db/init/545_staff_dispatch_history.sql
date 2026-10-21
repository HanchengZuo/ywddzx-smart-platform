-- Preserve each dispatch version rather than rewriting the membership of old tasks.
ALTER TABLE inspection_schedule_tasks ADD COLUMN IF NOT EXISTS plan_team JSONB;
ALTER TABLE inspection_schedule_tasks ADD COLUMN IF NOT EXISTS dispatch_event_id BIGINT
  REFERENCES inspection_schedule_events(id) ON DELETE SET NULL;

-- Recover the original snapshot from evidence already stored with the dispatch.
WITH original AS (
  SELECT task.id,e.id AS event_id,e.after_team,e.after_ids
  FROM inspection_schedule_tasks task
  JOIN LATERAL (
    SELECT ev.id,ev.after_team,ev.after_ids FROM inspection_schedule_events ev
    WHERE ev.mode=task.mode AND ev.year=task.year AND ev.period_number=task.period_number
      AND ev.station_id=task.station_id AND ev.column_key=task.column_key
      AND ev.after_date=task.scheduled_date
      AND ev.after_ids @> jsonb_build_array(task.user_id)
      AND ev.created_at<=task.created_at
    ORDER BY ev.id DESC LIMIT 1
  ) e ON TRUE WHERE task.dispatch_event_id IS NULL
)
UPDATE inspection_schedule_tasks task SET dispatch_event_id=original.event_id,
  plan_team=original.after_team,team_ids=original.after_ids
FROM original WHERE task.id=original.id;

CREATE INDEX IF NOT EXISTS idx_schedule_tasks_day_person
  ON inspection_schedule_tasks(scheduled_date,user_id,id);
CREATE INDEX IF NOT EXISTS idx_inspections_dispatch_progress
  ON inspections(station_id,inspection_table_id,inspection_date);
