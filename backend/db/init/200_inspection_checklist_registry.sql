-- inspection_tables 表：巡检检查表注册表
-- 用途：
-- 1. 登记系统内由管理页面创建的检查表
-- 2. 记录检查表名称、编码
-- 3. 供前端选择“哪张检查表”时使用

CREATE TABLE inspection_tables (
    id SERIAL PRIMARY KEY,                               -- 检查表ID，主键，自增
    table_code TEXT UNIQUE NOT NULL,                     -- 检查表编码，例如：safety_check
    table_name TEXT UNIQUE NOT NULL,                     -- 检查表名称，例如：安全管理检查表
    checklist_mode TEXT NOT NULL DEFAULT 'online' CHECK (checklist_mode IN ('online', 'offline')), -- 检查表模式：online 线上 / offline 线下
    standard_id_base INTEGER UNIQUE,                     -- 该检查表规范ID号段起点，例如第一张表 1000、第二张表 2000
    description TEXT,                                    -- 描述
    is_active BOOLEAN DEFAULT TRUE,                      -- 是否启用
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,      -- 创建时间
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP       -- 更新时间
);
