ALTER TABLE inspection_schedule_cells ADD COLUMN IF NOT EXISTS scheduled_date DATE;
ALTER TABLE inspection_schedule_events ADD COLUMN IF NOT EXISTS before_date DATE;
ALTER TABLE inspection_schedule_events ADD COLUMN IF NOT EXISTS after_date DATE;

CREATE TABLE IF NOT EXISTS staff_availability (
  person_name TEXT NOT NULL, day DATE NOT NULL, available BOOLEAN NOT NULL,
  reason TEXT NOT NULL DEFAULT '' CHECK(char_length(reason)<=4),
  revision INTEGER NOT NULL CHECK(revision>0),
  updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(person_name,day)
);
CREATE TABLE IF NOT EXISTS staff_availability_events (
  id BIGSERIAL PRIMARY KEY, person_name TEXT NOT NULL, day DATE NOT NULL,
  before_value JSONB NOT NULL, after_value JSONB NOT NULL,
  actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  actor_name TEXT NOT NULL, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_staff_availability_day ON staff_availability(day,person_name);
CREATE TABLE IF NOT EXISTS inspection_schedule_tasks (
  id BIGSERIAL PRIMARY KEY, mode TEXT NOT NULL CHECK(mode IN ('offline','online')),
  year INTEGER NOT NULL, period_number INTEGER NOT NULL, column_key TEXT NOT NULL,
  station_id INTEGER REFERENCES stations(id) ON DELETE SET NULL, station_name TEXT NOT NULL,
  table_id INTEGER REFERENCES inspection_tables(id) ON DELETE SET NULL, table_name TEXT NOT NULL,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  team_ids JSONB NOT NULL CHECK(jsonb_typeof(team_ids)='array'),
  scheduled_date DATE NOT NULL, period_start DATE NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','completed','cancelled')),
  completion_inspection_id INTEGER REFERENCES inspections(id) ON DELETE SET NULL,
  completed_at TIMESTAMP, cancelled_at TIMESTAMP,
  created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_schedule_tasks_pending_cell_person
 ON inspection_schedule_tasks(mode,year,period_number,station_id,column_key,user_id) WHERE status='pending';
CREATE INDEX IF NOT EXISTS idx_schedule_tasks_inbox ON inspection_schedule_tasks(user_id,scheduled_date,id) WHERE status='pending';
CREATE INDEX IF NOT EXISTS idx_schedule_tasks_user_status ON inspection_schedule_tasks(user_id,status);
CREATE INDEX IF NOT EXISTS idx_schedule_tasks_cell ON inspection_schedule_tasks(mode,year,period_number,station_id,column_key,status);
CREATE INDEX IF NOT EXISTS idx_schedule_cells_date ON inspection_schedule_cells(scheduled_date) WHERE scheduled_date IS NOT NULL;
