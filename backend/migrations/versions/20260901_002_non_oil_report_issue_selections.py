"""add non-oil report issue selections

Revision ID: 20260901_002
Revises: 20260901_001
Create Date: 2026-09-01 14:00:00
"""

from alembic import context, op
import sqlalchemy as sa


revision = "20260901_002"
down_revision = "20260901_001"
branch_labels = None
depends_on = None


def _table_exists(connection, table_name):
    if context.is_offline_mode():
        return False
    return bool(
        connection.execute(
            sa.text("SELECT to_regclass(:qualified_name);"),
            {"qualified_name": f"public.{table_name}"},
        ).scalar()
    )


def upgrade():
    connection = op.get_bind()
    table_name = "inspection_report_non_oil_issue_selections"
    if not _table_exists(connection, table_name):
        op.create_table(
            table_name,
            sa.Column("period_start", sa.Date(), primary_key=True),
            sa.Column("period_end_exclusive", sa.Date(), primary_key=True),
            sa.Column(
                "issue_id",
                sa.Integer(),
                sa.ForeignKey("issues.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "is_included",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
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
                "period_end_exclusive > period_start",
                name="ck_non_oil_issue_selection_period",
            ),
        )

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_non_oil_issue_selection_issue "
        "ON inspection_report_non_oil_issue_selections (issue_id, updated_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_non_oil_issue_selection_period "
        "ON inspection_report_non_oil_issue_selections "
        "(period_start, period_end_exclusive, is_included)"
    )


def downgrade():
    connection = op.get_bind()
    if _table_exists(connection, "inspection_report_non_oil_issue_selections"):
        op.drop_table("inspection_report_non_oil_issue_selections")
