"""add global page visibility settings

Revision ID: 20260707_002
Revises: 20260707_001
Create Date: 2026-07-07 14:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260707_002"
down_revision = "20260707_001"
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
    if not _table_exists(connection, "system_page_visibility"):
        op.create_table(
            "system_page_visibility",
            sa.Column("page_key", sa.Text(), primary_key=True),
            sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
            sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    if not _index_exists(connection, "idx_system_page_visibility_visible"):
        op.create_index(
            "idx_system_page_visibility_visible",
            "system_page_visibility",
            ["is_visible"],
        )


def downgrade():
    op.drop_index("idx_system_page_visibility_visible", table_name="system_page_visibility")
    op.drop_table("system_page_visibility")
