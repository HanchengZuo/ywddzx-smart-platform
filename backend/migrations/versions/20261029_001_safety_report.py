"""Global safety PPT source and editable analysis selections, separate from snapshots."""
from alembic import op
revision = '20261029_001'
down_revision = '20261025_002'
branch_labels = depends_on = None


def upgrade():
    op.execute('''CREATE TABLE IF NOT EXISTS inspection_report_safety_settings (
        id INTEGER PRIMARY KEY CHECK(id=1), settings JSONB NOT NULL DEFAULT '{}'::jsonb,
        revision INTEGER NOT NULL DEFAULT 0, updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        updated_by_name TEXT NOT NULL DEFAULT '', updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )''')
    op.execute('''CREATE INDEX IF NOT EXISTS idx_safety_analysis_evidence
        ON inspection_report_ai_memory(issue_ids, (payload->>'analysis_scope'), created_at DESC)
        WHERE report_type='safety_quality' AND operation='safety_detail' ''')


def downgrade():
    # Do not discard shared manual decisions during a code rollback.
    pass
