"""Audit rejection state and inspection reset lifecycle wording."""
from alembic import op

revision = '20260905_002'
down_revision = '20260905_001'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE OR REPLACE FUNCTION sync_issue_audit_state() RETURNS trigger AS $$
        BEGIN
          IF NEW.audit_status = 'rejected' THEN NEW.status := '已销毁';
          ELSIF TG_OP = 'UPDATE' AND OLD.audit_status = 'rejected' AND NEW.status = '已销毁'
            THEN NEW.status := '待整改';
          END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        DROP TRIGGER IF EXISTS issue_audit_state ON issues;
        CREATE TRIGGER issue_audit_state BEFORE INSERT OR UPDATE ON issues
          FOR EACH ROW EXECUTE FUNCTION sync_issue_audit_state();
        UPDATE issues SET status = '已销毁' WHERE audit_status = 'rejected' AND status IS DISTINCT FROM '已销毁';
        UPDATE issues SET status = '站级无法整改' WHERE status = '站经无法整改' AND audit_status <> 'rejected';
        UPDATE issues SET review_result = '整改通过' WHERE review_result = '已整改';

        DO $$ DECLARE definition text; BEGIN
          SELECT pg_get_functiondef('log_issue_lifecycle()'::regprocedure) INTO definition;
          definition := replace(definition, 'ELSE ''人工审核'' END;',
            'ELSE CASE WHEN current_setting(''app.lifecycle_context'', true) = ''inspection_reset'' THEN ''巡检记录重置，审核恢复待审核'' ELSE ''人工审核'' END END;');
          EXECUTE definition;
        END $$;

        CREATE OR REPLACE FUNCTION log_inspection_lifecycle() RETURNS trigger AS $$
        DECLARE kind text; label text; actor integer;
        BEGIN
          actor := NULLIF(current_setting('app.actor_id', true), '')::integer;
          IF NEW.inspector_completion_status IS DISTINCT FROM OLD.inspector_completion_status
             AND NEW.inspector_completion_status = '待检查人确认' THEN
            kind := 'inspection_reset'; label := '巡检记录已重置，恢复等待检查人确认';
          ELSIF (NEW.sign_status, NEW.station_manager_signed_at) IS DISTINCT FROM
                (OLD.sign_status, OLD.station_manager_signed_at) THEN
            kind := 'inspection_signed'; label := CASE WHEN NEW.station_manager_signed_at IS NOT NULL
              THEN '站经理签名确认' ELSE '撤销站经理签名，恢复等待签名' END;
          ELSIF (NEW.inspector_completion_status, NEW.inspector_completed_at) IS DISTINCT FROM
                (OLD.inspector_completion_status, OLD.inspector_completed_at) THEN
            kind := 'inspection_completed'; label := '巡检完成状态：' || COALESCE(NEW.inspector_completion_status, '待确认');
            actor := COALESCE(actor, NEW.inspector_completed_by);
          ELSE RETURN NEW;
          END IF;
          INSERT INTO inspection_issue_flow_history
            (issue_id, action_type, to_status, note, actor_user_id, actor_username, actor_name, actor_role)
          SELECT i.id, kind, label, label, u.id, u.username,
            COALESCE(u.real_name, CASE WHEN kind = 'inspection_signed' THEN NEW.station_manager_signed_name END), u.role
          FROM issues i LEFT JOIN users u ON u.id = actor WHERE i.inspection_id = NEW.id;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql;
    """)


def downgrade():
    op.execute('DROP TRIGGER IF EXISTS issue_audit_state ON issues; DROP FUNCTION IF EXISTS sync_issue_audit_state();')
    # Preserve lifecycle evidence and current business states; do not reopen closed issues.
