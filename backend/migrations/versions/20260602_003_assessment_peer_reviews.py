"""add assessment peer review tables

Revision ID: 20260602_003
Revises: 20260602_002
Create Date: 2026-06-02 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260602_003"
down_revision = "20260602_002"
branch_labels = None
depends_on = None


def _table_exists(connection, table_name):
    return bool(
        connection.execute(
            sa.text(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = :table_name
                LIMIT 1;
                """
            ),
            {"table_name": table_name},
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


def _create_index_if_missing(connection, index_name, table_name, columns):
    if not _index_exists(connection, index_name):
        op.create_index(index_name, table_name, columns)


def upgrade():
    connection = op.get_bind()
    if not _table_exists(connection, "peer_review_templates"):
        op.create_table(
            "peer_review_templates",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("default_deadline_at", sa.DateTime(), nullable=True),
            sa.Column("show_participation", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
            sa.Column("show_reviewer", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        )

    if not _table_exists(connection, "peer_review_template_items"):
        op.create_table(
            "peer_review_template_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("template_id", sa.Integer(), nullable=False),
            sa.Column("item_type", sa.Text(), nullable=False, server_default="score"),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("max_score", sa.Integer(), nullable=False, server_default="5"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.ForeignKeyConstraint(["template_id"], ["peer_review_templates.id"], ondelete="CASCADE"),
        )

    if not _table_exists(connection, "peer_review_template_participants"):
        op.create_table(
            "peer_review_template_participants",
            sa.Column("template_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["template_id"], ["peer_review_templates.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("template_id", "user_id"),
        )

    if not _table_exists(connection, "peer_review_template_reviewees"):
        op.create_table(
            "peer_review_template_reviewees",
            sa.Column("template_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["template_id"], ["peer_review_templates.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("template_id", "user_id"),
        )

    if not _table_exists(connection, "peer_review_tasks"):
        op.create_table(
            "peer_review_tasks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("template_id", sa.Integer(), nullable=True),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("deadline_at", sa.DateTime(), nullable=True),
            sa.Column("show_participation", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
            sa.Column("show_reviewer", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
            sa.Column("status", sa.Text(), nullable=False, server_default="active"),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.ForeignKeyConstraint(["template_id"], ["peer_review_templates.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        )

    if not _table_exists(connection, "peer_review_task_items"):
        op.create_table(
            "peer_review_task_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("task_id", sa.Integer(), nullable=False),
            sa.Column("source_template_item_id", sa.Integer(), nullable=True),
            sa.Column("item_type", sa.Text(), nullable=False, server_default="score"),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("max_score", sa.Integer(), nullable=False, server_default="5"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.ForeignKeyConstraint(["task_id"], ["peer_review_tasks.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["source_template_item_id"], ["peer_review_template_items.id"], ondelete="SET NULL"),
        )

    if not _table_exists(connection, "peer_review_task_participants"):
        op.create_table(
            "peer_review_task_participants",
            sa.Column("task_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["task_id"], ["peer_review_tasks.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("task_id", "user_id"),
        )

    if not _table_exists(connection, "peer_review_task_reviewees"):
        op.create_table(
            "peer_review_task_reviewees",
            sa.Column("task_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["task_id"], ["peer_review_tasks.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("task_id", "user_id"),
        )

    if not _table_exists(connection, "peer_review_responses"):
        op.create_table(
            "peer_review_responses",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("task_id", sa.Integer(), nullable=False),
            sa.Column("reviewer_id", sa.Integer(), nullable=False),
            sa.Column("reviewee_id", sa.Integer(), nullable=False),
            sa.Column("submitted_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.ForeignKeyConstraint(["task_id"], ["peer_review_tasks.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["reviewee_id"], ["users.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("task_id", "reviewer_id", "reviewee_id"),
        )

    if not _table_exists(connection, "peer_review_response_items"):
        op.create_table(
            "peer_review_response_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("response_id", sa.Integer(), nullable=False),
            sa.Column("task_item_id", sa.Integer(), nullable=False),
            sa.Column("item_type", sa.Text(), nullable=False, server_default="score"),
            sa.Column("score_value", sa.Integer(), nullable=True),
            sa.Column("text_value", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.ForeignKeyConstraint(["response_id"], ["peer_review_responses.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["task_item_id"], ["peer_review_task_items.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("response_id", "task_item_id"),
        )

    _create_index_if_missing(connection, "idx_peer_review_tasks_status_deadline", "peer_review_tasks", ["status", "deadline_at"])
    _create_index_if_missing(connection, "idx_peer_review_responses_task_reviewer", "peer_review_responses", ["task_id", "reviewer_id"])
    _create_index_if_missing(connection, "idx_peer_review_responses_task_reviewee", "peer_review_responses", ["task_id", "reviewee_id"])


def downgrade():
    for table_name in (
        "peer_review_response_items",
        "peer_review_responses",
        "peer_review_task_reviewees",
        "peer_review_task_participants",
        "peer_review_task_items",
        "peer_review_tasks",
        "peer_review_template_reviewees",
        "peer_review_template_participants",
        "peer_review_template_items",
        "peer_review_templates",
    ):
        if _table_exists(op.get_bind(), table_name):
            op.drop_table(table_name)
