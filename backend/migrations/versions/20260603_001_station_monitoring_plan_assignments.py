"""add station monitoring status and plan inspector assignments

Revision ID: 20260603_001
Revises: 20260602_003
Create Date: 2026-06-03 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260603_001"
down_revision = "20260602_003"
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


def _constraint_exists(connection, constraint_name):
    return bool(
        connection.execute(
            sa.text(
                """
                SELECT 1
                FROM information_schema.table_constraints
                WHERE table_schema = 'public'
                  AND constraint_name = :constraint_name
                LIMIT 1;
                """
            ),
            {"constraint_name": constraint_name},
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

    if not _column_exists(connection, "stations", "monitoring_status"):
        op.add_column(
            "stations",
            sa.Column(
                "monitoring_status",
                sa.Text(),
                nullable=False,
                server_default="运行中",
            ),
        )

    connection.execute(
        sa.text(
            """
            UPDATE stations
            SET monitoring_status = '运行中'
            WHERE monitoring_status IS NULL
               OR monitoring_status NOT IN ('运行中', '未运行');
            """
        )
    )

    if not _constraint_exists(connection, "stations_monitoring_status_check"):
        op.create_check_constraint(
            "stations_monitoring_status_check",
            "stations",
            "monitoring_status IN ('运行中', '未运行')",
        )

    if not _column_exists(connection, "inspection_plan_station_items", "assigned_inspector_id"):
        op.add_column(
            "inspection_plan_station_items",
            sa.Column("assigned_inspector_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_inspection_plan_items_assigned_inspector",
            "inspection_plan_station_items",
            "users",
            ["assigned_inspector_id"],
            ["id"],
            ondelete="SET NULL",
        )

    if not _column_exists(connection, "inspection_plan_station_items", "assigned_by"):
        op.add_column(
            "inspection_plan_station_items",
            sa.Column("assigned_by", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_inspection_plan_items_assigned_by",
            "inspection_plan_station_items",
            "users",
            ["assigned_by"],
            ["id"],
            ondelete="SET NULL",
        )

    if not _column_exists(connection, "inspection_plan_station_items", "assigned_at"):
        op.add_column(
            "inspection_plan_station_items",
            sa.Column("assigned_at", sa.DateTime(), nullable=True),
        )

    if not _index_exists(connection, "idx_inspection_plan_station_items_assigned_inspector_id"):
        op.create_index(
            "idx_inspection_plan_station_items_assigned_inspector_id",
            "inspection_plan_station_items",
            ["assigned_inspector_id"],
        )


def downgrade():
    connection = op.get_bind()

    if _index_exists(connection, "idx_inspection_plan_station_items_assigned_inspector_id"):
        op.drop_index(
            "idx_inspection_plan_station_items_assigned_inspector_id",
            table_name="inspection_plan_station_items",
        )

    if _column_exists(connection, "inspection_plan_station_items", "assigned_at"):
        op.drop_column("inspection_plan_station_items", "assigned_at")

    if _column_exists(connection, "inspection_plan_station_items", "assigned_by"):
        op.drop_constraint(
            "fk_inspection_plan_items_assigned_by",
            "inspection_plan_station_items",
            type_="foreignkey",
        )
        op.drop_column("inspection_plan_station_items", "assigned_by")

    if _column_exists(connection, "inspection_plan_station_items", "assigned_inspector_id"):
        op.drop_constraint(
            "fk_inspection_plan_items_assigned_inspector",
            "inspection_plan_station_items",
            type_="foreignkey",
        )
        op.drop_column("inspection_plan_station_items", "assigned_inspector_id")

    if _constraint_exists(connection, "stations_monitoring_status_check"):
        op.drop_constraint("stations_monitoring_status_check", "stations", type_="check")

    if _column_exists(connection, "stations", "monitoring_status"):
        op.drop_column("stations", "monitoring_status")
