"""Keep the revision applied by the canceled HTML prototype resolvable.

Some local databases ran that migration before its uncommitted code was
discarded. Leave any prototype tables untouched; no active feature uses them.
Fresh databases only need this compatibility marker, not the retired schema.
"""

revision = '20261024_001'
down_revision = '20261023_001'
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
