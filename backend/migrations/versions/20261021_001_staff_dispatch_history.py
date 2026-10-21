"""Immutable dispatch evidence and indexed staff history lookups."""
from pathlib import Path
from alembic import op

revision = '20261021_001'
down_revision = '20261020_004'
branch_labels = None
depends_on = None


def upgrade():
    op.execute((Path(__file__).resolve().parents[2] / 'db/init/545_staff_dispatch_history.sql').read_text())


def downgrade():
    # Retain original dispatch evidence when rolling back application code.
    pass
