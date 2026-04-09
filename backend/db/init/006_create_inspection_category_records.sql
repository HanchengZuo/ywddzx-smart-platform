-- inspection_category_records 表：巡检大类结果记录表
-- 用途：
-- 1. 记录某次巡检中，检查了哪个巡检大类
-- 2. 记录该大类本次巡检结果是“正常”还是“异常”
-- 3. 即使未发现问题，也必须保留一条记录
-- 4. 若该大类发现问题，则 issues 表中的问题从属于本表记录
--
-- 说明：
-- - 一个 inspection 下可以关联多个 category_record
-- - 同一次巡检中，同一个大类只允许记录一次
--
-- result 说明：
-- - 正常：本次检查该大类未发现问题
-- - 异常：本次检查该大类发现问题

CREATE TABLE inspection_category_records (
    id SERIAL PRIMARY KEY,                                              -- 巡检大类结果记录ID，主键，自增
    inspection_id INTEGER NOT NULL REFERENCES inspections(id),          -- 所属巡检主记录ID
    category_id INTEGER NOT NULL REFERENCES inspection_categories(id),  -- 巡检大类ID

    result TEXT NOT NULL,                                               -- 检查结果：正常 / 异常
    summary TEXT,                                                       -- 摘要，例如：本次计量检查未发现问题
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,                     -- 创建时间

    UNIQUE (inspection_id, category_id)                                 -- 同一次巡检中一个大类只记录一次
);