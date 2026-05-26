-- inspection_table_fields 表：检查表字段配置表
-- 用途：
-- 1. 记录每张检查表有哪些字段
-- 2. 字段系统标识由系统自动生成，并在全局唯一，便于追溯字段来源
-- 3. 标识哪些字段可用于前端高级筛选
-- 4. 标识哪些字段在巡检登记规范搜索结果中展示
-- 5. 标识哪些字段参与站点评分
-- 6. 供前端动态渲染不同检查表的筛选项

CREATE TABLE inspection_table_fields (
    id SERIAL PRIMARY KEY,                                             -- 字段配置ID，主键，自增
    inspection_table_id INTEGER NOT NULL REFERENCES inspection_tables(id) ON DELETE CASCADE, -- 所属检查表ID
    field_key TEXT UNIQUE NOT NULL,                                    -- 字段系统标识，全局唯一
    field_label TEXT NOT NULL,                                         -- 字段名称，由用户维护
    is_filterable BOOLEAN DEFAULT TRUE,                                -- 是否可筛选
    is_register_visible BOOLEAN DEFAULT TRUE,                          -- 是否在巡检登记规范搜索结果中展示
    is_long_text BOOLEAN DEFAULT FALSE,                                -- 是否为长内容字段
    is_scorable BOOLEAN DEFAULT FALSE,                                 -- 是否作为站点评分依据
    sort_order INTEGER DEFAULT 0,                                      -- 排序号
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,                    -- 创建时间
    UNIQUE (inspection_table_id, field_key)
);

-- inspection_standard_export_templates 表：外部规范导出模板
-- 用途：
-- 1. 记录导出规范时每张检查表需要展示哪些字段
-- 2. 模板为全系统共享，不区分用户
-- 3. 未配置模板时默认导出全部字段

CREATE TABLE inspection_standard_export_templates (
    id INTEGER PRIMARY KEY DEFAULT 1,                    -- 固定为 1，表示全局唯一模板
    template_config JSONB NOT NULL DEFAULT '{}'::jsonb,  -- {检查表ID: [字段键...]}
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,      -- 最近更新时间
    CONSTRAINT inspection_standard_export_templates_singleton CHECK (id = 1)
);
