"""Default-denied driving eligibility for supervised field teams."""
from pathlib import Path
from alembic import op

revision = '20261022_001'
down_revision = '20261021_002'
branch_labels = None
depends_on = None


def upgrade():
    op.execute((Path(__file__).resolve().parents[2] / 'db/init/555_user_driving_permits.sql').read_text())


def downgrade():
    # Preserve maintained account qualifications and historical team evidence.
    pass
