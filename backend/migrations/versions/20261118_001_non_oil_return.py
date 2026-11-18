"""Keep department rejections pending until the owning area returns them to station."""
from alembic import op

revision = '20261118_001'
down_revision = '20261108_001'
branch_labels = depends_on = None


def upgrade():
    op.execute("""ALTER TABLE issues DROP CONSTRAINT issue_non_oil_review_stage_check;
        ALTER TABLE issues ADD CONSTRAINT issue_non_oil_review_stage_check CHECK (
            (non_oil_review_stage IS NULL) = (non_oil_review_event_id IS NULL)
            AND (non_oil_review_stage IS NULL OR non_oil_review_stage IN ('area','department','field','area_return')));
    """)


def downgrade():
    op.execute("""UPDATE issues SET non_oil_review_stage='area' WHERE non_oil_review_stage='area_return';
        ALTER TABLE issues DROP CONSTRAINT issue_non_oil_review_stage_check;
        ALTER TABLE issues ADD CONSTRAINT issue_non_oil_review_stage_check CHECK (
            (non_oil_review_stage IS NULL) = (non_oil_review_event_id IS NULL)
            AND (non_oil_review_stage IS NULL OR non_oil_review_stage IN ('area','department','field')));
    """)
