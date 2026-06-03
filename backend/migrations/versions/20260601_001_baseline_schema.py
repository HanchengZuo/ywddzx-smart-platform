"""baseline schema from current SQL initialization scripts

Revision ID: 20260601_001
Revises:
Create Date: 2026-06-01 00:00:00
"""

from pathlib import Path

from alembic import op
import sqlalchemy as sa


revision = "20260601_001"
down_revision = None
branch_labels = None
depends_on = None


INIT_SQL_FILES = [
    "100_core_stations.sql",
    "110_core_users_permissions.sql",
    "200_inspection_checklist_registry.sql",
    "205_user_inspection_table_scopes.sql",
    "210_inspection_checklist_fields.sql",
    "215_inspection_internal_standards.sql",
    "220_inspection_records.sql",
    "230_inspection_issues.sql",
    "240_inspection_batches.sql",
    "250_inspection_completion_settings.sql",
    "500_inspection_plan_configs.sql",
    "510_inspection_plan_station_items.sql",
    "600_station_certificates.sql",
    "700_system_feedback.sql",
    "710_ai_usage_logs.sql",
    "720_assessment_station_scores.sql",
    "730_assessment_peer_reviews.sql",
]


def _business_table_count(connection):
    return connection.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
              AND table_name <> 'alembic_version';
            """
        )
    ).scalar_one()


def _init_sql_dir():
    return Path(__file__).resolve().parents[2] / "db" / "init"


def upgrade():
    connection = op.get_bind()

    # This baseline builds a brand-new empty database. Existing deployments
    # already initialized by legacy SQL scripts are treated as the baseline and
    # Alembic records the revision without replaying table creation statements.
    if _business_table_count(connection) > 0:
        return

    sql_dir = _init_sql_dir()
    for file_name in INIT_SQL_FILES:
        sql_path = sql_dir / file_name
        if not sql_path.exists():
            raise RuntimeError(f"Missing baseline SQL file: {sql_path}")

        sql_text = sql_path.read_text(encoding="utf-8").strip()
        if sql_text:
            connection.exec_driver_sql(sql_text)


def downgrade():
    # Intentionally no-op. This revision is a production baseline for an
    # existing system; destructive schema rollback should be handled manually.
    pass
