-- station_score_adjustments 表：站点评分人工调整记录
-- 用途：
-- 1. 按站点、月份、检查表和外部规范ID记录人工调整后的分值
-- 2. 记录最后调整人和调整时间
-- 3. 系统自动评分不落库，人工调整结果持久化并全局可见

CREATE TABLE station_score_adjustments (
    id SERIAL PRIMARY KEY,
    station_id INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    inspection_table_id INTEGER NOT NULL REFERENCES inspection_tables(id) ON DELETE CASCADE,
    standard_id BIGINT NOT NULL,
    score_month TEXT NOT NULL,
    manual_score NUMERIC(8, 2) NOT NULL,
    note TEXT,
    adjusted_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    adjusted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (station_id, inspection_table_id, standard_id, score_month)
);

CREATE INDEX idx_station_score_adjustments_month
ON station_score_adjustments (score_month);

