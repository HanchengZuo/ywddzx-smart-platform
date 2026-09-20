"""Independent, shared equipment report issue selection."""
from alembic import op

revision = '20260916_001'
down_revision = '20260910_001'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE IF NOT EXISTS inspection_report_equipment_issue_selections (
        issue_id bigint PRIMARY KEY REFERENCES issues(id) ON DELETE CASCADE,
        updated_by integer,
        updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
    )''')


def downgrade():
    # Preserve saved selections on code rollback.
    pass
