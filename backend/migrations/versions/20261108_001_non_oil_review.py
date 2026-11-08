"""Track the current non-oil review stage without rewriting historical results."""
from alembic import op

revision = '20261108_001'
down_revision = '20261107_001'
branch_labels = depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE issues ADD COLUMN non_oil_review_stage text,
            ADD COLUMN non_oil_review_event_id bigint,
            ADD CONSTRAINT issue_non_oil_review_stage_check CHECK (
                (non_oil_review_stage IS NULL) = (non_oil_review_event_id IS NULL)
                AND (non_oil_review_stage IS NULL OR non_oil_review_stage IN ('area', 'department', 'field'))
            );
        CREATE FUNCTION clear_non_oil_review_stage() RETURNS trigger AS $$
        BEGIN
            IF NEW.status IS DISTINCT FROM OLD.status
               OR NEW.rectification_at IS DISTINCT FROM OLD.rectification_at
               OR NEW.rectification_result IS DISTINCT FROM OLD.rectification_result
               OR NEW.inspection_table_id IS DISTINCT FROM OLD.inspection_table_id
               OR NEW.audit_status IS DISTINCT FROM OLD.audit_status THEN
                NEW.non_oil_review_stage := NULL;
                NEW.non_oil_review_event_id := NULL;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER issues_clear_non_oil_review_stage
            BEFORE UPDATE OF status, rectification_at, rectification_result, inspection_table_id, audit_status
            ON issues FOR EACH ROW EXECUTE FUNCTION clear_non_oil_review_stage();
    """)


def downgrade():
    op.execute("""
        DROP TRIGGER issues_clear_non_oil_review_stage ON issues;
        DROP FUNCTION clear_non_oil_review_stage();
        ALTER TABLE issues DROP CONSTRAINT issue_non_oil_review_stage_check,
            DROP COLUMN non_oil_review_stage, DROP COLUMN non_oil_review_event_id;
    """)
