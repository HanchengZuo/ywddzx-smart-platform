-- inspection_table_fields 表：检查表字段配置表
-- 用途：
-- 1. 记录每张检查表有哪些字段
-- 2. 字段系统标识由系统自动生成，并在全局唯一，便于追溯字段来源
-- 3. 标识哪些字段可用于前端高级筛选
-- 4. 供前端动态渲染不同检查表的筛选项

CREATE TABLE inspection_table_fields (
    id SERIAL PRIMARY KEY,                                             -- 字段配置ID，主键，自增
    inspection_table_id INTEGER NOT NULL REFERENCES inspection_tables(id) ON DELETE CASCADE, -- 所属检查表ID
    field_key TEXT UNIQUE NOT NULL,                                    -- 字段系统标识，全局唯一
    field_label TEXT NOT NULL,                                         -- 字段名称，由用户维护
    is_filterable BOOLEAN DEFAULT TRUE,                                -- 是否可筛选
    sort_order INTEGER DEFAULT 0,                                      -- 排序号
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,                    -- 创建时间
    UNIQUE (inspection_table_id, field_key)
);
