-- inspection_completion_settings 表：巡检记录完成确认规则
-- 用途：
-- 1. 将“站经理签字确认”和“检查人完成封存”拆开
-- 2. 同站点同检查表当月只复用一条 inspections 记录
-- 3. 检查人手动确认完成后，该检查表记录封存，不能继续新增、编辑、删除问题
-- 4. 超过配置天数仍未确认时，由系统自动确认完成

ALTER TABLE inspections
ADD COLUMN IF NOT EXISTS inspector_completion_status TEXT NOT NULL DEFAULT '待检查人确认';

ALTER TABLE inspections
ADD COLUMN IF NOT EXISTS inspector_completed_by INTEGER REFERENCES users(id) ON DELETE SET NULL;

ALTER TABLE inspections
ADD COLUMN IF NOT EXISTS inspector_completed_at TIMESTAMP;

ALTER TABLE inspections
ADD COLUMN IF NOT EXISTS inspector_completion_source TEXT;

ALTER TABLE inspections
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

UPDATE inspections
SET inspector_completion_status = '待检查人确认'
WHERE inspector_completion_status IS NULL
   OR inspector_completion_status NOT IN ('待检查人确认', '已确认完成');

UPDATE inspections
SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
WHERE updated_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_inspections_station_table_month
ON inspections (station_id, inspection_table_id, inspection_date);

CREATE INDEX IF NOT EXISTS idx_inspections_completion_status
ON inspections (inspector_completion_status, inspection_date);

CREATE TABLE IF NOT EXISTS inspection_completion_settings (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE,
    auto_complete_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    auto_complete_days INTEGER NOT NULL DEFAULT 7,
    updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_inspection_completion_singleton CHECK (singleton = TRUE),
    CONSTRAINT chk_inspection_completion_days CHECK (auto_complete_days BETWEEN 1 AND 31)
);

INSERT INTO inspection_completion_settings (
    singleton,
    auto_complete_enabled,
    auto_complete_days
)
VALUES (TRUE, TRUE, 7)
ON CONFLICT (singleton) DO NOTHING;
