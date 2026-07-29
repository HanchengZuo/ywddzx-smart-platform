"""add source selection to inspection report jobs

Revision ID: 20260729_001
Revises: 20260721_001
Create Date: 2026-07-29 10:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260729_001"
down_revision = "20260721_001"
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


def upgrade():
    connection = op.get_bind()
    if not _column_exists(connection, "inspection_report_jobs", "generation_options"):
        op.add_column(
            "inspection_report_jobs",
            sa.Column(
                "generation_options",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )


def downgrade():
    connection = op.get_bind()
    if _column_exists(connection, "inspection_report_jobs", "generation_options"):
        op.drop_column("inspection_report_jobs", "generation_options")
