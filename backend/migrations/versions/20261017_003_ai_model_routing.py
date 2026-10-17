"""Persist global and per-scenario model routing without storing credentials."""
from pathlib import Path
from alembic import op

revision = '20261017_003'
down_revision = '20261017_002'
branch_labels = None
depends_on = None


def upgrade():
    source = Path(__file__).resolve().parents[2] / 'db' / 'init' / '720_ai_model_settings.sql'
    op.get_bind().exec_driver_sql(source.read_text(encoding='utf-8'))


def downgrade():
    op.execute('DROP TABLE ai_model_setting_events')
    op.execute('DROP TABLE ai_model_settings')
