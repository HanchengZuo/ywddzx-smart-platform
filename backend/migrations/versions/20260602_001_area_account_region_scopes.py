"""add area account station region scopes

Revision ID: 20260602_001
Revises: 20260601_002
Create Date: 2026-06-02 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260602_001"
down_revision = "20260601_002"
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


def upgrade():
    connection = op.get_bind()
    if _table_exists(connection, "user_station_region_scopes"):
        return

    op.create_table(
        "user_station_region_scopes",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("scope_key", sa.Text(), nullable=False),
        sa.Column("station_region", sa.Text(), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("user_id", "scope_key", "station_region"),
    )


def downgrade():
    connection = op.get_bind()
    if _table_exists(connection, "user_station_region_scopes"):
        op.drop_table("user_station_region_scopes")
