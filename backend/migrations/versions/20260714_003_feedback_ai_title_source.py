"""persist feedback AI title provenance

Revision ID: 20260714_003
Revises: 20260714_002
Create Date: 2026-07-14 16:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260714_003"
down_revision = "20260714_002"
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
    if not _column_exists(connection, "system_feedbacks", "title_ai_generated"):
        op.add_column(
            "system_feedbacks",
            sa.Column(
                "title_ai_generated",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("FALSE"),
            ),
        )

    if connection.execute(sa.text("SELECT to_regclass('public.ai_usage_logs');")).scalar():
        connection.execute(
            sa.text(
                """
                UPDATE system_feedbacks AS feedback
                SET title_ai_generated = TRUE
                WHERE title_ai_generated = FALSE
                  AND EXISTS (
                      SELECT 1
                      FROM ai_usage_logs AS usage
                      WHERE usage.user_id = feedback.created_by
                        AND usage.usage_module = '系统反馈'
                        AND usage.usage_action = '自动生成反馈标题'
                        AND usage.ai_generated = TRUE
                        AND ABS(EXTRACT(EPOCH FROM (usage.created_at - feedback.created_at))) <= 5
                  );
                """
            )
        )


def downgrade():
    connection = op.get_bind()
    if _column_exists(connection, "system_feedbacks", "title_ai_generated"):
        op.drop_column("system_feedbacks", "title_ai_generated")
