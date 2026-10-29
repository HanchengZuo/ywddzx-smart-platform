"""Persistent, source-versioned safety requirements and shared manual overrides."""
from alembic import op

revision = '20261030_001'
down_revision = '20261029_001'
branch_labels = depends_on = None


def upgrade():
    op.execute('''CREATE TABLE IF NOT EXISTS inspection_report_safety_requirements (
        standard_key TEXT NOT NULL,
        source_signature TEXT NOT NULL CHECK (length(source_signature) = 64),
        mode TEXT NOT NULL CHECK (mode IN ('onsite', 'video')),
        external_standard_id TEXT NOT NULL,
        fields JSONB NOT NULL CHECK (jsonb_typeof(fields) = 'object'),
        ai_requirement TEXT NOT NULL DEFAULT '',
        manual_requirement TEXT CHECK (manual_requirement IS NULL OR length(btrim(manual_requirement)) > 0),
        revision BIGINT NOT NULL DEFAULT 1 CHECK (revision > 0),
        updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        updated_by_name TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (standard_key, source_signature)
    )''')
    op.execute('''DO $$ BEGIN
        IF to_regclass('inspection_report_ai_memory') IS NOT NULL THEN
            CREATE INDEX IF NOT EXISTS idx_safety_representative_signature
                ON inspection_report_ai_memory ((payload->>'selection_signature'), created_at DESC)
                WHERE report_type='safety_quality' AND operation='safety_examples';
        END IF;
    END $$''')


def downgrade():
    # Retain generated text, source versions and shared manual decisions on rollback.
    pass
