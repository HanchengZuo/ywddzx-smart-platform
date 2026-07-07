-- inspection_internal_standards 表：业务督导中心自建内部巡检规范库
-- 用途：
-- 1. 内部规范由“规范内容 + 标签 + 外部规范ID挂载关系”组成
-- 2. internal_standard_id 为系统生成的内部规范ID
-- 3. field_values/path_values 保留用于兼容旧版字段结构数据

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
-- 3. is_long_text 用于新增/编辑内部规范时展示长文本输入框
-- 4. is_register_visible 用于巡检登记规范搜索结果展示
-- 5. 字段删除后，对应 field_values 内容会在业务层清理

CREATE TABLE inspection_internal_standard_fields (
    id SERIAL PRIMARY KEY,
    field_key TEXT UNIQUE NOT NULL,
    field_label TEXT UNIQUE NOT NULL,
    is_filterable BOOLEAN DEFAULT TRUE,
    is_long_text BOOLEAN DEFAULT FALSE,
    is_register_visible BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE inspection_internal_standard_fields
ADD COLUMN IF NOT EXISTS is_long_text BOOLEAN DEFAULT FALSE;

ALTER TABLE inspection_internal_standard_fields
ADD COLUMN IF NOT EXISTS is_register_visible BOOLEAN DEFAULT TRUE;

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

-- inspection_internal_standard_tag_groups 表：内部规范标签群组
-- 说明：
-- 1. 外部规范ID、检查表为系统标签群组
-- 2. custom 类型由用户维护，例如区域、环节、专业等标签群组

CREATE TABLE inspection_internal_standard_tag_groups (
    id SERIAL PRIMARY KEY,
    group_name TEXT UNIQUE NOT NULL,
    group_type TEXT NOT NULL DEFAULT 'custom',
    color TEXT NOT NULL DEFAULT '#2563EB',
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    is_required BOOLEAN NOT NULL DEFAULT FALSE,
    is_filterable BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_internal_standard_tag_group_type
        CHECK (group_type IN ('custom', 'external_standard', 'inspection_table'))
);

CREATE TABLE inspection_internal_standard_tags (
    id SERIAL PRIMARY KEY,
    group_id INTEGER NOT NULL REFERENCES inspection_internal_standard_tag_groups(id) ON DELETE CASCADE,
    tag_name TEXT NOT NULL,
    tag_key TEXT NOT NULL,
    color TEXT NOT NULL DEFAULT '#2563EB',
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (group_id, tag_key)
);

CREATE TABLE inspection_internal_standard_tag_links (
    internal_standard_id INTEGER NOT NULL REFERENCES inspection_internal_standards(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES inspection_internal_standard_tags(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (internal_standard_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_internal_standard_tags_group
ON inspection_internal_standard_tags (group_id, sort_order);

CREATE INDEX IF NOT EXISTS idx_internal_standard_tag_links_tag
ON inspection_internal_standard_tag_links (tag_id);

INSERT INTO inspection_internal_standard_tag_groups (
    group_name,
    group_type,
    color,
    is_system,
    is_required,
    is_filterable,
    sort_order
)
VALUES
    ('外部规范ID', 'external_standard', '#2563EB', TRUE, TRUE, TRUE, 0),
    ('检查表', 'inspection_table', '#0F766E', TRUE, FALSE, TRUE, 1)
ON CONFLICT (group_name) DO NOTHING;

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
