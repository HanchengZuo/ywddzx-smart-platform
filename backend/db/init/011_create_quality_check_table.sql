-- 计质量检查表
-- 用途：
-- 1. 存储“计质量检查表”中的规范条目
-- 2. 每条规范拥有全局唯一 standard_id
-- 3. 本表字段固定，对应计质量检查表本身的结构

CREATE TABLE inspection_table_quality_check (
    id SERIAL PRIMARY KEY,                                   -- 主键，自增
    standard_id BIGINT UNIQUE NOT NULL,                      -- 全局唯一规范ID
    serial_no TEXT NOT NULL,                                 -- 序号，例如：1.1.1
    business_process TEXT,                                   -- 业务流程
    check_item TEXT,                                         -- 检查项目
    check_content TEXT,                                      -- 检查内容
    requirement TEXT,                                        -- 规范要求
    check_method TEXT,                                       -- 检查方法
    issue_code TEXT,                                         -- 问题编号
    common_issue TEXT,                                       -- 常见问题
    inspection_path TEXT,                                    -- 检查路径
    is_forbidden TEXT CHECK (is_forbidden IN ('是', '否')),   -- 是否禁止项
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP           -- 创建时间
);