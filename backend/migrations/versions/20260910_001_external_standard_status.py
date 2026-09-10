"""Persist external standard availability without altering historical issues."""
from alembic import op

revision = '20260910_001'
down_revision = '20260909_002'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE IF NOT EXISTS external_standard_status (
      standard_id bigint PRIMARY KEY,
      is_active boolean NOT NULL DEFAULT true,
      updated_by integer,
      updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
    )''')


def downgrade():
    # Preserve disabled states so rollback cannot silently reactivate standards.
    pass
