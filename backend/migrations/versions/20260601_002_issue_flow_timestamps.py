"""add issue rectification and review timestamps

Revision ID: 20260601_002
Revises: 20260601_001
Create Date: 2026-06-01 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260601_002"
down_revision = "20260601_001"
branch_labels = None
depends_on = None


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


def upgrade():
    connection = op.get_bind()
    if not _column_exists(connection, "issues", "rectification_at"):
        op.add_column("issues", sa.Column("rectification_at", sa.DateTime(), nullable=True))
    if not _column_exists(connection, "issues", "review_at"):
        op.add_column("issues", sa.Column("review_at", sa.DateTime(), nullable=True))


def downgrade():
    connection = op.get_bind()
    if _column_exists(connection, "issues", "review_at"):
        op.drop_column("issues", "review_at")
    if _column_exists(connection, "issues", "rectification_at"):
        op.drop_column("issues", "rectification_at")
