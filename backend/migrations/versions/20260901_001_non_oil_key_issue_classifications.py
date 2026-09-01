"""add non-oil key issue classifications

Revision ID: 20260901_001
Revises: 20260824_002
Create Date: 2026-09-01 10:00:00
"""

from alembic import context, op
import sqlalchemy as sa


revision = "20260901_001"
down_revision = "20260824_002"
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
    table_name = "inspection_report_non_oil_key_issue_classifications"
    if not _table_exists(connection, table_name):
        op.create_table(
            table_name,
            sa.Column(
                "issue_id",
                sa.Integer(),
                sa.ForeignKey("issues.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("ai_category", sa.String(length=80)),
            sa.Column("effective_category", sa.String(length=80), nullable=False),
            sa.Column(
                "classification_source",
                sa.String(length=20),
                nullable=False,
                server_default="ai",
            ),
            sa.Column("reason", sa.Text()),
            sa.Column("model_name", sa.String(length=100)),
            sa.Column(
                "classified_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
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
                "classification_source IN ('ai', 'manual', 'fallback')",
                name="ck_non_oil_key_issue_classification_source",
            ),
        )

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_non_oil_key_issue_effective "
        "ON inspection_report_non_oil_key_issue_classifications "
        "(effective_category, updated_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_non_oil_key_issue_source "
        "ON inspection_report_non_oil_key_issue_classifications "
        "(classification_source, updated_at DESC)"
    )


def downgrade():
    connection = op.get_bind()
    if _table_exists(connection, "inspection_report_non_oil_key_issue_classifications"):
        op.drop_table("inspection_report_non_oil_key_issue_classifications")
