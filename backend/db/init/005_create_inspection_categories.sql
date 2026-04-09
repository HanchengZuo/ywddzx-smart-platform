-- inspection_categories 表：巡检大类固定表
-- 用途：
-- 1. 保存固定巡检方向/大类
-- 2. 用于巡检登记时选择本次检查属于哪个方向
-- 3. 即使未发现问题，也要记录本次检查了哪个大类
--
-- 示例：
-- - 计量
-- - 安全
-- - 环保
-- - 服务
--
-- 说明：
-- - 本表只保存固定主数据
-- - 具体某次巡检检查了哪个大类，由 inspection_category_records 表记录

CREATE TABLE inspection_categories (
    id SERIAL PRIMARY KEY,                              -- 巡检大类ID，主键，自增
    name TEXT UNIQUE NOT NULL,                          -- 大类名称，例如：计量 / 安全 / 环保
    sort_order INTEGER DEFAULT 0,                       -- 排序号
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP      -- 创建时间
);