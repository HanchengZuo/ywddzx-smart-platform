"""Two-stage station appeals with lifecycle evidence."""
from alembic import op

revision = '20260905_003'
down_revision = '20260905_002'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
      CREATE TABLE IF NOT EXISTS inspection_issue_appeals (
        id SERIAL PRIMARY KEY,
        issue_id INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
        status VARCHAR(24) NOT NULL CHECK (status IN ('area_pending','quality_pending','approved','rejected','cancelled')),
        reason TEXT NOT NULL CHECK (length(trim(reason)) BETWEEN 1 AND 4000),
        submitted_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        area_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        area_reason TEXT,
        area_at TIMESTAMPTZ,
        quality_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        quality_reason TEXT,
        quality_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
      );
      CREATE UNIQUE INDEX IF NOT EXISTS uq_issue_active_appeal ON inspection_issue_appeals(issue_id)
        WHERE status IN ('area_pending','quality_pending');
      CREATE INDEX IF NOT EXISTS idx_issue_appeals_status ON inspection_issue_appeals(status, id DESC);
      CREATE INDEX IF NOT EXISTS idx_issue_appeals_issue ON inspection_issue_appeals(issue_id);
      CREATE OR REPLACE FUNCTION cancel_reset_issue_appeals() RETURNS trigger AS $$
      DECLARE affected integer; actor integer;
      BEGIN
        IF OLD.status = '申诉中' AND NEW.status = '申诉中' AND NEW.audit_status IS DISTINCT FROM OLD.audit_status THEN
          NEW.status := CASE WHEN NEW.audit_status = 'rejected' THEN '已销毁' ELSE '待整改' END;
        END IF;
        IF OLD.status = '申诉中' AND (NEW.status <> '申诉中' OR NEW.audit_status IS DISTINCT FROM OLD.audit_status) THEN
          UPDATE inspection_issue_appeals SET status='cancelled', updated_at=CURRENT_TIMESTAMP
            WHERE issue_id=NEW.id AND status IN ('area_pending','quality_pending');
          GET DIAGNOSTICS affected = ROW_COUNT;
          IF affected > 0 THEN
            actor := NULLIF(current_setting('app.actor_id', true), '')::integer;
            INSERT INTO inspection_issue_flow_history
              (issue_id,action_type,from_status,to_status,result,note,actor_user_id,actor_username,actor_name,actor_role)
            SELECT NEW.id,'appeal_cancelled','申诉中',NEW.status,'申诉取消',
              '巡检重置或问题审核状态变化，当前申诉已取消，按最新问题状态继续处理。',u.id,u.username,u.real_name,u.role
            FROM (SELECT 1) seed LEFT JOIN users u ON u.id=actor;
          END IF;
        END IF;
        RETURN NEW;
      END; $$ LANGUAGE plpgsql;
      DROP TRIGGER IF EXISTS issue_appeal_reset ON issues;
      CREATE TRIGGER issue_appeal_reset BEFORE UPDATE ON issues FOR EACH ROW EXECUTE FUNCTION cancel_reset_issue_appeals();
    """)


def downgrade():
    # Evidence is retained; pending appeals must be resolved before rolling code back.
    op.execute("DROP TRIGGER IF EXISTS issue_appeal_reset ON issues; DROP FUNCTION IF EXISTS cancel_reset_issue_appeals();")
