"""Checklist editions preserve structures, originals and historical identities."""
from alembic import op
from psycopg2.extras import RealDictCursor

revision = '20261103_001'
down_revision = '20261102_002'
branch_labels = depends_on = None


def upgrade():
    from checklist_version_migration import install
    with op.get_bind().connection.driver_connection.cursor(cursor_factory=RealDictCursor) as cur:
        install(cur)


def downgrade():
    pass  # Never discard historical versions or detach existing business records.
