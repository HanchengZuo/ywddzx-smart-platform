CREATE TABLE IF NOT EXISTS inspection_schedule_shelf (
  id BIGSERIAL PRIMARY KEY,
  mode TEXT NOT NULL CHECK(mode IN ('offline','online')),
  scheduled_date DATE NOT NULL,
  inspector_ids JSONB NOT NULL CHECK(jsonb_typeof(inspector_ids)='array'),
  plan_team JSONB,
  name TEXT NOT NULL,
  source_station_id INTEGER REFERENCES stations(id) ON DELETE SET NULL,
  source_station_name TEXT NOT NULL,
  source_column_key TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'waiting' CHECK(status IN ('waiting','assigned','discarded')),
  revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0),
  target_station_id INTEGER REFERENCES stations(id) ON DELETE SET NULL,
  target_column_key TEXT,
  created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_schedule_shelf_waiting
  ON inspection_schedule_shelf(mode,scheduled_date,id) WHERE status='waiting';
CREATE TABLE IF NOT EXISTS inspection_schedule_shelf_events (
  id BIGSERIAL PRIMARY KEY,
  shelf_id BIGINT REFERENCES inspection_schedule_shelf(id) ON DELETE SET NULL,
  action TEXT NOT NULL,
  details JSONB NOT NULL,
  actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  actor_name TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
