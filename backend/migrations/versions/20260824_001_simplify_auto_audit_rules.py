"""simplify automatic audit rules to external standard ids

Revision ID: 20260824_001
Revises: 20260817_001
Create Date: 2026-08-24 10:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260824_001"
down_revision = "20260817_001"
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


def _constraint_exists(connection, table_name, constraint_name):
    return bool(
        connection.execute(
            sa.text(
                """
                SELECT 1
                FROM pg_constraint constraint_row
                JOIN pg_class table_row ON table_row.oid = constraint_row.conrelid
                JOIN pg_namespace schema_row ON schema_row.oid = table_row.relnamespace
                WHERE schema_row.nspname = 'public'
                  AND table_row.relname = :table_name
                  AND constraint_row.conname = :constraint_name
                LIMIT 1;
                """
            ),
            {"table_name": table_name, "constraint_name": constraint_name},
        ).first()
    )


def upgrade():
    connection = op.get_bind()
    table_name = "inspection_auto_audit_rules"
    if not _table_exists(connection, table_name):
        return

    if not _column_exists(connection, table_name, "external_standard_id"):
        op.add_column(table_name, sa.Column("external_standard_id", sa.BigInteger()))

    if _column_exists(connection, table_name, "match_type"):
        # Historical logs remain intact. Keyword rules are no longer active rules.
        connection.execute(
            sa.text(
                """
                DELETE FROM inspection_auto_audit_rules
                WHERE match_type <> 'external_standard_id';
                """
            )
        )
        if _column_exists(connection, table_name, "match_value"):
            connection.execute(
                sa.text(
                    """
                    UPDATE inspection_auto_audit_rules
                    SET external_standard_id = BTRIM(match_value)::BIGINT
                    WHERE external_standard_id IS NULL
                      AND match_type = 'external_standard_id'
                      AND BTRIM(match_value) ~ '^[0-9]+$'
                      AND BTRIM(match_value)::NUMERIC > 0;
                    """
                )
            )

    connection.execute(
        sa.text(
            """
            DELETE FROM inspection_auto_audit_rules
            WHERE external_standard_id IS NULL OR external_standard_id <= 0;
            """
        )
    )
    connection.execute(
        sa.text(
            """
            WITH ranked_rules AS (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY external_standard_id
                        ORDER BY updated_at DESC NULLS LAST, id DESC
                    ) AS duplicate_rank
                FROM inspection_auto_audit_rules
            )
            DELETE FROM inspection_auto_audit_rules rule_row
            USING ranked_rules
            WHERE rule_row.id = ranked_rules.id
              AND ranked_rules.duplicate_rank > 1;
            """
        )
    )

    for index_name in (
        "idx_inspection_auto_audit_rules_execution",
        "uq_inspection_auto_audit_rules_condition",
    ):
        if _index_exists(connection, index_name):
            op.drop_index(index_name, table_name=table_name)

    for constraint_name in (
        "ck_inspection_auto_audit_rules_match_type",
        "ck_inspection_auto_audit_rules_priority",
    ):
        if _constraint_exists(connection, table_name, constraint_name):
            op.drop_constraint(constraint_name, table_name, type_="check")

    for column_name in ("match_type", "match_value", "priority"):
        if _column_exists(connection, table_name, column_name):
            op.drop_column(table_name, column_name)

    op.alter_column(table_name, "external_standard_id", nullable=False)
    if not _index_exists(connection, "uq_inspection_auto_audit_rules_external_standard"):
        op.create_index(
            "uq_inspection_auto_audit_rules_external_standard",
            table_name,
            ["external_standard_id"],
            unique=True,
        )
    if not _index_exists(connection, "idx_inspection_auto_audit_rules_enabled"):
        op.create_index(
            "idx_inspection_auto_audit_rules_enabled",
            table_name,
            ["is_enabled", "external_standard_id"],
        )


def downgrade():
    connection = op.get_bind()
    table_name = "inspection_auto_audit_rules"
    if not _table_exists(connection, table_name):
        return

    for index_name in (
        "idx_inspection_auto_audit_rules_enabled",
        "uq_inspection_auto_audit_rules_external_standard",
    ):
        if _index_exists(connection, index_name):
            op.drop_index(index_name, table_name=table_name)

    if not _column_exists(connection, table_name, "match_type"):
        op.add_column(table_name, sa.Column("match_type", sa.Text()))
    if not _column_exists(connection, table_name, "match_value"):
        op.add_column(table_name, sa.Column("match_value", sa.Text()))
    if not _column_exists(connection, table_name, "priority"):
        op.add_column(
            table_name,
            sa.Column("priority", sa.Integer(), server_default=sa.text("100")),
        )

    connection.execute(
        sa.text(
            """
            UPDATE inspection_auto_audit_rules
            SET match_type = 'external_standard_id',
                match_value = external_standard_id::TEXT,
                priority = 100;
            """
        )
    )
    op.alter_column(table_name, "match_type", nullable=False)
    op.alter_column(table_name, "match_value", nullable=False)
    op.alter_column(table_name, "priority", nullable=False)

    if not _constraint_exists(connection, table_name, "ck_inspection_auto_audit_rules_match_type"):
        op.create_check_constraint(
            "ck_inspection_auto_audit_rules_match_type",
            table_name,
            "match_type IN ('external_standard_id', 'description_keyword')",
        )
    if not _constraint_exists(connection, table_name, "ck_inspection_auto_audit_rules_priority"):
        op.create_check_constraint(
            "ck_inspection_auto_audit_rules_priority",
            table_name,
            "priority BETWEEN 1 AND 9999",
        )
    if not _index_exists(connection, "uq_inspection_auto_audit_rules_condition"):
        op.create_index(
            "uq_inspection_auto_audit_rules_condition",
            table_name,
            ["match_type", sa.text("LOWER(BTRIM(match_value))")],
            unique=True,
        )
    if not _index_exists(connection, "idx_inspection_auto_audit_rules_execution"):
        op.create_index(
            "idx_inspection_auto_audit_rules_execution",
            table_name,
            ["is_enabled", "priority", "id"],
        )

    if _column_exists(connection, table_name, "external_standard_id"):
        op.drop_column(table_name, "external_standard_id")
