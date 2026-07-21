"""add inspection issue automatic audit rules and history

Revision ID: 20260721_001
Revises: 20260714_003
Create Date: 2026-07-21 10:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260721_001"
down_revision = "20260714_003"
branch_labels = None
depends_on = None


def _table_exists(connection, table_name):
    return bool(
        connection.execute(
            sa.text("SELECT to_regclass(:table_name);"),
            {"table_name": f"public.{table_name}"},
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

    if not _table_exists(connection, "inspection_auto_audit_rules"):
        op.create_table(
            "inspection_auto_audit_rules",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("rule_name", sa.Text(), nullable=False),
            sa.Column("match_type", sa.Text(), nullable=False),
            sa.Column("match_value", sa.Text(), nullable=False),
            sa.Column("decision", sa.Text(), nullable=False),
            sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("100")),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
            sa.Column("remark", sa.Text()),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.CheckConstraint(
                "match_type IN ('external_standard_id', 'description_keyword')",
                name="ck_inspection_auto_audit_rules_match_type",
            ),
            sa.CheckConstraint(
                "decision IN ('approved', 'rejected')",
                name="ck_inspection_auto_audit_rules_decision",
            ),
            sa.CheckConstraint(
                "priority BETWEEN 1 AND 9999",
                name="ck_inspection_auto_audit_rules_priority",
            ),
        )

    if not _index_exists(connection, "idx_inspection_auto_audit_rules_execution"):
        op.create_index(
            "idx_inspection_auto_audit_rules_execution",
            "inspection_auto_audit_rules",
            ["is_enabled", "priority", "id"],
        )
    if not _index_exists(connection, "uq_inspection_auto_audit_rules_condition"):
        op.create_index(
            "uq_inspection_auto_audit_rules_condition",
            "inspection_auto_audit_rules",
            ["match_type", sa.text("LOWER(BTRIM(match_value))")],
            unique=True,
        )

    issue_columns = (
        ("audit_source", sa.Column("audit_source", sa.Text())),
        ("auto_audit_rule_id", sa.Column("auto_audit_rule_id", sa.Integer())),
        ("auto_audit_rule_name", sa.Column("auto_audit_rule_name", sa.Text())),
        ("auto_audit_match_summary", sa.Column("auto_audit_match_summary", sa.Text())),
    )
    for column_name, column in issue_columns:
        if not _column_exists(connection, "issues", column_name):
            op.add_column("issues", column)

    if not _index_exists(connection, "idx_issues_audit_source"):
        op.create_index("idx_issues_audit_source", "issues", ["audit_source", "audited_at"])

    if not _table_exists(connection, "inspection_auto_audit_logs"):
        op.create_table(
            "inspection_auto_audit_logs",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id", ondelete="SET NULL")),
            sa.Column("issue_reference_id", sa.Integer(), nullable=False),
            sa.Column("inspection_reference_id", sa.Integer(), nullable=False),
            sa.Column(
                "rule_id",
                sa.Integer(),
                sa.ForeignKey("inspection_auto_audit_rules.id", ondelete="SET NULL"),
            ),
            sa.Column("rule_name", sa.Text(), nullable=False),
            sa.Column("match_type", sa.Text(), nullable=False),
            sa.Column("match_value", sa.Text(), nullable=False),
            sa.Column("decision", sa.Text(), nullable=False),
            sa.Column("station_name", sa.Text()),
            sa.Column("inspection_table_name", sa.Text()),
            sa.Column("external_standard_id", sa.BigInteger()),
            sa.Column("issue_description", sa.Text()),
            sa.Column("triggered_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.CheckConstraint(
                "match_type IN ('external_standard_id', 'description_keyword')",
                name="ck_inspection_auto_audit_logs_match_type",
            ),
            sa.CheckConstraint(
                "decision IN ('approved', 'rejected')",
                name="ck_inspection_auto_audit_logs_decision",
            ),
        )

    if not _index_exists(connection, "idx_inspection_auto_audit_logs_triggered"):
        op.create_index(
            "idx_inspection_auto_audit_logs_triggered",
            "inspection_auto_audit_logs",
            [sa.text("triggered_at DESC")],
        )
    if not _index_exists(connection, "idx_inspection_auto_audit_logs_rule"):
        op.create_index(
            "idx_inspection_auto_audit_logs_rule",
            "inspection_auto_audit_logs",
            ["rule_id", "decision"],
        )


def downgrade():
    connection = op.get_bind()
    if _table_exists(connection, "inspection_auto_audit_logs"):
        op.drop_table("inspection_auto_audit_logs")
    if _index_exists(connection, "idx_issues_audit_source"):
        op.drop_index("idx_issues_audit_source", table_name="issues")
    for column_name in (
        "auto_audit_match_summary",
        "auto_audit_rule_name",
        "auto_audit_rule_id",
        "audit_source",
    ):
        if _column_exists(connection, "issues", column_name):
            op.drop_column("issues", column_name)
    if _table_exists(connection, "inspection_auto_audit_rules"):
        op.drop_table("inspection_auto_audit_rules")
