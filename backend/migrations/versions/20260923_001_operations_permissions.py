"""Initial BI grants only for supervisors; preserve later administrator overrides."""
from alembic import op

revision = '20260923_001'
down_revision = '20260920_001'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""INSERT INTO role_permissions(role,permission_key,is_allowed)
      SELECT 'supervisor', key, TRUE FROM unnest(ARRAY[
        'view_operations_overview','view_operations_rectification','view_operations_insights'
      ]) AS key ON CONFLICT(role,permission_key) DO NOTHING""")


def downgrade():
    # Do not erase grants/denials subsequently edited by administrators.
    pass
