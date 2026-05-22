-- ai_usage_logs 表：AI 调用统计日志
-- 用途：
-- 1. 记录用户在系统内触发 AI 能力的位置和结果
-- 2. 按字符数粗略估算 token 用量和费用
-- 3. 为后续 AI 能力复用、费用分析和异常排查提供基础数据

CREATE TABLE IF NOT EXISTS ai_usage_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    username TEXT,
    real_name TEXT,
    role TEXT,
    usage_module TEXT NOT NULL,
    usage_action TEXT NOT NULL,
    model TEXT NOT NULL,
    base_url TEXT DEFAULT 'https://api.deepseek.com',
    ai_called BOOLEAN NOT NULL DEFAULT FALSE,
    ai_generated BOOLEAN NOT NULL DEFAULT FALSE,
    success BOOLEAN NOT NULL DEFAULT FALSE,
    fallback_used BOOLEAN NOT NULL DEFAULT FALSE,
    status_code INTEGER,
    prompt_chars INTEGER NOT NULL DEFAULT 0,
    prompt_chinese_chars INTEGER NOT NULL DEFAULT 0,
    prompt_other_chars INTEGER NOT NULL DEFAULT 0,
    completion_chars INTEGER NOT NULL DEFAULT 0,
    completion_chinese_chars INTEGER NOT NULL DEFAULT 0,
    completion_other_chars INTEGER NOT NULL DEFAULT 0,
    total_chars INTEGER NOT NULL DEFAULT 0,
    input_tokens_est NUMERIC(14, 2) NOT NULL DEFAULT 0,
    output_tokens_est NUMERIC(14, 2) NOT NULL DEFAULT 0,
    total_tokens_est NUMERIC(14, 2) NOT NULL DEFAULT 0,
    input_cost_est NUMERIC(14, 6) NOT NULL DEFAULT 0,
    output_cost_est NUMERIC(14, 6) NOT NULL DEFAULT 0,
    total_cost_est NUMERIC(14, 6) NOT NULL DEFAULT 0,
    message TEXT,
    request_summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ai_usage_logs_created_at
    ON ai_usage_logs(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_usage_logs_user_id
    ON ai_usage_logs(user_id);

CREATE INDEX IF NOT EXISTS idx_ai_usage_logs_module_action
    ON ai_usage_logs(usage_module, usage_action);
