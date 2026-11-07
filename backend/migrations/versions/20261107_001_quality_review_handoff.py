"""Route the current review round to Quality Safety after an explicit handoff."""
from alembic import op

revision = '20261107_001'
down_revision = '20261105_001'
branch_labels = depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE issues ADD COLUMN quality_review_handoff_id bigint
            REFERENCES inspection_issue_flow_history(id) ON DELETE SET NULL;
        CREATE INDEX idx_issues_quality_review_handoff ON issues (id DESC)
            WHERE quality_review_handoff_id IS NOT NULL AND status = '待复核';

        CREATE FUNCTION clear_quality_review_handoff() RETURNS trigger AS $$
        BEGIN
            IF NEW.quality_review_handoff_id IS NOT NULL AND (
                NEW.status IS DISTINCT FROM OLD.status
                OR NEW.rectification_at IS DISTINCT FROM OLD.rectification_at
                OR NEW.rectification_result IS DISTINCT FROM OLD.rectification_result
                OR NEW.inspection_table_id IS DISTINCT FROM OLD.inspection_table_id
                OR NEW.audit_status IS DISTINCT FROM OLD.audit_status
            ) THEN
                NEW.quality_review_handoff_id := NULL;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER issues_clear_quality_review_handoff
            BEFORE UPDATE OF status, rectification_at, rectification_result, inspection_table_id, audit_status
            ON issues FOR EACH ROW EXECUTE FUNCTION clear_quality_review_handoff();
    """)


def downgrade():
    op.execute("""
        DROP TRIGGER issues_clear_quality_review_handoff ON issues;
        DROP FUNCTION clear_quality_review_handoff();
        DROP INDEX idx_issues_quality_review_handoff;
        ALTER TABLE issues DROP COLUMN quality_review_handoff_id;
    """)
