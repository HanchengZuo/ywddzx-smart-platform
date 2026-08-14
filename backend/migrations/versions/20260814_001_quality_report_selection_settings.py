"""add configurable quality report issue selection settings

Revision ID: 20260814_001
Revises: 20260810_001
Create Date: 2026-08-14 16:00:00
"""

import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260814_001"
down_revision = "20260810_001"
branch_labels = None
depends_on = None


DEFAULT_SETTINGS = {
    "sample_counts": {
        "more_than_20": 8,
        "more_than_10": 6,
        "more_than_4": 4,
        "at_most_4": 2,
    },
    "prohibited_standard_priorities": [],
    "flow_standard_priorities": {},
}


def _table_exists(connection, table_name):
    return bool(
        connection.execute(
            sa.text("SELECT to_regclass(:qualified_name);"),
            {"qualified_name": f"public.{table_name}"},
        ).scalar()
    )


def upgrade():
    connection = op.get_bind()
    table_name = "inspection_report_quality_selection_settings"
    if not _table_exists(connection, table_name):
        op.create_table(
            table_name,
            sa.Column("id", sa.SmallInteger(), primary_key=True),
            sa.Column(
                "settings",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
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
                "id = 1",
                name="ck_quality_report_selection_settings_singleton",
            ),
        )

    connection.execute(
        sa.text(
            """
            INSERT INTO inspection_report_quality_selection_settings (id, settings)
            VALUES (1, CAST(:settings AS jsonb))
            ON CONFLICT (id) DO NOTHING;
            """
        ),
        {"settings": json.dumps(DEFAULT_SETTINGS)},
    )


def downgrade():
    connection = op.get_bind()
    if _table_exists(connection, "inspection_report_quality_selection_settings"):
        op.drop_table("inspection_report_quality_selection_settings")
