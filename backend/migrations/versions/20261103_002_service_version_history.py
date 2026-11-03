"""Correct the pre-versioning service IDs and preserve the original evidence."""
from alembic import op
from psycopg2.extras import RealDictCursor

revision = '20261103_002'
down_revision = '20261103_001'
branch_labels = depends_on = None


def upgrade():
    from checklist_service_history import correct_history
    with op.get_bind().connection.driver_connection.cursor(cursor_factory=RealDictCursor) as cur:
        correct_history(cur)


def downgrade():
    pass  # Do not silently undo a user-approved data correction or discard its audit.
