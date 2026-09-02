"""make non-oil issue selection global by issue_id

Remove period_start / period_end_exclusive from the primary key so that
exclusion decisions persist across date-range changes.

Revision ID: 20260902_002
Revises: 20260902_001
Create Date: 2026-09-02 17:00:00
"""

from alembic import context, op
import sqlalchemy as sa


revision = "20260902_002"
down_revision = "20260902_001"
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
        return

    # Clear stale data (period-keyed rows are incompatible with new schema).
    op.execute(f"DELETE FROM {table_name}")

    # Drop old constraints and indexes.
    op.execute(
        f"ALTER TABLE {table_name} "
        "DROP CONSTRAINT IF EXISTS inspection_report_non_oil_issue_selections_pkey"
    )
    op.execute(
        f"ALTER TABLE {table_name} "
        "DROP CONSTRAINT IF EXISTS ck_non_oil_issue_selection_period"
    )
    op.execute(
        "DROP INDEX IF EXISTS idx_non_oil_issue_selection_issue"
    )
    op.execute(
        "DROP INDEX IF EXISTS idx_non_oil_issue_selection_period"
    )

    # Remove period columns.
    op.execute(f"ALTER TABLE {table_name} DROP COLUMN IF EXISTS period_start")
    op.execute(f"ALTER TABLE {table_name} DROP COLUMN IF EXISTS period_end_exclusive")

    # New primary key on issue_id alone.
    op.execute(
        f"ALTER TABLE {table_name} ADD PRIMARY KEY (issue_id)"
    )

    # New indexes.
    op.execute(
        "CREATE INDEX idx_non_oil_issue_selection_issue "
        "ON inspection_report_non_oil_issue_selections (issue_id, updated_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_non_oil_issue_selection_included "
        "ON inspection_report_non_oil_issue_selections (is_included)"
    )


def downgrade():
    connection = op.get_bind()
    table_name = "inspection_report_non_oil_issue_selections"
    if not _table_exists(connection, table_name):
        return

    op.execute("DROP INDEX IF EXISTS idx_non_oil_issue_selection_included")
    op.execute("DROP INDEX IF EXISTS idx_non_oil_issue_selection_issue")
    op.execute(
        f"ALTER TABLE {table_name} "
        "DROP CONSTRAINT IF EXISTS inspection_report_non_oil_issue_selections_pkey"
    )

    op.execute(
        f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS "
        "period_start DATE"
    )
    op.execute(
        f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS "
        "period_end_exclusive DATE"
    )

    op.execute(
        f"ALTER TABLE {table_name} ADD PRIMARY KEY "
        "(period_start, period_end_exclusive, issue_id)"
    )
    op.execute(
        "CREATE INDEX idx_non_oil_issue_selection_issue "
        "ON inspection_report_non_oil_issue_selections (issue_id, updated_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_non_oil_issue_selection_period "
        "ON inspection_report_non_oil_issue_selections "
        "(period_start, period_end_exclusive, is_included)"
    )
