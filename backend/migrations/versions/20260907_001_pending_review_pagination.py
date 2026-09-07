"""Small partial index for the all-time pending review queue."""
from alembic import op

revision = '20260907_001'
down_revision = '20260906_003'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_issues_pending_review_id
        ON issues (id DESC)
        WHERE status = '待复核' AND COALESCE(audit_status, 'pending') <> 'rejected'
    """)


def downgrade():
    op.execute('DROP INDEX IF EXISTS idx_issues_pending_review_id')
