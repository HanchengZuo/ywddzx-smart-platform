CREATE TABLE IF NOT EXISTS ai_model_settings (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    default_model TEXT NOT NULL DEFAULT 'deepseek-v4-pro',
    overrides JSONB NOT NULL DEFAULT '{}'::jsonb,
    revision INTEGER NOT NULL DEFAULT 0,
    updated_by_name TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO ai_model_settings(singleton) VALUES(TRUE) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS ai_model_setting_events (
    id BIGSERIAL PRIMARY KEY,
    actor_id INTEGER,
    actor_name TEXT NOT NULL,
    before_config JSONB NOT NULL,
    after_config JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
