"""store inspection report history by date period

Revision ID: 20260902_001
Revises: 20260901_002
Create Date: 2026-09-02 10:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260902_001"
down_revision = "20260901_002"
branch_labels = None
depends_on = None


def _table_exists(connection, table_name):
    return bool(
        connection.execute(
            sa.text("SELECT to_regclass(:name);"),
            {"name": f"public.{table_name}"},
        ).scalar()
    )


def _column_exists(connection, table_name, column_name):
    return bool(
        connection.execute(
            sa.text(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table_name
                  AND column_name = :column_name
                """
            ),
            {"table_name": table_name, "column_name": column_name},
        ).first()
    )


def _add_period_columns(connection, table_name, timestamp_column="created_at"):
    if not _column_exists(connection, table_name, "period_start"):
        op.add_column(table_name, sa.Column("period_start", sa.Date(), nullable=True))
    if not _column_exists(connection, table_name, "period_end_exclusive"):
        op.add_column(
            table_name,
            sa.Column("period_end_exclusive", sa.Date(), nullable=True),
        )
    op.execute(
        sa.text(
            f"""
            UPDATE {table_name}
            SET period_start = CASE
                    WHEN report_month ~ '^\\d{{4}}-(0[1-9]|1[0-2])$'
                        THEN to_date(report_month || '-01', 'YYYY-MM-DD')
                    ELSE COALESCE({timestamp_column}::date, CURRENT_DATE)
                END,
                period_end_exclusive = CASE
                    WHEN report_month ~ '^\\d{{4}}-(0[1-9]|1[0-2])$'
                        THEN (to_date(report_month || '-01', 'YYYY-MM-DD') + INTERVAL '1 month')::date
                    ELSE COALESCE({timestamp_column}::date, CURRENT_DATE) + 1
                END
            WHERE period_start IS NULL OR period_end_exclusive IS NULL
            """
        )
    )
    op.alter_column(table_name, "period_start", nullable=False)
    op.alter_column(table_name, "period_end_exclusive", nullable=False)


def upgrade():
    connection = op.get_bind()

    if _table_exists(connection, "inspection_report_snapshots"):
        _add_period_columns(connection, "inspection_report_snapshots", "generated_at")
        if not _column_exists(connection, "inspection_report_snapshots", "generation_context"):
            op.add_column(
                "inspection_report_snapshots",
                sa.Column(
                    "generation_context",
                    postgresql.JSONB(),
                    nullable=False,
                    server_default=sa.text("'{}'::jsonb"),
                ),
            )
        op.execute("DROP INDEX IF EXISTS uq_inspection_report_snapshots_type_month_scope")
        # Older releases stored one snapshot per user scope. Keep the newest
        # copy before switching to one shared history item per date range.
        op.execute(
            """
            DELETE FROM inspection_report_snapshots target
            USING inspection_report_snapshots newer
            WHERE target.report_type = newer.report_type
              AND target.period_start = newer.period_start
              AND target.period_end_exclusive = newer.period_end_exclusive
              AND (
                    target.generated_at < newer.generated_at
                    OR (
                        target.generated_at = newer.generated_at
                        AND target.id < newer.id
                    )
                  )
            """
        )
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_inspection_report_snapshots_type_period "
            "ON inspection_report_snapshots "
            "(report_type, period_start, period_end_exclusive)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_inspection_report_snapshots_type_generated "
            "ON inspection_report_snapshots (report_type, generated_at DESC)"
        )

    if _table_exists(connection, "inspection_report_jobs"):
        _add_period_columns(connection, "inspection_report_jobs")
        op.execute("DROP INDEX IF EXISTS uq_inspection_report_jobs_active_scope")
        op.execute(
            """
            WITH ranked AS (
                SELECT task_id,
                       ROW_NUMBER() OVER (
                           PARTITION BY report_type, period_start, period_end_exclusive
                           ORDER BY created_at DESC, task_id DESC
                       ) AS position
                FROM inspection_report_jobs
                WHERE status IN ('queued', 'running')
            )
            UPDATE inspection_report_jobs job
            SET status = 'failed',
                progress = LEAST(progress, 99),
                stage_message = '历史重复任务已在升级时终止',
                error_message = '日期范围历史存储升级后，同一时间段只保留一个生成任务。',
                finished_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            FROM ranked
            WHERE job.task_id = ranked.task_id
              AND ranked.position > 1
            """
        )
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_inspection_report_jobs_active_period "
            "ON inspection_report_jobs "
            "(report_type, period_start, period_end_exclusive) "
            "WHERE status IN ('queued', 'running')"
        )

    if _table_exists(connection, "inspection_report_exports"):
        _add_period_columns(connection, "inspection_report_exports")
        if not _column_exists(connection, "inspection_report_exports", "snapshot_id"):
            op.add_column(
                "inspection_report_exports",
                sa.Column(
                    "snapshot_id",
                    sa.Integer(),
                    sa.ForeignKey("inspection_report_snapshots.id", ondelete="SET NULL"),
                    nullable=True,
                ),
            )
        op.execute("DROP INDEX IF EXISTS uq_inspection_report_exports_active_request")
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_inspection_report_exports_active_snapshot "
            "ON inspection_report_exports (requested_by, snapshot_id) "
            "WHERE status IN ('queued', 'running') AND snapshot_id IS NOT NULL"
        )

    if not _table_exists(connection, "inspection_report_quality_source_settings"):
        op.create_table(
            "inspection_report_quality_source_settings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("period_start", sa.Date(), nullable=False),
            sa.Column("period_end_exclusive", sa.Date(), nullable=False),
            sa.Column("selection_mode", sa.Text(), nullable=False, server_default="all"),
            sa.Column(
                "station_ids",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column(
                "updated_by",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.CheckConstraint(
                "selection_mode IN ('all', 'custom')",
                name="ck_quality_report_source_selection_mode",
            ),
            sa.CheckConstraint(
                "period_end_exclusive > period_start",
                name="ck_quality_report_source_period",
            ),
            sa.UniqueConstraint(
                "period_start",
                "period_end_exclusive",
                name="uq_quality_report_source_period",
            ),
        )
        op.create_index(
            "idx_quality_report_source_updated",
            "inspection_report_quality_source_settings",
            ["updated_at"],
        )


def downgrade():
    # Keep period data on downgrade; removing it could orphan generated files or
    # collapse multiple date-range reports back into one month record.
    op.execute("DROP INDEX IF EXISTS uq_inspection_report_exports_active_snapshot")
    op.execute("DROP INDEX IF EXISTS uq_inspection_report_jobs_active_period")
    op.execute("DROP INDEX IF EXISTS idx_inspection_report_snapshots_type_generated")
    op.execute("DROP INDEX IF EXISTS uq_inspection_report_snapshots_type_period")
