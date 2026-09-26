"""Grant cockpit access to departments and areas without changing business scopes."""
from alembic import op

revision = '20260927_001'
down_revision = '20260923_001'
branch_labels = None
depends_on = None


def upgrade():
    # Explicit role/user denials remain authoritative, including after a repeated upgrade.
    op.execute("""INSERT INTO role_permissions(role,permission_key,is_allowed)
      SELECT role, 'view_operations_overview', TRUE FROM unnest(ARRAY[
        'quality_safety','development_plan','oil_gas','non_oil','finance','area_account'
      ]) AS role ON CONFLICT(role,permission_key) DO NOTHING""")


def downgrade():
    # Preserve administrator choices; revoke this read-only grant in permission management if needed.
    pass
