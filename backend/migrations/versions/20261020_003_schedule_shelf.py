"""Durable shared dispatch shelf, separate from active station plans."""
from pathlib import Path
from alembic import op

revision = '20261020_003'
down_revision = '20261020_002'
branch_labels = None
depends_on = None


def upgrade():
    op.execute((Path(__file__).resolve().parents[2] / 'db/init/535_schedule_shelf.sql').read_text())


def downgrade():
    # Keep parked plans and dispatch accountability on application rollback.
    pass
