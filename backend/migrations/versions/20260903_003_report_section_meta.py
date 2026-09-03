"""Record the last operator of each shared report configuration section."""

from alembic import op

revision = "20260903_003"
down_revision = "20260903_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE inspection_report_workspaces
        ADD COLUMN IF NOT EXISTS section_meta JSONB NOT NULL DEFAULT '{}'::jsonb
    """)


def downgrade():
    # Retain audit metadata if application code is rolled back.
    pass
