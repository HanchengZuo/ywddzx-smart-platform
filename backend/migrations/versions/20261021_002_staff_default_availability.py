"""Keep today's automatic availability distinguishable and historically persistent."""
from pathlib import Path
from alembic import op

revision = '20261021_002'
down_revision = '20261021_001'
branch_labels = None
depends_on = None


def upgrade():
    op.execute((Path(__file__).resolve().parents[2] / 'db/init/550_staff_default_availability.sql').read_text())


def downgrade():
    # Preserve availability and its provenance when rolling application code back.
    pass
