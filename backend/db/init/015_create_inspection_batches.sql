-- inspection_batches 表：巡检批次表
-- 用途：
-- 1. 以“站点 + 日期”为维度，承载一次完整批次检查
-- 2. 一个批次下可挂多条 inspections（不同检查表）
-- 3. 用于站经理签名确认、批次锁定与批次级汇总展示

CREATE TABLE IF NOT EXISTS inspection_batches (
    id SERIAL PRIMARY KEY,
    station_id INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    inspector_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    batch_date DATE NOT NULL,
    status TEXT NOT NULL DEFAULT '进行中',
    station_manager_signed_name TEXT,
    station_manager_signature_path TEXT,
    station_manager_signed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_inspection_batches_status CHECK (status IN ('进行中', '已签名确认'))
);

-- 同一站点同一天只允许存在一个“进行中”批次
CREATE UNIQUE INDEX IF NOT EXISTS uq_inspection_batches_station_date_open
ON inspection_batches (station_id, batch_date)
WHERE status = '进行中';

CREATE INDEX IF NOT EXISTS idx_inspection_batches_station_date
ON inspection_batches (station_id, batch_date);

CREATE INDEX IF NOT EXISTS idx_inspection_batches_inspector_date
ON inspection_batches (inspector_id, batch_date);

ALTER TABLE inspections
ADD COLUMN IF NOT EXISTS batch_id INTEGER REFERENCES inspection_batches(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_inspections_batch_id
ON inspections (batch_id);
