-- inspection_internal_standards 表：业务督导中心自建内部巡检规范库
-- 用途：
-- 1. 以动态字段配置承载内部规范结构，例如：区域、环节、分类、子分类、规范等
-- 2. internal_standard_id 为系统生成的内部规范ID，例如 PDJ1、PDJ2
-- 3. field_values 使用 JSONB 保存每条内部规范的字段值，不写死字段数量

CREATE TABLE inspection_internal_standards (
    id SERIAL PRIMARY KEY,
    internal_standard_id TEXT UNIQUE NOT NULL,
    path_values JSONB NOT NULL DEFAULT '[]'::jsonb,
    field_values JSONB NOT NULL DEFAULT '{}'::jsonb,
    content TEXT NOT NULL DEFAULT '',
    notes TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- inspection_internal_standard_fields 表：内部巡检规范库字段配置
-- 说明：
-- 1. 管理员可自由定义字段数量和顺序
-- 2. is_filterable 用于前端筛选面板
-- 3. 字段删除后，对应 field_values 内容会在业务层清理

CREATE TABLE inspection_internal_standard_fields (
    id SERIAL PRIMARY KEY,
    field_key TEXT UNIQUE NOT NULL,
    field_label TEXT UNIQUE NOT NULL,
    is_filterable BOOLEAN DEFAULT TRUE,
    is_long_text BOOLEAN DEFAULT FALSE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE inspection_internal_standard_fields
ADD COLUMN IF NOT EXISTS is_long_text BOOLEAN DEFAULT FALSE;

-- inspection_internal_standard_links 表：内部规范与外部规范唯一挂载关系
-- 说明：
-- 1. 一条内部规范可挂载多个外部规范ID
-- 2. 一个外部规范ID只能归属于一条内部规范，external_standard_id 全局唯一
-- 3. external_inspection_table_id 用于追溯外部规范来自哪张检查表

CREATE TABLE inspection_internal_standard_links (
    id SERIAL PRIMARY KEY,
    internal_standard_id INTEGER NOT NULL REFERENCES inspection_internal_standards(id) ON DELETE CASCADE,
    external_standard_id BIGINT NOT NULL UNIQUE,
    external_inspection_table_id INTEGER REFERENCES inspection_tables(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_internal_standards_path_values
ON inspection_internal_standards USING GIN (path_values);

CREATE INDEX IF NOT EXISTS idx_internal_standards_field_values
ON inspection_internal_standards USING GIN (field_values);

CREATE INDEX IF NOT EXISTS idx_internal_standard_links_internal
ON inspection_internal_standard_links (internal_standard_id);

-- inspection_standard_usage_settings 表：巡检登记规范来源开关
-- 说明：
-- 1. internal 表示巡检登记使用业务督导中心自建内部规范库
-- 2. external 表示巡检登记临时切回检查表原件库中的外部规范
-- 3. 使用单行配置，便于内部规范整理期灵活切换

CREATE TABLE inspection_standard_usage_settings (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE,
    register_standard_source TEXT NOT NULL DEFAULT 'internal',
    updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_inspection_standard_usage_singleton CHECK (singleton = TRUE),
    CONSTRAINT chk_inspection_standard_usage_source
        CHECK (register_standard_source IN ('internal', 'external'))
);

INSERT INTO inspection_standard_usage_settings (singleton, register_standard_source)
VALUES (TRUE, 'internal')
ON CONFLICT (singleton) DO NOTHING;
