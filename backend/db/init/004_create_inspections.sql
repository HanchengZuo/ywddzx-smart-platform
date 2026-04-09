-- inspections 表：巡检主表
-- 用途：
-- 1. 记录督导组对某站某天发起的一次巡检行为
-- 2. 每一次提交都视为一次独立巡检动作
-- 3. 不再限制同一督导员同一天同一站点只能有一条记录
-- 4. 具体检查了哪些大类、各大类结果如何，由 inspection_category_records 表记录
--
-- 说明：
-- - inspection_date 精确到天
-- - created_at 记录该次巡检主记录的创建时间

CREATE TABLE inspections (
    id SERIAL PRIMARY KEY,                               -- 巡检主记录ID，主键，自增
    station_id INTEGER NOT NULL REFERENCES stations(id), -- 巡检站点ID
    inspector_id INTEGER NOT NULL REFERENCES users(id),  -- 巡检人ID（应为督导组账号）
    inspection_date DATE NOT NULL,                       -- 巡检日期（精确到天）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP       -- 创建时间
);