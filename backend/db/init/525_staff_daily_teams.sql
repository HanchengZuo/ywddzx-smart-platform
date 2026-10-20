ALTER TABLE staff_availability ADD COLUMN IF NOT EXISTS history_status TEXT
  CHECK(history_status IN ('offline','online','busy'));
CREATE TABLE IF NOT EXISTS staff_daily_teams (
  day DATE PRIMARY KEY,
  assignments JSONB NOT NULL DEFAULT '[]' CHECK(jsonb_typeof(assignments)='array'),
  revision INTEGER NOT NULL CHECK(revision>0),
  updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS staff_daily_team_events (
  id BIGSERIAL PRIMARY KEY, day DATE NOT NULL,
  before_value JSONB NOT NULL, after_value JSONB NOT NULL,
  actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  actor_name TEXT NOT NULL, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
