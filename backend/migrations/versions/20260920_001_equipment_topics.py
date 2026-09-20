"""Shared manual topic choices; retain on rollback."""
from alembic import op
revision = '20260920_001'
down_revision = '20260916_001'
branch_labels = None
depends_on = None

def upgrade():
    op.execute('''CREATE TABLE IF NOT EXISTS inspection_report_equipment_topic_selections (
        kind text NOT NULL CHECK(kind IN ('special','severe')),
        issue_id bigint NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
        selected boolean NOT NULL,
        updated_by integer,
        updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(kind,issue_id)
    )''')

def downgrade():
    pass
