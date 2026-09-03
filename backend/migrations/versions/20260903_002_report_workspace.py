"""Remember current report settings separately from generated report snapshots."""

from alembic import op

revision = "20260903_002"
down_revision = "20260903_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS inspection_report_workspaces (
            report_type TEXT PRIMARY KEY,
            generation_options JSONB NOT NULL DEFAULT '{}'::jsonb,
            revision BIGINT NOT NULL DEFAULT 0,
            updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            updated_by_name TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        ALTER TABLE inspection_report_jobs
        ADD COLUMN IF NOT EXISTS requested_by_name TEXT NOT NULL DEFAULT ''
    """)
    op.execute("""
        UPDATE inspection_report_jobs j
        SET requested_by_name = COALESCE(NULLIF(u.real_name, ''), u.username, '')
        FROM users u
        WHERE u.id = j.requested_by AND j.requested_by_name = ''
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_report_jobs_type_requested
        ON inspection_report_jobs (report_type, created_at DESC)
    """)


def downgrade():
    # Preserve saved user choices and audit identities when rolling code back.
    pass
