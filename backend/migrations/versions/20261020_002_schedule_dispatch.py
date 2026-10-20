"""Team plan snapshots and separately expiring field tasks."""
from pathlib import Path
from alembic import op

revision = '20261020_002'
down_revision = '20261020_001'
branch_labels = None
depends_on = None


def upgrade():
    op.execute((Path(__file__).resolve().parents[2] / 'db/init/530_schedule_dispatch.sql').read_text())


def downgrade():
    # Keep dispatch history and snapshots when rolling application code back.
    pass
