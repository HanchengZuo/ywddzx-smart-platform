"""add indexes for paged inspection record lists

Revision ID: 20260604_001
Revises: 20260603_002
Create Date: 2026-06-04 10:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260604_001"
down_revision = "20260603_002"
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
                LIMIT 1;
                """
            ),
            {"index_name": index_name},
        ).first()
    )


def _create_index_if_missing(connection, index_name, table_name, columns):
    if _index_exists(connection, index_name):
        return
    op.create_index(index_name, table_name, columns)


def _execute_index_if_missing(connection, index_name, statement):
    if _index_exists(connection, index_name):
        return
    connection.execute(sa.text(statement))


def upgrade():
    connection = op.get_bind()

    _execute_index_if_missing(
        connection,
        "idx_inspections_date_id",
        """
        CREATE INDEX idx_inspections_date_id
        ON inspections (inspection_date DESC, id DESC);
        """,
    )
    _execute_index_if_missing(
        connection,
        "idx_inspections_inspector_date_id",
        """
        CREATE INDEX idx_inspections_inspector_date_id
        ON inspections (inspector_id, inspection_date DESC, id DESC);
        """,
    )
    _execute_index_if_missing(
        connection,
        "idx_inspections_table_date_id",
        """
        CREATE INDEX idx_inspections_table_date_id
        ON inspections (inspection_table_id, inspection_date DESC, id DESC);
        """,
    )
    _execute_index_if_missing(
        connection,
        "idx_inspections_sign_status_date",
        """
        CREATE INDEX idx_inspections_sign_status_date
        ON inspections (sign_status, inspection_date DESC);
        """,
    )
    _execute_index_if_missing(
        connection,
        "idx_inspections_completion_status_date_desc",
        """
        CREATE INDEX idx_inspections_completion_status_date_desc
        ON inspections (inspector_completion_status, inspection_date DESC);
        """,
    )
    _create_index_if_missing(
        connection,
        "idx_issues_inspection_id",
        "issues",
        ["inspection_id"],
    )
    _create_index_if_missing(
        connection,
        "idx_issues_inspection_audit_status",
        "issues",
        ["inspection_id", "audit_status"],
    )
    _create_index_if_missing(
        connection,
        "idx_issues_inspection_inspector_id",
        "issues",
        ["inspection_id", "inspector_id"],
    )
    _create_index_if_missing(
        connection,
        "idx_stations_region_id",
        "stations",
        ["region", "id"],
    )


def downgrade():
    # Keep indexes in place; they are safe performance helpers.
    pass
