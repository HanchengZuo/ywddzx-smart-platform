"""Cockpit-authorized expert Q&A job history. No new permission or business data changes."""
from alembic import op

revision = '20261013_001'
down_revision = '20260927_001'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE IF NOT EXISTS expert_qa_questions(
        id VARCHAR(32) PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        session_key VARCHAR(64) NOT NULL,
        question TEXT NOT NULL,
        options JSONB NOT NULL DEFAULT '{}'::jsonb,
        status TEXT NOT NULL CHECK(status IN ('queued','retrieving','answering','completed','failed')),
        result JSONB,
        error_message TEXT NOT NULL DEFAULT '',
        cache_key VARCHAR(64),
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )''')
    op.execute('CREATE INDEX IF NOT EXISTS idx_expert_qa_user_time ON expert_qa_questions(user_id,created_at DESC)')
    op.execute("CREATE INDEX IF NOT EXISTS idx_expert_qa_cache ON expert_qa_questions(user_id,cache_key) WHERE status='completed'")


def downgrade():
    # Preserve paid answers and history on a code rollback; removal is an administrator decision.
    pass
