-- Station-level monthly video waivers. Dispatch and actual inspection records stay intact.
CREATE TABLE IF NOT EXISTS inspection_schedule_video_exceptions (
    id BIGSERIAL PRIMARY KEY,
    year INTEGER NOT NULL CHECK (year BETWEEN 2000 AND 2100),
    month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    station_id INTEGER REFERENCES stations(id) ON DELETE SET NULL,
    station_name TEXT NOT NULL,
    scheduled_date DATE NOT NULL,
    reported_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    reporter_name TEXT NOT NULL,
    reason TEXT NOT NULL CHECK (char_length(btrim(reason)) BETWEEN 1 AND 500),
    source_task_id BIGINT REFERENCES inspection_schedule_tasks(id) ON DELETE SET NULL,
    task_ids JSONB NOT NULL,
    dispatch_snapshot JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (year, month, station_id)
);
