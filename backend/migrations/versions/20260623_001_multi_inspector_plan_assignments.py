"""support multiple inspectors on plan station assignments

Revision ID: 20260623_001
Revises: 20260618_001
Create Date: 2026-06-23 10:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260623_001"
down_revision = "20260618_001"
branch_labels = None
depends_on = None


def _table_exists(connection, table_name):
    return bool(
        connection.execute(
            sa.text(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = :table_name
                LIMIT 1;
                """
            ),
            {"table_name": table_name},
        ).first()
    )


def _column_exists(connection, table_name, column_name):
    return bool(
        connection.execute(
            sa.text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table_name
                  AND column_name = :column_name
                LIMIT 1;
                """
            ),
            {"table_name": table_name, "column_name": column_name},
        ).first()
    )


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


def upgrade():
    connection = op.get_bind()
    table_name = "inspection_plan_station_items"

    if not _table_exists(connection, table_name):
        return

    if not _column_exists(connection, table_name, "assigned_inspector_ids"):
        op.add_column(
            table_name,
            sa.Column(
                "assigned_inspector_ids",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
        )

    connection.execute(
        sa.text(
            """
            UPDATE inspection_plan_station_items
            SET assigned_inspector_ids = CASE
                    WHEN assigned_inspector_id IS NULL THEN '[]'::jsonb
                    ELSE jsonb_build_array(assigned_inspector_id)
                END
            WHERE assigned_inspector_ids IS NULL
               OR assigned_inspector_ids = '[]'::jsonb
               OR jsonb_typeof(assigned_inspector_ids) <> 'array';
            """
        )
    )

    if not _index_exists(connection, "idx_inspection_plan_station_items_assigned_inspector_ids"):
        op.create_index(
            "idx_inspection_plan_station_items_assigned_inspector_ids",
            table_name,
            ["assigned_inspector_ids"],
            postgresql_using="gin",
        )


def downgrade():
    # Keep the JSONB assignment history in place to avoid losing multi-person dispatch data.
    pass
