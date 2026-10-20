ALTER TABLE inspection_schedule_cells ADD COLUMN IF NOT EXISTS plan_team JSONB;
ALTER TABLE inspection_schedule_events ADD COLUMN IF NOT EXISTS before_team JSONB;
ALTER TABLE inspection_schedule_events ADD COLUMN IF NOT EXISTS after_team JSONB;
ALTER TABLE inspection_schedule_tasks ADD COLUMN IF NOT EXISTS expired_at TIMESTAMP;
ALTER TABLE inspection_schedule_tasks DROP CONSTRAINT IF EXISTS inspection_schedule_tasks_status_check;
ALTER TABLE inspection_schedule_tasks ADD CONSTRAINT inspection_schedule_tasks_status_check
  CHECK(status IN ('pending','completed','cancelled','expired'));
