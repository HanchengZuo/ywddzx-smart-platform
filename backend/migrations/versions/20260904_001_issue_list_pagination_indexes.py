"""add indexes for paged issue list queries

Revision ID: 20260904_001
Revises: 20260903_003
Create Date: 2026-09-04 16:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260904_001"
down_revision = "20260903_003"
branch_labels = None
depends_on = None


def _index_exists(connection, index_name):
    return bool(
        connection.execute(
            sa.text(
                """
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname = :index_name
                LIMIT 1
                """
            ),
            {"index_name": index_name},
        ).first()
    )


def _create_index_if_missing(connection, index_name, statement):
    if _index_exists(connection, index_name):
        return
    connection.execute(sa.text(statement))


def upgrade():
    connection = op.get_bind()
    _create_index_if_missing(
        connection,
        "idx_issues_created_id_desc",
        "CREATE INDEX idx_issues_created_id_desc ON issues (created_at DESC, id DESC)",
    )
    _create_index_if_missing(
        connection,
        "idx_issues_station_created_id_desc",
        "CREATE INDEX idx_issues_station_created_id_desc ON issues (station_id, created_at DESC, id DESC)",
    )
    _create_index_if_missing(
        connection,
        "idx_issues_table_created_id_desc",
        "CREATE INDEX idx_issues_table_created_id_desc ON issues (inspection_table_id, created_at DESC, id DESC)",
    )
    _create_index_if_missing(
        connection,
        "idx_issues_audit_created_id_desc",
        "CREATE INDEX idx_issues_audit_created_id_desc ON issues (audit_status, created_at DESC, id DESC)",
    )


def downgrade():
    # These indexes are safe performance helpers and may be shared by newer releases.
    pass
