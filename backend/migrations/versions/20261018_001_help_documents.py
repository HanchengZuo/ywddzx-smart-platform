"""Persistent help articles, publication workflow and editorial audit history."""
from pathlib import Path
from alembic import op

revision = '20261018_001'
down_revision = '20261017_003'
branch_labels = None
depends_on = None


def upgrade():
    source = Path(__file__).resolve().parents[2] / 'db' / 'init' / '730_help_documents.sql'
    op.get_bind().exec_driver_sql(source.read_text(encoding='utf-8'))


def downgrade():
    op.execute('DROP TABLE help_document_events')
    op.execute('DROP TABLE help_documents')
