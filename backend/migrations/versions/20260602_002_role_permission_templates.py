"""add role permission templates and scopes

Revision ID: 20260602_002
Revises: 20260602_001
Create Date: 2026-06-02 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260602_002"
down_revision = "20260602_001"
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
    if not _table_exists(connection, "role_permissions"):
        op.create_table(
            "role_permissions",
            sa.Column("role", sa.Text(), nullable=False),
            sa.Column("permission_key", sa.Text(), nullable=False),
            sa.Column("is_allowed", sa.Boolean(), nullable=False),
            sa.Column("updated_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("role", "permission_key"),
        )

    if _table_exists(connection, "inspection_tables") and not _table_exists(connection, "role_inspection_table_scopes"):
        op.create_table(
            "role_inspection_table_scopes",
            sa.Column("role", sa.Text(), nullable=False),
            sa.Column("scope_key", sa.Text(), nullable=False),
            sa.Column("inspection_table_id", sa.Integer(), nullable=False),
            sa.Column("updated_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.ForeignKeyConstraint(["inspection_table_id"], ["inspection_tables.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("role", "scope_key", "inspection_table_id"),
        )

    if not _table_exists(connection, "role_station_region_scopes"):
        op.create_table(
            "role_station_region_scopes",
            sa.Column("role", sa.Text(), nullable=False),
            sa.Column("scope_key", sa.Text(), nullable=False),
            sa.Column("station_region", sa.Text(), nullable=False),
            sa.Column("updated_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("role", "scope_key", "station_region"),
        )


def downgrade():
    connection = op.get_bind()
    if _table_exists(connection, "role_station_region_scopes"):
        op.drop_table("role_station_region_scopes")
    if _table_exists(connection, "role_inspection_table_scopes"):
        op.drop_table("role_inspection_table_scopes")
    if _table_exists(connection, "role_permissions"):
        op.drop_table("role_permissions")
