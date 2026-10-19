"""Independent station enrollment switches for on-site and video scheduling."""
from alembic import op
from station_plan_eligibility import SCHEMA_SQL

revision = '20261019_001'
down_revision = '20261018_002'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(SCHEMA_SQL)


def downgrade():
    # Keep administrator choices and historical plan commitments on application rollback.
    pass
