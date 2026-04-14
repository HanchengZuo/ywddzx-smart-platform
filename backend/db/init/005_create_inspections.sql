-- inspections 表：巡检主表
-- 用途：
-- 1. 记录督导组对某站点发起的一次巡检登记
-- 2. 每次提交都视为一次独立巡检动作
-- 3. 绑定本次巡检所选的检查表
-- 4. 后续可通过 batch_id 归属到同一巡检批次（见 015_create_inspection_batches.sql）
--
-- 说明：
-- - 当前系统已取消“大类”概念，改为“先选检查表”
-- - 后续 issues 表中的问题记录通过 inspection_id 关联到本表
-- - batch_id 不在本文件中定义，而由后续增量 SQL 补充，便于兼容已有初始化顺序

CREATE TABLE inspections (
    id SERIAL PRIMARY KEY,                                                    -- 巡检主记录ID，主键，自增
    station_id INTEGER NOT NULL REFERENCES stations(id),                      -- 巡检站点ID
    inspector_id INTEGER NOT NULL REFERENCES users(id),                       -- 巡检人ID
    inspection_table_id INTEGER NOT NULL REFERENCES inspection_tables(id),    -- 本次巡检所选检查表ID
    inspection_date DATE NOT NULL,                                            -- 巡检日期（精确到天）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP                            -- 创建时间
);