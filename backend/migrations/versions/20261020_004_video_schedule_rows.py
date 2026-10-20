"""Consolidate legacy video waiting cards into station-level assignments."""
from pathlib import Path
from alembic import op

revision = '20261020_004'
down_revision = '20261020_003'
branch_labels = None
depends_on = None


def upgrade():
    op.execute((Path(__file__).resolve().parents[2] / 'db/init/540_video_schedule_rows.sql').read_text())


def downgrade():
    # Keep consolidated cards and the complete upgrade audit trail.
    pass
