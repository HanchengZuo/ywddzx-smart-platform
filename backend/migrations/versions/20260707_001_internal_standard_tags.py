"""add tag model for internal inspection standards

Revision ID: 20260707_001
Revises: 20260623_002
Create Date: 2026-07-07 10:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260707_001"
down_revision = "20260623_002"
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

    if not _table_exists(connection, "inspection_internal_standard_tag_groups"):
        op.create_table(
            "inspection_internal_standard_tag_groups",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("group_name", sa.Text(), nullable=False, unique=True),
            sa.Column("group_type", sa.Text(), nullable=False, server_default="custom"),
            sa.Column("color", sa.Text(), nullable=False, server_default="#2563EB"),
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
            sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
            sa.Column("is_filterable", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.CheckConstraint(
                "group_type IN ('custom', 'external_standard', 'inspection_table')",
                name="chk_internal_standard_tag_group_type",
            ),
        )
    elif not _column_exists(connection, "inspection_internal_standard_tag_groups", "color"):
        op.add_column(
            "inspection_internal_standard_tag_groups",
            sa.Column("color", sa.Text(), nullable=False, server_default="#2563EB"),
        )

    if not _table_exists(connection, "inspection_internal_standard_tags"):
        op.create_table(
            "inspection_internal_standard_tags",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "group_id",
                sa.Integer(),
                sa.ForeignKey("inspection_internal_standard_tag_groups.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("tag_name", sa.Text(), nullable=False),
            sa.Column("tag_key", sa.Text(), nullable=False),
            sa.Column("color", sa.Text(), nullable=False, server_default="#2563EB"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("group_id", "tag_key", name="uq_internal_standard_tags_group_key"),
        )

    if not _table_exists(connection, "inspection_internal_standard_tag_links"):
        op.create_table(
            "inspection_internal_standard_tag_links",
            sa.Column(
                "internal_standard_id",
                sa.Integer(),
                sa.ForeignKey("inspection_internal_standards.id", ondelete="CASCADE"),
                primary_key=True,
                nullable=False,
            ),
            sa.Column(
                "tag_id",
                sa.Integer(),
                sa.ForeignKey("inspection_internal_standard_tags.id", ondelete="CASCADE"),
                primary_key=True,
                nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    if not _index_exists(connection, "idx_internal_standard_tags_group"):
        op.create_index(
            "idx_internal_standard_tags_group",
            "inspection_internal_standard_tags",
            ["group_id", "sort_order"],
        )

    if not _index_exists(connection, "idx_internal_standard_tag_links_tag"):
        op.create_index(
            "idx_internal_standard_tag_links_tag",
            "inspection_internal_standard_tag_links",
            ["tag_id"],
        )

    connection.execute(
        sa.text(
            """
            INSERT INTO inspection_internal_standard_tag_groups (
                group_name,
                group_type,
                color,
                is_system,
                is_required,
                is_filterable,
                sort_order
            )
            VALUES
                ('外部规范ID', 'external_standard', '#2563EB', TRUE, TRUE, TRUE, 0),
                ('检查表', 'inspection_table', '#0F766E', TRUE, FALSE, TRUE, 1)
            ON CONFLICT (group_name)
            DO UPDATE SET
                group_type = EXCLUDED.group_type,
                color = EXCLUDED.color,
                is_system = EXCLUDED.is_system,
                is_required = EXCLUDED.is_required,
                is_filterable = EXCLUDED.is_filterable,
                sort_order = EXCLUDED.sort_order,
                updated_at = CURRENT_TIMESTAMP;
            """
        )
    )


def downgrade():
    # Keep tag data to avoid losing curated internal-standard taxonomy.
    pass
