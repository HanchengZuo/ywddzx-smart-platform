"""Persistent quality workflow deadlines, policy snapshots and timeout evidence."""
from alembic import op

revision = '20260906_002'
down_revision = '20260906_001'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE IF NOT EXISTS quality_deadline_policy (
      id integer PRIMARY KEY CHECK(id=1), acceptance_days integer NOT NULL DEFAULT 3 CHECK(acceptance_days BETWEEN 1 AND 365),
      appeal_days integer NOT NULL DEFAULT 3 CHECK(appeal_days BETWEEN 1 AND 365),
      review_days integer NOT NULL DEFAULT 3 CHECK(review_days BETWEEN 1 AND 365),
      timeout_action text NOT NULL DEFAULT 'manual' CHECK(timeout_action IN ('manual','approve','reject')),
      version integer NOT NULL DEFAULT 1, activated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_by integer REFERENCES users(id) ON DELETE SET NULL
    );
    INSERT INTO quality_deadline_policy(id) VALUES(1) ON CONFLICT DO NOTHING;
    CREATE TABLE IF NOT EXISTS quality_deadline_events (
      id bigserial PRIMARY KEY, kind text NOT NULL, inspection_id integer, issue_id integer, appeal_id integer,
      stage text, started_at timestamptz, deadline_at timestamptz, policy jsonb NOT NULL DEFAULT '{}',
      responsible jsonb NOT NULL DEFAULT '[]', actor jsonb NOT NULL DEFAULT '{}', detail text NOT NULL,
      created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS quality_deadline_events_created ON quality_deadline_events(id DESC);
    CREATE INDEX IF NOT EXISTS quality_deadline_events_inspection ON quality_deadline_events(inspection_id);
    CREATE TABLE IF NOT EXISTS quality_deadline_worker_state (
      id integer PRIMARY KEY CHECK(id=1), last_success_at timestamptz, last_failure_at timestamptz
    );
    INSERT INTO quality_deadline_worker_state(id) VALUES(1) ON CONFLICT DO NOTHING;
    ALTER TABLE inspections ADD COLUMN IF NOT EXISTS quality_accept_started_at timestamptz;
    ALTER TABLE inspections ADD COLUMN IF NOT EXISTS quality_accept_deadline_at timestamptz;
    ALTER TABLE inspections ADD COLUMN IF NOT EXISTS quality_accept_policy jsonb;
    ALTER TABLE inspections ADD COLUMN IF NOT EXISTS quality_accept_source text;
    ALTER TABLE issues ADD COLUMN IF NOT EXISTS quality_appeal_started_at timestamptz;
    ALTER TABLE issues ADD COLUMN IF NOT EXISTS quality_appeal_deadline_at timestamptz;
    ALTER TABLE issues ADD COLUMN IF NOT EXISTS quality_appeal_policy jsonb;
    ALTER TABLE inspection_issue_appeals ADD COLUMN IF NOT EXISTS review_deadline_at timestamptz;
    ALTER TABLE inspection_issue_appeals ADD COLUMN IF NOT EXISTS review_started_at timestamptz;
    ALTER TABLE inspection_issue_appeals ADD COLUMN IF NOT EXISTS review_policy jsonb;
    ALTER TABLE inspection_issue_appeals ADD COLUMN IF NOT EXISTS timeout_at timestamptz;
    ALTER TABLE inspection_issue_appeals ADD COLUMN IF NOT EXISTS timeout_stage text;
    ALTER TABLE inspection_issue_appeals ADD COLUMN IF NOT EXISTS phase_responsible jsonb NOT NULL DEFAULT '{}';
    CREATE INDEX IF NOT EXISTS quality_accept_due ON inspections(quality_accept_deadline_at) WHERE sign_status <> '已签名确认';
    CREATE INDEX IF NOT EXISTS quality_review_due ON inspection_issue_appeals(review_deadline_at) WHERE status IN ('area_pending','quality_pending');

    CREATE OR REPLACE FUNCTION is_quality_deadline_table(table_id integer) RETURNS boolean AS $$
      SELECT COALESCE(bool_or(
        btrim(regexp_replace(replace(table_name,'加油站',''), '[（(](现场|视频)[）)]', '', 'g')) IN ('计量稽查检查表','质量安全环保检查表')
          AND lower(btrim(COALESCE(NULLIF(checklist_mode,''),'online'))) IN ('online','offline')
        OR btrim(regexp_replace(replace(table_name,'加油站',''), '[（(](现场|视频)[）)]', '', 'g')) = '环境无异味管理检查表' AND lower(btrim(COALESCE(NULLIF(checklist_mode,''),'online')))='offline'
      ),false) FROM inspection_tables WHERE id=table_id;
    $$ LANGUAGE sql STABLE;

    CREATE OR REPLACE FUNCTION refresh_quality_acceptance(target_id integer) RETURNS void AS $$
    DECLARE rec record; cfg record; ready_at timestamptz; pending boolean;
    BEGIN
      SELECT * INTO rec FROM inspections WHERE id=target_id FOR UPDATE;
      IF NOT FOUND OR NOT is_quality_deadline_table(rec.inspection_table_id) THEN RETURN; END IF;
      IF rec.sign_status='已签名确认' THEN RETURN; END IF;
      SELECT * INTO cfg FROM quality_deadline_policy WHERE id=1;
      SELECT COALESCE(bool_or(COALESCE(audit_status,'pending')='pending'),false),
        GREATEST(max(audited_at AT TIME ZONE 'Asia/Shanghai'), rec.inspector_completed_at AT TIME ZONE 'Asia/Shanghai', cfg.activated_at)
        INTO pending,ready_at FROM issues WHERE inspection_id=target_id;
      IF rec.inspector_completion_status IS DISTINCT FROM '已确认完成' OR pending THEN
        UPDATE inspections SET quality_accept_started_at=NULL,quality_accept_deadline_at=NULL,quality_accept_policy=NULL
          WHERE id=target_id AND quality_accept_started_at IS NOT NULL;
      ELSIF rec.quality_accept_started_at IS NULL OR ready_at > rec.quality_accept_started_at THEN
        UPDATE inspections SET quality_accept_started_at=ready_at,
          quality_accept_deadline_at=ready_at + make_interval(days=>cfg.acceptance_days),quality_accept_policy=to_jsonb(cfg)
          WHERE id=target_id;
      END IF;
    END; $$ LANGUAGE plpgsql;

    CREATE OR REPLACE FUNCTION quality_issue_appeal_window() RETURNS trigger AS $$
    DECLARE ins record; cfg record;
    BEGIN
      IF NEW.quality_appeal_deadline_at IS NULL AND NEW.audit_status='approved'
          AND is_quality_deadline_table(NEW.inspection_table_id) THEN
        SELECT * INTO ins FROM inspections WHERE id=NEW.inspection_id;
        IF ins.sign_status='已签名确认' THEN
          SELECT * INTO cfg FROM quality_deadline_policy WHERE id=1;
          NEW.quality_appeal_started_at := GREATEST(ins.station_manager_signed_at AT TIME ZONE 'Asia/Shanghai',
            NEW.audited_at AT TIME ZONE 'Asia/Shanghai',cfg.activated_at);
          NEW.quality_appeal_deadline_at := NEW.quality_appeal_started_at + make_interval(days=>cfg.appeal_days);
          NEW.quality_appeal_policy := to_jsonb(cfg);
        END IF;
      END IF;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql;
    DROP TRIGGER IF EXISTS quality_issue_window ON issues;
    CREATE TRIGGER quality_issue_window BEFORE INSERT OR UPDATE ON issues FOR EACH ROW EXECUTE FUNCTION quality_issue_appeal_window();

    CREATE OR REPLACE FUNCTION quality_inspection_acceptance() RETURNS trigger AS $$
    BEGIN
      IF NEW.sign_status='已签名确认' AND OLD.sign_status IS DISTINCT FROM NEW.sign_status
          AND is_quality_deadline_table(NEW.inspection_table_id) THEN
        UPDATE issues SET quality_appeal_deadline_at=NULL WHERE inspection_id=NEW.id
          AND audit_status='approved' AND quality_appeal_deadline_at IS NULL;
      END IF;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql;
    DROP TRIGGER IF EXISTS quality_inspection_accepted ON inspections;
    CREATE TRIGGER quality_inspection_accepted AFTER UPDATE ON inspections FOR EACH ROW EXECUTE FUNCTION quality_inspection_acceptance();

    DO $$ DECLARE definition text; BEGIN
      SELECT pg_get_functiondef('log_inspection_lifecycle()'::regprocedure) INTO definition;
      IF position('app.quality_auto_accept' IN definition)=0 THEN
        definition := replace(definition, 'BEGIN',
          'BEGIN IF current_setting(''app.quality_auto_accept'',true)=''1'' THEN RETURN NEW; END IF;');
        EXECUTE definition;
      END IF;
    END $$;
    """)


def downgrade():
    op.execute('DROP TRIGGER IF EXISTS quality_issue_window ON issues; DROP TRIGGER IF EXISTS quality_inspection_accepted ON inspections;')
    # Do not erase policy snapshots, deadlines, or management responsibility evidence.
