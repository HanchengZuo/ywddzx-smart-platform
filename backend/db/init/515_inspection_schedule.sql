-- v9.7: a cell stores intent only; completion is always derived from inspections.
CREATE TABLE IF NOT EXISTS inspection_schedule_cells (
    mode TEXT NOT NULL CHECK (mode IN ('offline', 'online')),
    year INTEGER NOT NULL CHECK (year BETWEEN 2000 AND 2100),
    period_number INTEGER NOT NULL,
    station_id INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    column_key TEXT NOT NULL,
    inspector_ids JSONB NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(inspector_ids) = 'array'),
    revision INTEGER NOT NULL CHECK (revision > 0),
    updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (mode, year, period_number, station_id, column_key),
    CHECK ((mode = 'offline' AND period_number BETWEEN 1 AND 4) OR
           (mode = 'online' AND period_number BETWEEN 1 AND 12))
);

CREATE TABLE IF NOT EXISTS inspection_schedule_events (
    id BIGSERIAL PRIMARY KEY,
    mode TEXT NOT NULL,
    year INTEGER NOT NULL,
    period_number INTEGER NOT NULL,
    station_id INTEGER REFERENCES stations(id) ON DELETE SET NULL,
    station_name TEXT NOT NULL,
    column_key TEXT NOT NULL,
    before_ids JSONB NOT NULL,
    after_ids JSONB NOT NULL,
    actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    actor_name TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_inspection_schedule_events_cell
    ON inspection_schedule_events(mode, year, period_number, station_id, column_key, id DESC);
