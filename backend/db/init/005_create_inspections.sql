-- inspections 表：巡检主表
-- 用途：
-- 1. 记录督导组对某站点发起的一次巡检登记
-- 2. 每次提交都视为一次独立巡检动作
-- 3. 绑定本次巡检所选的检查表
--
-- 说明：
-- - 当前系统已取消“大类”概念，改为“先选检查表”
-- - 后续 issues 表中的问题记录通过 inspection_id 关联到本表

CREATE TABLE inspections (
    id SERIAL PRIMARY KEY,                                                    -- 巡检主记录ID，主键，自增
    station_id INTEGER NOT NULL REFERENCES stations(id),                      -- 巡检站点ID
    inspector_id INTEGER NOT NULL REFERENCES users(id),                       -- 巡检人ID
    inspection_table_id INTEGER NOT NULL REFERENCES inspection_tables(id),    -- 本次巡检所选检查表ID
    inspection_date DATE NOT NULL,                                            -- 巡检日期（精确到天）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP                            -- 创建时间
);