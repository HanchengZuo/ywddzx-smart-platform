"""Remove the retired photo-export permission without changing data scopes."""
from alembic import op

revision = '20261016_001'
down_revision = '20261013_001'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DELETE FROM user_permissions WHERE permission_key = 'export_issue_photos'")
    op.execute("DELETE FROM role_permissions WHERE permission_key = 'export_issue_photos'")


def downgrade():
    # Old grants/denials cannot be reconstructed; never invent administrator choices.
    pass
