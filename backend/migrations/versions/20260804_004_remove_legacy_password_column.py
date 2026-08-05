"""remove the legacy plaintext password column

Revision ID: 20260804_004
Revises: 20260804_003
Create Date: 2026-08-04 16:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260804_004"
down_revision = "20260804_003"
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
                LIMIT 1
                """
            ),
            {"table_name": table_name, "column_name": column_name},
        ).first()
    )


def upgrade():
    connection = op.get_bind()
    if not _column_exists(connection, "users", "password"):
        return

    populated_count = connection.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM users
            WHERE password IS NOT NULL AND password <> ''
            """
        )
    ).scalar_one()
    if int(populated_count or 0) > 0:
        raise RuntimeError(
            "refusing to drop public.users.password because plaintext values still exist"
        )

    op.drop_column("users", "password")


def downgrade():
    connection = op.get_bind()
    if not _column_exists(connection, "users", "password"):
        op.add_column("users", sa.Column("password", sa.Text(), nullable=True))
