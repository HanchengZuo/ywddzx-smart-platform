"""Persist successful report AI outputs and per-generation audit information."""

from alembic import op

revision = "20260903_001"
down_revision = "20260902_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS inspection_report_ai_memory (
            cache_key VARCHAR(64) PRIMARY KEY,
            operation VARCHAR(64) NOT NULL,
            report_type VARCHAR(64) NOT NULL,
            issue_ids BIGINT[] NOT NULL,
            payload JSONB NOT NULL,
            model VARCHAR(100) NOT NULL,
            source_task_id VARCHAR(64) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_report_ai_memory_created ON inspection_report_ai_memory (created_at)")
    op.execute("""
        ALTER TABLE inspection_report_jobs
        ADD COLUMN IF NOT EXISTS ai_generation_log JSONB NOT NULL DEFAULT '{}'::jsonb
    """)


def downgrade():
    op.execute("ALTER TABLE inspection_report_jobs DROP COLUMN IF EXISTS ai_generation_log")
    op.execute("DROP TABLE IF EXISTS inspection_report_ai_memory")
