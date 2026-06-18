"""add per-inspector inspection completion confirmations

Revision ID: 20260618_001
Revises: 20260604_001
Create Date: 2026-06-18 10:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260618_001"
down_revision = "20260604_001"
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

    if not _table_exists(connection, "inspection_inspector_confirmations"):
        op.create_table(
            "inspection_inspector_confirmations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "inspection_id",
                sa.Integer(),
                sa.ForeignKey("inspections.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "inspector_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "confirmed_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column("source", sa.Text(), nullable=False, server_default="manual"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint(
                "inspection_id",
                "inspector_id",
                name="uq_inspection_inspector_confirmations",
            ),
        )

    if not _index_exists(connection, "idx_inspection_inspector_confirmations_inspection"):
        op.create_index(
            "idx_inspection_inspector_confirmations_inspection",
            "inspection_inspector_confirmations",
            ["inspection_id"],
        )

    if not _index_exists(connection, "idx_inspection_inspector_confirmations_inspector"):
        op.create_index(
            "idx_inspection_inspector_confirmations_inspector",
            "inspection_inspector_confirmations",
            ["inspector_id"],
        )


def downgrade():
    # Keep the table in place to avoid losing confirmation audit history.
    pass
