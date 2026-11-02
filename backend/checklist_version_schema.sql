CREATE TABLE IF NOT EXISTS inspection_checklist_versions (
    id SERIAL PRIMARY KEY,
    inspection_table_id INTEGER NOT NULL REFERENCES inspection_tables(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL CHECK(version_number > 0),
    version_name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
    fields JSONB NOT NULL DEFAULT '[]'::jsonb CHECK(jsonb_typeof(fields)='array'),
    original_document JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_key TEXT, revision INTEGER NOT NULL DEFAULT 1,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(inspection_table_id,version_number), UNIQUE(inspection_table_id,id),
    UNIQUE(inspection_table_id,source_key)
);
ALTER TABLE inspection_tables ADD COLUMN IF NOT EXISTS active_version_id INTEGER;
CREATE TABLE IF NOT EXISTS checklist_standard_registry (
    standard_id BIGINT PRIMARY KEY CHECK(standard_id > 0),
    inspection_table_id INTEGER NOT NULL REFERENCES inspection_tables(id) ON DELETE RESTRICT,
    checklist_version_id INTEGER NOT NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    archived_data JSONB,
    FOREIGN KEY(inspection_table_id,checklist_version_id)
      REFERENCES inspection_checklist_versions(inspection_table_id,id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS checklist_registry_version ON checklist_standard_registry(checklist_version_id,standard_id);
CREATE TABLE IF NOT EXISTS checklist_version_events (
    id BIGSERIAL PRIMARY KEY,
    inspection_table_id INTEGER NOT NULL REFERENCES inspection_tables(id) ON DELETE RESTRICT,
    checklist_version_id INTEGER NOT NULL REFERENCES inspection_checklist_versions(id) ON DELETE RESTRICT,
    action TEXT NOT NULL, actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS inspection_report_version_bindings (
    inspection_table_id INTEGER PRIMARY KEY REFERENCES inspection_tables(id) ON DELETE RESTRICT,
    checklist_version_id INTEGER NOT NULL REFERENCES inspection_checklist_versions(id) ON DELETE RESTRICT
);

CREATE OR REPLACE FUNCTION checklist_bind_standard_version() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE family INTEGER; active INTEGER;
BEGIN
    SELECT id,active_version_id INTO family,active FROM inspection_tables
    WHERE 'inspection_table_'||table_code=TG_TABLE_NAME FOR SHARE;
    IF family IS NULL THEN RAISE EXCEPTION '检查表未完成版本初始化'; END IF;
    IF TG_OP='DELETE' THEN
        UPDATE checklist_standard_registry SET is_deleted=TRUE,archived_data=to_jsonb(OLD)
          WHERE standard_id=OLD.standard_id;
        RETURN OLD;
    END IF;
    IF TG_OP='UPDATE' AND NEW.standard_id<>OLD.standard_id THEN
        RAISE EXCEPTION '规范ID全局唯一，创建后不能更改';
    END IF;
    NEW.checklist_version_id := COALESCE(NEW.checklist_version_id,active);
    IF NOT EXISTS(SELECT 1 FROM inspection_checklist_versions WHERE id=NEW.checklist_version_id AND inspection_table_id=family)
    THEN RAISE EXCEPTION '规范与检查表版本不匹配'; END IF;
    IF TG_OP='INSERT' THEN
        INSERT INTO checklist_standard_registry(standard_id,inspection_table_id,checklist_version_id)
        VALUES(NEW.standard_id,family,NEW.checklist_version_id);
    ELSIF NEW.checklist_version_id IS DISTINCT FROM OLD.checklist_version_id THEN
        IF current_setting('ywddzx.allow_standard_reassignment',TRUE) IS DISTINCT FROM 'on'
        THEN RAISE EXCEPTION '不能移动已有规范的版本，请为新版创建新的规范ID'; END IF;
        UPDATE checklist_standard_registry SET checklist_version_id=NEW.checklist_version_id WHERE standard_id=NEW.standard_id;
    END IF;
    RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION checklist_bind_record_version() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE active INTEGER; enabled BOOLEAN; assigned INTEGER; record_version INTEGER;
BEGIN
    IF TG_OP='UPDATE' AND NEW.inspection_table_id=OLD.inspection_table_id THEN
        IF TG_TABLE_NAME<>'issues' THEN
            IF NEW.checklist_version_id IS DISTINCT FROM OLD.checklist_version_id
            THEN RAISE EXCEPTION '历史业务数据的检查表版本不能直接修改'; END IF;
            RETURN NEW;
        END IF;
        IF NEW.standard_id IS NOT DISTINCT FROM OLD.standard_id THEN
            IF NEW.checklist_version_id IS DISTINCT FROM OLD.checklist_version_id
            THEN RAISE EXCEPTION '历史业务数据的检查表版本不能直接修改'; END IF;
            RETURN NEW;
        END IF;
    END IF;
    SELECT active_version_id,is_active INTO active,enabled FROM inspection_tables
      WHERE id=NEW.inspection_table_id FOR SHARE;
    IF active IS NULL OR NOT COALESCE(enabled,FALSE) THEN RAISE EXCEPTION '检查表未启用'; END IF;
    assigned := active;
    IF TG_TABLE_NAME='issues' THEN
        SELECT checklist_version_id INTO assigned FROM checklist_standard_registry
          WHERE standard_id=NEW.standard_id AND inspection_table_id=NEW.inspection_table_id AND NOT is_deleted;
        IF assigned IS DISTINCT FROM active THEN RAISE EXCEPTION '规范所属检查表版本已停用，请重新选择规范'; END IF;
        SELECT checklist_version_id INTO record_version FROM inspections WHERE id=NEW.inspection_id;
        IF record_version IS DISTINCT FROM assigned THEN RAISE EXCEPTION '巡检记录版本已变化，请刷新后重新登记'; END IF;
    END IF;
    IF TG_OP='INSERT' AND NEW.checklist_version_id IS NOT NULL AND NEW.checklist_version_id<>assigned
    THEN RAISE EXCEPTION '检查表版本已变化，请刷新后重新登记'; END IF;
    NEW.checklist_version_id := assigned;
    RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION checklist_create_initial_version() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE version_id INTEGER;
BEGIN
    INSERT INTO inspection_checklist_versions(inspection_table_id,version_number,version_name)
      VALUES(NEW.id,1,'初始版本') RETURNING id INTO version_id;
    UPDATE inspection_tables SET active_version_id=version_id WHERE id=NEW.id;
    INSERT INTO inspection_report_version_bindings VALUES(NEW.id,version_id);
    RETURN NEW;
END $$;
