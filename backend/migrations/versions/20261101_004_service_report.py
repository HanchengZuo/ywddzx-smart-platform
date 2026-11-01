"""Shared first-chapter service report settings; retain decisions on rollback."""
from alembic import op
revision = '20261101_004'
down_revision = '20261101_003'
branch_labels = depends_on = None

def upgrade():
    op.execute('''CREATE TABLE IF NOT EXISTS inspection_report_service_settings (
        id INTEGER PRIMARY KEY CHECK(id=1), settings JSONB NOT NULL DEFAULT '{}'::jsonb,
        revision INTEGER NOT NULL DEFAULT 0, updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        updated_by_name TEXT NOT NULL DEFAULT '', updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )''')

def downgrade():
    pass
