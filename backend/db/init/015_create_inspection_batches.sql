-- inspection_batches 表：巡检批次表
-- 用途：
-- 1. 以“站点 + 日期”为维度，承载一次完整批次检查
-- 2. 一个批次下可挂多条 inspections（不同检查表）
-- 3. 仅用于同一天同站点巡检记录的分组归属，不再承载签名状态与签名结果

CREATE TABLE IF NOT EXISTS inspection_batches (
    id SERIAL PRIMARY KEY,
    station_id INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    inspector_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    batch_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 同一站点同一天只保留一个批次记录，用于归拢当日该站点的多张检查表巡检记录
CREATE UNIQUE INDEX IF NOT EXISTS uq_inspection_batches_station_date
ON inspection_batches (station_id, batch_date);

CREATE INDEX IF NOT EXISTS idx_inspection_batches_station_date
ON inspection_batches (station_id, batch_date);

CREATE INDEX IF NOT EXISTS idx_inspection_batches_inspector_date
ON inspection_batches (inspector_id, batch_date);

ALTER TABLE inspections
ADD COLUMN IF NOT EXISTS batch_id INTEGER REFERENCES inspection_batches(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_inspections_batch_id
ON inspections (batch_id);