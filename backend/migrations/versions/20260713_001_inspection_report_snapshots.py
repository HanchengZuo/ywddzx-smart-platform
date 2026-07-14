"""add inspection report snapshots

Revision ID: 20260713_001
Revises: 20260709_001
Create Date: 2026-07-13 10:30:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260713_001"
down_revision = "20260709_001"
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
    if not _table_exists(connection, "inspection_report_snapshots"):
        op.create_table(
            "inspection_report_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("report_type", sa.Text(), nullable=False),
            sa.Column("report_month", sa.Text(), nullable=False),
            sa.Column("scope_key", sa.Text(), nullable=False, server_default="global"),
            sa.Column("report_payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("generated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("generated_by_name", sa.Text(), nullable=False, server_default=""),
            sa.Column("generated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    if not _index_exists(connection, "uq_inspection_report_snapshots_type_month_scope"):
        op.create_index(
            "uq_inspection_report_snapshots_type_month_scope",
            "inspection_report_snapshots",
            ["report_type", "report_month", "scope_key"],
            unique=True,
        )
    if not _index_exists(connection, "idx_inspection_report_snapshots_generated_at"):
        op.create_index(
            "idx_inspection_report_snapshots_generated_at",
            "inspection_report_snapshots",
            ["generated_at"],
        )


def downgrade():
    op.drop_index("idx_inspection_report_snapshots_generated_at", table_name="inspection_report_snapshots")
    op.drop_index("uq_inspection_report_snapshots_type_month_scope", table_name="inspection_report_snapshots")
    op.drop_table("inspection_report_snapshots")
