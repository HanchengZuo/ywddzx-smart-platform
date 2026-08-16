"""add issue rectification and review flow history

Revision ID: 20260815_001
Revises: 20260814_001
Create Date: 2026-08-15 10:00:00
"""

from alembic import context, op
import sqlalchemy as sa


revision = "20260815_001"
down_revision = "20260814_001"
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
    table_name = "inspection_issue_flow_history"
    if not _table_exists(connection, table_name):
        op.create_table(
            table_name,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "issue_id",
                sa.Integer(),
                sa.ForeignKey("issues.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("round_no", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("action_type", sa.String(length=48), nullable=False),
            sa.Column("from_status", sa.String(length=32)),
            sa.Column("to_status", sa.String(length=32), nullable=False),
            sa.Column("result", sa.String(length=32)),
            sa.Column("note", sa.Text()),
            sa.Column("photo_path", sa.Text()),
            sa.Column(
                "actor_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
            ),
            sa.Column("actor_username", sa.String(length=120)),
            sa.Column("actor_name", sa.String(length=120)),
            sa.Column("actor_role", sa.String(length=80)),
            sa.Column("event_key", sa.String(length=160), unique=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.CheckConstraint("round_no >= 1", name="ck_issue_flow_history_round_positive"),
        )

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_issue_flow_history_issue_created "
        "ON inspection_issue_flow_history (issue_id, created_at ASC, id ASC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_issue_flow_history_actor "
        "ON inspection_issue_flow_history (actor_user_id, created_at DESC)"
    )

    # Existing rows are represented once so the timeline starts with the
    # business state already stored before this migration.
    connection.execute(
        sa.text(
            """
            INSERT INTO inspection_issue_flow_history (
                issue_id,
                round_no,
                action_type,
                from_status,
                to_status,
                result,
                note,
                photo_path,
                event_key,
                created_at
            )
            SELECT
                i.id,
                1,
                'rectification_submitted',
                '待整改',
                '待复核',
                i.rectification_result,
                i.rectification_note,
                i.rectification_photo_path,
                'legacy:rectification:' || i.id::text,
                COALESCE(i.rectification_at, i.created_at, CURRENT_TIMESTAMP)
            FROM issues i
            WHERE i.rectification_result IS NOT NULL
               OR i.rectification_at IS NOT NULL
            ON CONFLICT (event_key) DO NOTHING;
            """
        )
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO inspection_issue_flow_history (
                issue_id,
                round_no,
                action_type,
                from_status,
                to_status,
                result,
                note,
                photo_path,
                event_key,
                created_at
            )
            SELECT
                i.id,
                1,
                'review_submitted',
                '待复核',
                CASE
                    WHEN i.review_result = '已整改' THEN '已闭环'
                    WHEN i.review_result IN ('站经无法整改', '站级无法整改') THEN '站经无法整改'
                    WHEN i.review_result IN ('整改不通过', '整改未通过') THEN '待整改'
                    ELSE COALESCE(NULLIF(i.status, ''), '待复核')
                END,
                i.review_result,
                i.review_note,
                i.review_photo_path,
                'legacy:review:' || i.id::text,
                COALESCE(i.review_at, i.rectification_at, i.created_at, CURRENT_TIMESTAMP)
            FROM issues i
            WHERE i.review_result IS NOT NULL
               OR i.review_at IS NOT NULL
            ON CONFLICT (event_key) DO NOTHING;
            """
        )
    )


def downgrade():
    connection = op.get_bind()
    if _table_exists(connection, "inspection_issue_flow_history"):
        op.drop_table("inspection_issue_flow_history")
