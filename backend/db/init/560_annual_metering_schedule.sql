-- Annual metering intent shares the existing transaction/audit machinery, not monthly video tasks.
ALTER TABLE inspection_schedule_cells DROP CONSTRAINT IF EXISTS inspection_schedule_cells_mode_check;
ALTER TABLE inspection_schedule_cells ADD CONSTRAINT inspection_schedule_cells_mode_check
  CHECK(mode IN ('offline','online','annual'));
ALTER TABLE inspection_schedule_cells DROP CONSTRAINT IF EXISTS inspection_schedule_cells_check;
ALTER TABLE inspection_schedule_cells DROP CONSTRAINT IF EXISTS inspection_schedule_cells_period_check;
ALTER TABLE inspection_schedule_cells ADD CONSTRAINT inspection_schedule_cells_period_check CHECK(
  (mode='offline' AND period_number BETWEEN 1 AND 4) OR
  (mode='online' AND period_number BETWEEN 1 AND 12) OR
  (mode='annual' AND period_number=1));

CREATE TABLE IF NOT EXISTS annual_metering_plans (
  year INTEGER PRIMARY KEY CHECK(year BETWEEN 2000 AND 2100),
  quotas JSONB NOT NULL DEFAULT '{}' CHECK(jsonb_typeof(quotas)='object'),
  revision INTEGER NOT NULL CHECK(revision>0),
  updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS annual_metering_plan_events (
  id BIGSERIAL PRIMARY KEY, year INTEGER NOT NULL,
  before_quotas JSONB NOT NULL, after_quotas JSONB NOT NULL,
  actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  actor_name TEXT NOT NULL, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
