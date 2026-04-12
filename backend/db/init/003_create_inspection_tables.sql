-- inspection_tables 表：巡检检查表注册表
-- 用途：
-- 1. 登记系统内有哪些检查表
-- 2. 记录检查表名称、编码
-- 3. 供前端选择“哪张检查表”时使用

CREATE TABLE inspection_tables (
    id SERIAL PRIMARY KEY,                               -- 检查表ID，主键，自增
    table_code TEXT UNIQUE NOT NULL,                     -- 检查表编码，例如：quality_check / service_hygiene_check
    table_name TEXT UNIQUE NOT NULL,                     -- 检查表名称，例如：计质量检查表
    description TEXT,                                    -- 描述
    is_active BOOLEAN DEFAULT TRUE,                      -- 是否启用
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP       -- 创建时间
);