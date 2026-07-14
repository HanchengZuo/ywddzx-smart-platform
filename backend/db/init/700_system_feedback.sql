-- system_feedbacks 表：系统反馈主表
-- 用途：
-- 1. 保存所有用户公开提交的系统反馈
-- 2. 按反馈类型、问题模块、标题和详细说明组织内容
-- 3. 保存提交人快照，避免用户资料后续变动影响历史反馈展示

CREATE TABLE IF NOT EXISTS system_feedbacks (
    id SERIAL PRIMARY KEY,
    feedback_type TEXT NOT NULL,
    module TEXT NOT NULL,
    title TEXT NOT NULL,
    title_ai_generated BOOLEAN NOT NULL DEFAULT FALSE,
    description TEXT NOT NULL,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    author_name TEXT,
    author_phone TEXT,
    author_role TEXT,
    accepted_at TIMESTAMP,
    accepted_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS system_feedback_screenshots (
    id SERIAL PRIMARY KEY,
    feedback_id INTEGER NOT NULL REFERENCES system_feedbacks(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS system_feedback_comments (
    id SERIAL PRIMARY KEY,
    feedback_id INTEGER NOT NULL REFERENCES system_feedbacks(id) ON DELETE CASCADE,
    comment_text TEXT NOT NULL,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    author_name TEXT,
    author_phone TEXT,
    author_role TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS system_feedback_read_states (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    last_read_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_system_feedbacks_created_at
    ON system_feedbacks(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_system_feedbacks_accepted_at
    ON system_feedbacks(accepted_at DESC);

CREATE INDEX IF NOT EXISTS idx_system_feedback_screenshots_feedback_id
    ON system_feedback_screenshots(feedback_id);

CREATE INDEX IF NOT EXISTS idx_system_feedback_comments_feedback_id
    ON system_feedback_comments(feedback_id);

CREATE INDEX IF NOT EXISTS idx_system_feedback_comments_created_at
    ON system_feedback_comments(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_system_feedback_read_states_last_read
    ON system_feedback_read_states(last_read_at DESC);
