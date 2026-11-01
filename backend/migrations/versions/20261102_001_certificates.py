"""Certificate registration, immutable versions and per-user reminder receipts."""

from alembic import op

revision = "20261102_001"
down_revision = "20261101_004"
branch_labels = depends_on = None


def upgrade():
    op.execute(
        """ALTER TABLE station_certificates ADD COLUMN IF NOT EXISTS is_present BOOLEAN NOT NULL DEFAULT TRUE;
        ALTER TABLE station_certificates ADD COLUMN IF NOT EXISTS photo_path TEXT;
        ALTER TABLE station_certificates ADD COLUMN IF NOT EXISTS revision INTEGER NOT NULL DEFAULT 1;
        ALTER TABLE station_certificates ALTER COLUMN expiry_date DROP NOT NULL;
        CREATE TABLE IF NOT EXISTS station_certificate_history (
            id BIGSERIAL PRIMARY KEY, certificate_id INTEGER NOT NULL REFERENCES station_certificates(id) ON DELETE CASCADE,
            revision INTEGER NOT NULL, is_present BOOLEAN NOT NULL, start_date DATE, expiry_date DATE, remark TEXT,photo_path TEXT,
            actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL, actor_name TEXT NOT NULL DEFAULT '',
            action TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(certificate_id,revision));
        INSERT INTO station_certificate_history(certificate_id,revision,is_present,start_date,expiry_date,remark,photo_path,actor_id,actor_name,action,created_at)
        SELECT c.id,c.revision,c.is_present,c.start_date,c.expiry_date,c.remark,c.photo_path,u.id,COALESCE(u.real_name,u.username,''),
            '历史记录迁入',COALESCE(c.updated_at,c.created_at,LOCALTIMESTAMP) AT TIME ZONE 'Asia/Shanghai'
        FROM station_certificates c LEFT JOIN users u ON u.id=COALESCE(c.updated_by,c.created_by)
        ON CONFLICT(certificate_id,revision) DO NOTHING;
        CREATE TABLE IF NOT EXISTS station_certificate_reminder_reads (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            certificate_id INTEGER NOT NULL REFERENCES station_certificates(id) ON DELETE CASCADE,
            revision INTEGER NOT NULL, status TEXT NOT NULL, read_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id,certificate_id,revision,status));
        CREATE INDEX IF NOT EXISTS idx_certificate_history_record ON station_certificate_history(certificate_id,id DESC);
        DO $$ BEGIN
            IF to_regclass('system_page_visibility') IS NOT NULL THEN
                INSERT INTO system_page_visibility(page_key,is_visible,updated_by)
                SELECT p.path,v.is_visible,v.updated_by FROM system_page_visibility v
                CROSS JOIN (VALUES ('/certificates/register'),('/certificates/ledger'),('/certificates/reminders')) p(path)
                WHERE v.page_key='/inspection/certificates'
                ON CONFLICT(page_key) DO NOTHING;
            END IF;
        END $$;
        """
    )


def downgrade():
    pass  # Keep evidence and history on rollback.
