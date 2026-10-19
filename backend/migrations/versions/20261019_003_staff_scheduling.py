"""Dated dispatch, official-workday availability and durable personal tasks."""
from pathlib import Path
from alembic import op

revision = '20261019_003'
down_revision = '20261019_002'
branch_labels = None
depends_on = None


def upgrade():
    op.execute((Path(__file__).resolve().parents[2] / 'db/init/520_staff_scheduling.sql').read_text())


def downgrade():
    # Keep dispatch and accountability history on application rollback.
    pass
