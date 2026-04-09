

-- inspection_standards 表：巡检规范标准表
-- 用途：
-- 1. 保存固定的巡检检查标准
-- 2. 督导组录入问题时引用其中一条规范
-- 3. 一个问题仅对应一条规范

CREATE TABLE inspection_standards (
    id SERIAL PRIMARY KEY,                              -- 规范ID，主键，自增
    code TEXT UNIQUE NOT NULL,                          -- 问题编号/规范编号，例如：1、10、18
    business_process TEXT NOT NULL,                     -- 业务流程，例如：质量监控、计量监控
    check_item TEXT NOT NULL,                           -- 检查项目，例如：储油周期、油品库存管理
    check_content TEXT NOT NULL,                        -- 检查内容，例如：油品检验、库存盘点
    requirement TEXT NOT NULL,                          -- 规范要求
    check_method TEXT NOT NULL,                         -- 检查方法
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP      -- 创建时间
);