"""Business notification evidence and lightweight signature-readiness invalidations."""
from alembic import op

revision = '20261101_002'
down_revision = '20261101_001'
branch_labels = depends_on = None


def upgrade():
    op.execute('''ALTER TABLE web_push_messages DROP CONSTRAINT web_push_messages_kind_check;
    ALTER TABLE web_push_messages ADD CONSTRAINT web_push_messages_kind_check CHECK(kind IN ('manual','test','business'));
    ALTER TABLE web_push_messages ADD COLUMN event_key TEXT UNIQUE;
    ALTER TABLE web_push_messages ADD COLUMN source TEXT NOT NULL DEFAULT '';
    ALTER TABLE web_push_messages ADD COLUMN entity_id INTEGER;
    ALTER TABLE web_push_messages ADD COLUMN action_path TEXT NOT NULL DEFAULT '/notifications';
    ALTER TABLE web_push_messages ADD COLUMN push_hint TEXT NOT NULL DEFAULT '';
    ALTER TABLE web_push_recipients ADD COLUMN delivery_note TEXT NOT NULL DEFAULT '';
    CREATE TABLE web_push_signature_state (
      inspection_id INTEGER PRIMARY KEY REFERENCES inspections(id) ON DELETE CASCADE,
      ready BOOLEAN NOT NULL, station_id INTEGER, episode INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE web_push_signature_changes (
      id BIGSERIAL PRIMARY KEY, inspection_id INTEGER NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
      changed_at TIMESTAMPTZ NOT NULL DEFAULT now());
    CREATE INDEX web_push_signature_changes_record ON web_push_signature_changes(inspection_id,id);
    -- Establish a baseline, not a broadcast of the pre-upgrade unread backlog.
    INSERT INTO web_push_signature_state(inspection_id,ready,station_id)
      SELECT ins.id,COALESCE(ins.inspector_completion_status,'待检查人确认')='已确认完成'
        AND COALESCE(ins.sign_status,'待签名确认')<>'已签名确认'
        AND NOT EXISTS(SELECT 1 FROM issues i WHERE i.inspection_id=ins.id AND COALESCE(i.audit_status,'pending')='pending'),
        ins.station_id FROM inspections ins;
    CREATE FUNCTION push_signature_changed() RETURNS trigger AS $$
    DECLARE target INTEGER;
    BEGIN
      IF TG_TABLE_NAME='issues' THEN
        IF TG_OP<>'INSERT' THEN
          target := OLD.inspection_id;
          INSERT INTO web_push_signature_changes(inspection_id) SELECT target WHERE EXISTS(SELECT 1 FROM inspections WHERE id=target);
        END IF;
        IF TG_OP<>'DELETE' AND (TG_OP='INSERT' OR NEW.inspection_id IS DISTINCT FROM OLD.inspection_id) THEN
          target := NEW.inspection_id;
          INSERT INTO web_push_signature_changes(inspection_id) SELECT target WHERE EXISTS(SELECT 1 FROM inspections WHERE id=target);
        END IF;
      ELSE
        INSERT INTO web_push_signature_changes(inspection_id) VALUES(NEW.id);
      END IF;
      RETURN NULL;
    END; $$ LANGUAGE plpgsql;
    CREATE TRIGGER push_signature_issue_change AFTER INSERT OR DELETE OR UPDATE OF audit_status,inspection_id ON issues
      FOR EACH ROW EXECUTE FUNCTION push_signature_changed();
    CREATE TRIGGER push_signature_record_change AFTER INSERT OR UPDATE OF sign_status,inspector_completion_status,station_id,inspection_table_id ON inspections
      FOR EACH ROW EXECUTE FUNCTION push_signature_changed();''')


def downgrade():
    op.execute('''DROP TRIGGER push_signature_issue_change ON issues;
    DROP TRIGGER push_signature_record_change ON inspections;
    DROP FUNCTION push_signature_changed();
    DROP TABLE web_push_signature_changes,web_push_signature_state;
    DELETE FROM web_push_messages WHERE kind='business';
    ALTER TABLE web_push_messages DROP CONSTRAINT web_push_messages_kind_check;
    ALTER TABLE web_push_messages ADD CONSTRAINT web_push_messages_kind_check CHECK(kind IN ('manual','test'));
    ALTER TABLE web_push_messages DROP COLUMN event_key,DROP COLUMN source,DROP COLUMN entity_id,DROP COLUMN action_path,DROP COLUMN push_hint;
    ALTER TABLE web_push_recipients DROP COLUMN delivery_note;''')
