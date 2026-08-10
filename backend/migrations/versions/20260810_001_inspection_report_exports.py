"""add background PowerPoint export jobs for inspection reports

Revision ID: 20260810_001
Revises: 20260804_005
Create Date: 2026-08-10 10:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260810_001"
down_revision = "20260804_005"
branch_labels = None
depends_on = None


def _table_exists(connection, table_name):
    return bool(
        connection.execute(
            sa.text("SELECT to_regclass(:qualified_name);"),
            {"qualified_name": f"public.{table_name}"},
        ).scalar()
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
                LIMIT 1;
                """
            ),
            {"table_name": table_name, "column_name": column_name},
        ).first()
    )


def _index_exists(connection, index_name):
    return bool(
        connection.execute(
            sa.text(
                """
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = 'public' AND indexname = :index_name
                LIMIT 1;
                """
            ),
            {"index_name": index_name},
        ).first()
    )


def upgrade():
    connection = op.get_bind()
    table_name = "inspection_report_exports"
    if not _table_exists(connection, table_name):
        op.create_table(
            table_name,
            sa.Column("task_id", sa.Text(), primary_key=True),
            sa.Column("report_type", sa.Text(), nullable=False),
            sa.Column("report_month", sa.Text(), nullable=False),
            sa.Column("scope_key", sa.Text(), nullable=False),
            sa.Column(
                "requested_by",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("status", sa.Text(), nullable=False, server_default="queued"),
            sa.Column("progress", sa.SmallInteger(), nullable=False, server_default="0"),
            sa.Column("stage_message", sa.Text(), nullable=False, server_default="等待后台处理"),
            sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
            sa.Column("include_photos", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("file_path", sa.Text()),
            sa.Column("file_name", sa.Text()),
            sa.Column("file_size", sa.BigInteger()),
            sa.Column("slide_count", sa.Integer()),
            sa.Column("snapshot_generated_at", sa.DateTime(timezone=True)),
            sa.Column("report_payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("started_at", sa.DateTime(timezone=True)),
            sa.Column("finished_at", sa.DateTime(timezone=True)),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP + INTERVAL '7 days'")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint(
                "status IN ('queued', 'running', 'completed', 'failed')",
                name="ck_inspection_report_exports_status",
            ),
            sa.CheckConstraint(
                "progress >= 0 AND progress <= 100",
                name="ck_inspection_report_exports_progress",
            ),
            sa.CheckConstraint(
                "file_size IS NULL OR file_size >= 0",
                name="ck_inspection_report_exports_file_size",
            ),
            sa.CheckConstraint(
                "slide_count IS NULL OR slide_count > 0",
                name="ck_inspection_report_exports_slide_count",
            ),
        )

    # These guards also repair partially-created tables from interrupted deploys.
    repair_columns = [
        ("include_photos", sa.Column("include_photos", sa.Boolean(), nullable=False, server_default=sa.true())),
        ("file_path", sa.Column("file_path", sa.Text())),
        ("file_name", sa.Column("file_name", sa.Text())),
        ("file_size", sa.Column("file_size", sa.BigInteger())),
        ("slide_count", sa.Column("slide_count", sa.Integer())),
        ("snapshot_generated_at", sa.Column("snapshot_generated_at", sa.DateTime(timezone=True))),
        ("report_payload", sa.Column("report_payload", sa.JSON(), nullable=True)),
        ("expires_at", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP + INTERVAL '7 days'"))),
    ]
    for column_name, column in repair_columns:
        if not _column_exists(connection, table_name, column_name):
            op.add_column(table_name, column)

    if not _index_exists(connection, "uq_inspection_report_exports_active_request"):
        op.create_index(
            "uq_inspection_report_exports_active_request",
            table_name,
            ["requested_by", "report_type", "report_month", "scope_key"],
            unique=True,
            postgresql_where=sa.text("status IN ('queued', 'running')"),
        )
    if not _index_exists(connection, "idx_inspection_report_exports_user_updated"):
        op.create_index(
            "idx_inspection_report_exports_user_updated",
            table_name,
            ["requested_by", "updated_at"],
        )
    if not _index_exists(connection, "idx_inspection_report_exports_expires"):
        op.create_index(
            "idx_inspection_report_exports_expires",
            table_name,
            ["expires_at"],
        )


def downgrade():
    connection = op.get_bind()
    if _table_exists(connection, "inspection_report_exports"):
        op.drop_table("inspection_report_exports")
