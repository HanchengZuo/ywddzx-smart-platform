"""Shared station targets for smart planning and deduplicated dispatch shelves."""
from pathlib import Path
from alembic import op

revision = '20261022_003'
down_revision = '20261022_002'
branch_labels = None
depends_on = None


def upgrade():
    op.execute((Path(__file__).resolve().parents[2] / 'db/init/565_schedule_dispatch_quotas.sql').read_text())


def downgrade():
    # Retain shared settings and audit history.
    pass
