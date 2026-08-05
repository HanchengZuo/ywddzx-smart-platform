"""add persistent authentication rate limits

Revision ID: 20260804_005
Revises: 20260804_004
Create Date: 2026-08-04 17:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260804_005"
down_revision = "20260804_004"
branch_labels = None
depends_on = None


def _table_exists(connection, table_name):
    return bool(
        connection.execute(
            sa.text(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = :table_name
                LIMIT 1
                """
            ),
            {"table_name": table_name},
        ).first()
    )


def upgrade():
    connection = op.get_bind()
    if _table_exists(connection, "authentication_rate_limits"):
        return

    op.create_table(
        "authentication_rate_limits",
        sa.Column("scope_key", sa.String(length=64), primary_key=True),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_auth_rate_limits_attempt_count"),
    )
    op.create_index(
        "idx_auth_rate_limits_updated_at",
        "authentication_rate_limits",
        ["updated_at"],
    )
    op.create_index(
        "idx_auth_rate_limits_blocked_until",
        "authentication_rate_limits",
        ["blocked_until"],
    )


def downgrade():
    connection = op.get_bind()
    if _table_exists(connection, "authentication_rate_limits"):
        op.drop_table("authentication_rate_limits")
