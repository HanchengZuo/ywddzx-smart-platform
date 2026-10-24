"""Separate department readers from the full report workbench."""
from pathlib import Path
from alembic import op

revision = '20261025_001'
down_revision = '20261024_001'
branch_labels = None
depends_on = None


def upgrade():
    op.execute((Path(__file__).resolve().parents[2] / 'db/init/575_report_perspectives.sql').read_text())


def downgrade():
    # Never silently restore broader access on an application rollback.
    pass
