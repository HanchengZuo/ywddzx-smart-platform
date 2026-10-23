"""Retain station-level video task exceptions and their original dispatch evidence."""
from pathlib import Path
from alembic import op

revision = '20261023_001'
down_revision = '20261022_003'
branch_labels = None
depends_on = None


def upgrade():
    op.execute((Path(__file__).resolve().parents[2] / 'db/init/570_video_task_exceptions.sql').read_text())


def downgrade():
    # Do not discard responsibility/audit evidence on an application rollback.
    pass
