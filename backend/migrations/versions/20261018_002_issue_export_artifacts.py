"""Shared content-addressed issue Excel exports with per-user task ownership."""
from alembic import op
from issue_export_cache import BASE_SCHEMA_SQL, SCHEMA_SQL

revision = '20261018_002'
down_revision = '20261018_001'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(BASE_SCHEMA_SQL)
    op.execute(SCHEMA_SQL)


def downgrade():
    # Keep shared files and task references: removing them would invalidate live downloads.
    pass
