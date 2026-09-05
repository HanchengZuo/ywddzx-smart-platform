"""Capture issue audit and inspection lifecycle events; retire unable status."""
from alembic import op

revision = "20260905_001"
down_revision = "20260904_001"
branch_labels = None
depends_on = None


def upgrade():
    # Backfill only facts still available in the source, never invent old decisions.
    op.execute("""
        INSERT INTO inspection_issue_flow_history
          (issue_id, action_type, to_status, result, note, actor_user_id,
           actor_username, actor_name, actor_role, created_at, event_key)
        SELECT i.id, 'audit_changed',
          CASE i.audit_status WHEN 'approved' THEN '审核通过' ELSE '审核否决' END,
          CASE i.audit_status WHEN 'approved' THEN '审核通过' ELSE '审核否决' END,
          CASE WHEN i.audit_source = 'automatic' THEN '自动审核：' || COALESCE(i.auto_audit_rule_name, '')
               ELSE '历史审核记录（仅可恢复最后一次已保存的结论）' END,
          u.id, u.username, u.real_name, u.role, i.audited_at, 'audit-backfill-' || i.id
        FROM issues i LEFT JOIN users u ON u.id = i.audited_by
        WHERE i.audited_at IS NOT NULL AND i.audit_status IN ('approved', 'rejected')
          AND NOT EXISTS (SELECT 1 FROM inspection_issue_flow_history h
                          WHERE h.issue_id = i.id AND h.action_type = 'audit_changed')
        ON CONFLICT (event_key) DO NOTHING;

        INSERT INTO inspection_issue_flow_history
          (issue_id, action_type, from_status, to_status, note, event_key)
        SELECT id, 'status_changed', status, '待整改',
          '站级无法整改状态已停用，转回待整改；原有整改复核记录保留。', 'retired-status-' || id
        FROM issues WHERE status IN ('站经无法整改','站级无法整改','站级无法完成整改','站经理无法整改')
        ON CONFLICT (event_key) DO NOTHING;
        UPDATE issues SET status = '待整改'
        WHERE status IN ('站经无法整改','站级无法整改','站级无法完成整改','站经理无法整改');

        CREATE OR REPLACE FUNCTION log_issue_lifecycle() RETURNS trigger AS $$
        DECLARE kind text; detail text; target text; actor integer;
        BEGIN
          actor := NULLIF(current_setting('app.actor_id', true), '')::integer;
          IF TG_OP = 'INSERT' THEN
            INSERT INTO inspection_issue_flow_history
              (issue_id, action_type, to_status, actor_user_id, actor_username, actor_name, actor_role, created_at)
            SELECT NEW.id, 'issue_created', '待检查人确认', u.id, u.username, u.real_name, u.role, NEW.created_at
            FROM (SELECT 1) x LEFT JOIN users u ON u.id = COALESCE(actor, NEW.inspector_id);
            RETURN NEW;
          END IF;
          IF NEW.audit_status IS DISTINCT FROM OLD.audit_status THEN
            kind := 'audit_changed';
            target := CASE NEW.audit_status WHEN 'approved' THEN '审核通过'
                      WHEN 'rejected' THEN '审核否决' ELSE '待审核' END;
            detail := CASE WHEN NEW.audit_source = 'automatic'
                      THEN '自动审核：' || COALESCE(NEW.auto_audit_rule_name, '') ELSE '人工审核' END;
            actor := COALESCE(actor, NEW.audited_by);
          ELSIF (NEW.description, NEW.standard_id, NEW.internal_standard_id, NEW.photo_path, NEW.inspector_id)
             IS DISTINCT FROM (OLD.description, OLD.standard_id, OLD.internal_standard_id, OLD.photo_path, OLD.inspector_id) THEN
            kind := 'issue_updated'; target := NEW.status; detail := '问题内容、规范、照片或检查人信息已修改。';
          ELSIF NEW.status IS DISTINCT FROM OLD.status
             AND NEW.rectification_at IS NOT DISTINCT FROM OLD.rectification_at
             AND NEW.review_at IS NOT DISTINCT FROM OLD.review_at THEN
            kind := 'status_changed'; target := NEW.status; detail := '问题流转状态调整。';
          ELSE RETURN NEW;
          END IF;
          INSERT INTO inspection_issue_flow_history
            (issue_id, action_type, from_status, to_status, result, note,
             actor_user_id, actor_username, actor_name, actor_role)
          SELECT NEW.id, kind,
            CASE WHEN kind = 'audit_changed' THEN CASE OLD.audit_status WHEN 'approved' THEN '审核通过'
                 WHEN 'rejected' THEN '审核否决' ELSE '待审核' END ELSE OLD.status END,
            target, CASE WHEN kind = 'audit_changed' THEN target END, detail,
            u.id, u.username, u.real_name, u.role
          FROM (SELECT 1) x LEFT JOIN users u ON u.id = actor;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        DROP TRIGGER IF EXISTS issue_lifecycle_changed ON issues;
        CREATE TRIGGER issue_lifecycle_changed AFTER INSERT OR UPDATE ON issues
        FOR EACH ROW EXECUTE FUNCTION log_issue_lifecycle();

        CREATE OR REPLACE FUNCTION log_inspection_lifecycle() RETURNS trigger AS $$
        DECLARE kind text; label text; actor integer;
        BEGIN
          actor := NULLIF(current_setting('app.actor_id', true), '')::integer;
          IF (NEW.sign_status, NEW.station_manager_signed_at) IS DISTINCT FROM
             (OLD.sign_status, OLD.station_manager_signed_at) THEN
            kind := 'inspection_signed'; label := CASE WHEN NEW.station_manager_signed_at IS NOT NULL
              THEN '站经理签名确认' ELSE '撤销站经理签名' END;
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
        DROP TRIGGER IF EXISTS inspection_lifecycle_changed ON inspections;
        CREATE TRIGGER inspection_lifecycle_changed AFTER UPDATE ON inspections
        FOR EACH ROW EXECUTE FUNCTION log_inspection_lifecycle();
    """)
    op.execute("""
        INSERT INTO inspection_issue_flow_history
          (issue_id, action_type, to_status, note, actor_name, created_at, event_key)
        SELECT i.id, 'inspection_signed', '站经理签名确认', '历史签名记录', ins.station_manager_signed_name,
          ins.station_manager_signed_at, 'signed-backfill-' || i.id
        FROM issues i JOIN inspections ins ON ins.id = i.inspection_id
        WHERE ins.station_manager_signed_at IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM inspection_issue_flow_history h
                          WHERE h.issue_id = i.id AND h.action_type = 'inspection_signed')
        ON CONFLICT (event_key) DO NOTHING;
        INSERT INTO inspection_issue_flow_history
          (issue_id, action_type, to_status, note, created_at, event_key)
        SELECT i.id, 'inspection_completed', '巡检完成确认', '历史巡检完成记录',
          ins.inspector_completed_at, 'completed-backfill-' || i.id
        FROM issues i JOIN inspections ins ON ins.id = i.inspection_id
        WHERE ins.inspector_completed_at IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM inspection_issue_flow_history h
                          WHERE h.issue_id = i.id AND h.action_type = 'inspection_completed')
        ON CONFLICT (event_key) DO NOTHING;
    """)


def downgrade():
    op.execute("""
        DROP TRIGGER IF EXISTS issue_lifecycle_changed ON issues;
        DROP TRIGGER IF EXISTS inspection_lifecycle_changed ON inspections;
        DROP FUNCTION IF EXISTS log_issue_lifecycle();
        DROP FUNCTION IF EXISTS log_inspection_lifecycle();
    """)
    # Keep audit evidence and current business state intact on rollback.
