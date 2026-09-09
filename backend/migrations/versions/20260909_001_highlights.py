"""Independent highlight registration and audit history."""
from alembic import op

revision = '20260909_001'
down_revision = '20260907_001'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE IF NOT EXISTS inspection_highlights (
      id BIGSERIAL PRIMARY KEY,
      station_id INTEGER NOT NULL REFERENCES stations(id),
      inspector_id INTEGER NOT NULL REFERENCES users(id),
      inspection_table_id INTEGER NOT NULL REFERENCES inspection_tables(id),
      description TEXT NOT NULL,
      photo_path TEXT NOT NULL,
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      audit_status TEXT NOT NULL DEFAULT 'pending' CHECK (audit_status IN ('pending','approved','rejected')),
      audited_by INTEGER REFERENCES users(id),
      audited_at TIMESTAMP,
      audit_note TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_highlights_created ON inspection_highlights(created_at DESC, id DESC);
    CREATE INDEX IF NOT EXISTS idx_highlights_station ON inspection_highlights(station_id, id DESC);
    CREATE INDEX IF NOT EXISTS idx_highlights_table ON inspection_highlights(inspection_table_id, id DESC);
    CREATE TABLE IF NOT EXISTS inspection_highlight_audits (
      id BIGSERIAL PRIMARY KEY,
      highlight_id BIGINT NOT NULL REFERENCES inspection_highlights(id) ON DELETE CASCADE,
      actor_id INTEGER REFERENCES users(id),
      from_status TEXT NOT NULL,
      to_status TEXT NOT NULL,
      note TEXT NOT NULL DEFAULT '',
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """)


def downgrade():
    op.execute('DROP TABLE IF EXISTS inspection_highlight_audits; DROP TABLE IF EXISTS inspection_highlights;')
