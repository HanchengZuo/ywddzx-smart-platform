"""Persist station-pair driving estimates independently of scheduling requests."""
from pathlib import Path
from alembic import op

revision = '20261025_002'
down_revision = '20261025_001'
branch_labels = None
depends_on = None


def upgrade():
    op.execute((Path(__file__).resolve().parents[2] / 'db/init/580_driving_matrix.sql').read_text())


def downgrade():
    # Do not delete the road database or planning evidence on code rollback.
    pass
