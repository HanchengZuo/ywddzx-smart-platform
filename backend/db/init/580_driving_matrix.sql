CREATE TABLE IF NOT EXISTS driving_matrix_runs (
    id BIGSERIAL PRIMARY KEY,
    slot TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status IN ('collecting','published','failed')),
    stations JSONB NOT NULL,
    invalid_stations JSONB NOT NULL DEFAULT '[]',
    station_hash TEXT NOT NULL,
    expected_pairs INTEGER NOT NULL CHECK (expected_pairs >= 0),
    completed_pairs INTEGER NOT NULL DEFAULT 0,
    unreachable_pairs INTEGER NOT NULL DEFAULT 0,
    api_requests INTEGER NOT NULL DEFAULT 0,
    attempts INTEGER NOT NULL DEFAULT 1,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    last_error TEXT,
    policy TEXT NOT NULL DEFAULT 'amap-driving-single-direction-v1'
);
CREATE TABLE IF NOT EXISTS driving_matrix_pairs (
    run_id BIGINT NOT NULL REFERENCES driving_matrix_runs(id) ON DELETE CASCADE,
    origin_id INTEGER NOT NULL,
    destination_id INTEGER NOT NULL,
    seconds INTEGER,
    meters INTEGER,
    reachable BOOLEAN NOT NULL,
    sampled_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(run_id,origin_id,destination_id),
    CHECK (origin_id < destination_id),
    CHECK ((reachable AND seconds >= 0 AND meters >= 0 AND seconds IS NOT NULL AND meters IS NOT NULL)
        OR (NOT reachable AND seconds IS NULL AND meters IS NULL))
);
CREATE TABLE IF NOT EXISTS driving_matrix_state (
    id INTEGER PRIMARY KEY CHECK (id=1),
    active_run_id BIGINT REFERENCES driving_matrix_runs(id),
    published_at TIMESTAMPTZ
);
INSERT INTO driving_matrix_state(id) VALUES(1) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS driving_matrix_previews (
    token TEXT PRIMARY KEY,
    actor_id INTEGER NOT NULL,
    day DATE NOT NULL,
    payload JSONB NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS driving_matrix_preview_expiry ON driving_matrix_previews(expires_at);
