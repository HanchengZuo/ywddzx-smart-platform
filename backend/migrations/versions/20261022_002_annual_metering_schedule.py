"""Annual metering schedule and monthly regional quotas."""
from pathlib import Path
from alembic import op

revision = '20261022_002'
down_revision = '20261022_001'
branch_labels = None
depends_on = None


def upgrade():
    op.execute((Path(__file__).resolve().parents[2] / 'db/init/560_annual_metering_schedule.sql').read_text())


def downgrade():
    # Keep planning and audit history; older releases simply ignore annual entries.
    pass
