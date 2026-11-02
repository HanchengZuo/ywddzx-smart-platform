"""Shared equipment phrases and station representative adjustments."""

from alembic import op

revision = "20261102_002"
down_revision = "20261102_001"
branch_labels = depends_on = None


def upgrade():
    op.execute("""CREATE TABLE IF NOT EXISTS inspection_report_equipment_settings (
        id INTEGER PRIMARY KEY CHECK(id=1), settings JSONB NOT NULL DEFAULT '{}'::jsonb,
        revision INTEGER NOT NULL DEFAULT 0, updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        updated_by_name TEXT NOT NULL DEFAULT '',updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    INSERT INTO inspection_report_equipment_settings(id,settings)
    VALUES(1,'{"phrases":{"9067":"非检查表类问题"},"station_overrides":{}}'::jsonb)
    ON CONFLICT(id) DO NOTHING;""")


def downgrade():
    pass
