"""add password character complexity policy

Revision ID: 20260804_002
Revises: 20260804_001
Create Date: 2026-08-04 12:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260804_002"
down_revision = "20260804_001"
branch_labels = None
depends_on = None


POLICY_COLUMNS = (
    "require_uppercase",
    "require_lowercase",
    "require_number",
    "require_special",
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
                LIMIT 1
                """
            ),
            {"table_name": table_name, "column_name": column_name},
        ).first()
    )


def upgrade():
    connection = op.get_bind()
    for column_name in POLICY_COLUMNS:
        if not _column_exists(connection, "password_security_policies", column_name):
            op.add_column(
                "password_security_policies",
                sa.Column(
                    column_name,
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.true(),
                ),
            )


def downgrade():
    connection = op.get_bind()
    for column_name in reversed(POLICY_COLUMNS):
        if _column_exists(connection, "password_security_policies", column_name):
            op.drop_column("password_security_policies", column_name)
