-- inspection_table_fields 表：检查表字段配置表
-- 用途：
-- 1. 记录每张检查表有哪些字段
-- 2. 标识哪些字段可用于前端高级筛选
-- 3. 供前端动态渲染不同检查表的筛选项

CREATE TABLE inspection_table_fields (
    id SERIAL PRIMARY KEY,                                             -- 字段配置ID，主键，自增
    inspection_table_id INTEGER NOT NULL REFERENCES inspection_tables(id), -- 所属检查表ID
    field_key TEXT NOT NULL,                                           -- 字段键，例如：business_process
    field_label TEXT NOT NULL,                                         -- 字段名称，例如：业务流程
    is_filterable BOOLEAN DEFAULT TRUE,                                -- 是否可筛选
    sort_order INTEGER DEFAULT 0,                                      -- 排序号
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP                     -- 创建时间
);