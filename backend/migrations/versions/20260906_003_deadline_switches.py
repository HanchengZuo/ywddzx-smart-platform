"""Independent live switches and database-wide low-frequency scan scheduling."""
from alembic import op

revision = '20260906_003'
down_revision = '20260906_002'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    ALTER TABLE quality_deadline_policy ADD COLUMN IF NOT EXISTS acceptance_enabled boolean NOT NULL DEFAULT true;
    ALTER TABLE quality_deadline_policy ADD COLUMN IF NOT EXISTS appeal_enabled boolean NOT NULL DEFAULT true;
    ALTER TABLE quality_deadline_policy ADD COLUMN IF NOT EXISTS review_enabled boolean NOT NULL DEFAULT true;
    ALTER TABLE quality_deadline_policy ADD COLUMN IF NOT EXISTS acceptance_enabled_at timestamptz;
    ALTER TABLE quality_deadline_policy ADD COLUMN IF NOT EXISTS appeal_enabled_at timestamptz;
    ALTER TABLE quality_deadline_policy ADD COLUMN IF NOT EXISTS review_enabled_at timestamptz;
    ALTER TABLE quality_deadline_policy ADD COLUMN IF NOT EXISTS acceptance_enabled_policy jsonb;
    ALTER TABLE quality_deadline_policy ADD COLUMN IF NOT EXISTS appeal_enabled_policy jsonb;
    ALTER TABLE quality_deadline_policy ADD COLUMN IF NOT EXISTS review_enabled_policy jsonb;
    UPDATE quality_deadline_policy SET
      acceptance_enabled_at=COALESCE(acceptance_enabled_at,activated_at),
      appeal_enabled_at=COALESCE(appeal_enabled_at,activated_at),
      review_enabled_at=COALESCE(review_enabled_at,activated_at),
      acceptance_enabled_policy=COALESCE(acceptance_enabled_policy,jsonb_build_object('acceptance_days',acceptance_days,'version',version)),
      appeal_enabled_policy=COALESCE(appeal_enabled_policy,jsonb_build_object('appeal_days',appeal_days,'version',version)),
      review_enabled_policy=COALESCE(review_enabled_policy,jsonb_build_object('review_days',review_days,'timeout_action',timeout_action,'version',version));
    ALTER TABLE quality_deadline_worker_state ADD COLUMN IF NOT EXISTS next_scan_at timestamptz;

    CREATE OR REPLACE FUNCTION quality_effective_deadline(phase text, deadline timestamptz, started timestamptz)
    RETURNS timestamptz AS $$
    DECLARE cfg jsonb; enabled_at timestamptz;
    BEGIN
      SELECT to_jsonb(p) INTO cfg FROM quality_deadline_policy p WHERE id=1;
      IF NOT COALESCE((cfg->>(phase || '_enabled'))::boolean,false) THEN RETURN NULL; END IF;
      enabled_at := (cfg->>(phase || '_enabled_at'))::timestamptz;
      IF started IS NULL OR started < enabled_at THEN
        RETURN enabled_at + make_interval(days=>(cfg->(phase || '_enabled_policy')->>(phase || '_days'))::integer);
      END IF;
      RETURN deadline;
    END; $$ LANGUAGE plpgsql STABLE;

    CREATE OR REPLACE FUNCTION refresh_quality_acceptance(target_id integer) RETURNS void AS $$
    DECLARE rec record; cfg record; ready_at timestamptz; pending boolean;
    BEGIN
      SELECT * INTO cfg FROM quality_deadline_policy WHERE id=1;
      IF NOT cfg.acceptance_enabled THEN RETURN; END IF;
      SELECT * INTO rec FROM inspections WHERE id=target_id FOR UPDATE;
      IF NOT FOUND OR NOT is_quality_deadline_table(rec.inspection_table_id) THEN RETURN; END IF;
      IF rec.sign_status='已签名确认' THEN RETURN; END IF;
      SELECT COALESCE(bool_or(COALESCE(audit_status,'pending')='pending'),false),
        GREATEST(max(audited_at AT TIME ZONE 'Asia/Shanghai'), rec.inspector_completed_at AT TIME ZONE 'Asia/Shanghai', cfg.acceptance_enabled_at)
        INTO pending,ready_at FROM issues WHERE inspection_id=target_id;
      IF rec.inspector_completion_status IS DISTINCT FROM '已确认完成' OR pending THEN
        UPDATE inspections SET quality_accept_started_at=NULL,quality_accept_deadline_at=NULL,quality_accept_policy=NULL
          WHERE id=target_id AND quality_accept_started_at IS NOT NULL;
      ELSIF rec.quality_accept_started_at IS NULL OR ready_at > rec.quality_accept_started_at THEN
        UPDATE inspections SET quality_accept_started_at=ready_at,
          quality_accept_deadline_at=ready_at + make_interval(days=>CASE WHEN ready_at=cfg.acceptance_enabled_at THEN (cfg.acceptance_enabled_policy->>'acceptance_days')::integer ELSE cfg.acceptance_days END),
          quality_accept_policy=CASE WHEN ready_at=cfg.acceptance_enabled_at THEN to_jsonb(cfg)||cfg.acceptance_enabled_policy ELSE to_jsonb(cfg) END
          WHERE id=target_id;
      END IF;
    END; $$ LANGUAGE plpgsql;

    CREATE OR REPLACE FUNCTION quality_issue_appeal_window() RETURNS trigger AS $$
    DECLARE ins record; cfg record;
    BEGIN
      SELECT * INTO cfg FROM quality_deadline_policy WHERE id=1;
      IF cfg.appeal_enabled AND (NEW.quality_appeal_deadline_at IS NULL OR NEW.quality_appeal_started_at < cfg.appeal_enabled_at)
          AND NEW.audit_status='approved' AND is_quality_deadline_table(NEW.inspection_table_id) THEN
        SELECT * INTO ins FROM inspections WHERE id=NEW.inspection_id;
        IF ins.sign_status='已签名确认' THEN
          NEW.quality_appeal_started_at := GREATEST(ins.station_manager_signed_at AT TIME ZONE 'Asia/Shanghai',
            NEW.audited_at AT TIME ZONE 'Asia/Shanghai',cfg.appeal_enabled_at);
          NEW.quality_appeal_policy := CASE WHEN NEW.quality_appeal_started_at=cfg.appeal_enabled_at THEN to_jsonb(cfg)||cfg.appeal_enabled_policy ELSE to_jsonb(cfg) END;
          NEW.quality_appeal_deadline_at := NEW.quality_appeal_started_at + make_interval(days=>(NEW.quality_appeal_policy->>'appeal_days')::integer);
        END IF;
      END IF;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql;
    """)


def downgrade():
    # Keep switch state and audit evidence. Roll back the application only after stopping workers.
    pass
