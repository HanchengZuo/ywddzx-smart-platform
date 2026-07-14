"""add background inspection report jobs

Revision ID: 20260714_001
Revises: 20260713_001
Create Date: 2026-07-14 10:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260714_001"
down_revision = "20260713_001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "inspection_report_jobs",
        sa.Column("task_id", sa.Text(), primary_key=True),
        sa.Column("report_type", sa.Text(), nullable=False),
        sa.Column("report_month", sa.Text(), nullable=False),
        sa.Column("scope_key", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="queued"),
        sa.Column("progress", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("stage_message", sa.Text(), nullable=False, server_default="等待后台处理"),
        sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("finished_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_inspection_report_jobs_status",
        ),
        sa.CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="ck_inspection_report_jobs_progress",
        ),
    )
    op.create_index(
        "uq_inspection_report_jobs_active_scope",
        "inspection_report_jobs",
        ["report_type", "report_month", "scope_key"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )
    op.create_index(
        "idx_inspection_report_jobs_user_updated",
        "inspection_report_jobs",
        ["requested_by", "updated_at"],
    )


def downgrade():
    op.drop_index("idx_inspection_report_jobs_user_updated", table_name="inspection_report_jobs")
    op.drop_index("uq_inspection_report_jobs_active_scope", table_name="inspection_report_jobs")
    op.drop_table("inspection_report_jobs")
