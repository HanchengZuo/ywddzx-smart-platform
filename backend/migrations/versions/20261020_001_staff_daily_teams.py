"""Editable staff history and shared daily leader/student teams."""
from pathlib import Path
from alembic import op

revision = '20261020_001'
down_revision = '20261019_003'
branch_labels = None
depends_on = None


def upgrade():
    op.execute((Path(__file__).resolve().parents[2] / 'db/init/525_staff_daily_teams.sql').read_text())


def downgrade():
    # Preserve manual history and dispatch accountability on code rollback.
    pass
