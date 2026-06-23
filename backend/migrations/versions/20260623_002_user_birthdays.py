"""add managed user birthday blessings

Revision ID: 20260623_002
Revises: 20260623_001
Create Date: 2026-06-23 16:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260623_002"
down_revision = "20260623_001"
branch_labels = None
depends_on = None


DEFAULT_USER_BIRTHDAYS = [
    ("徐佳仪", 1, 11),
    ("王昕怡", 1, 16),
    ("宋辞", 2, 5),
    ("吴杰", 2, 11),
    ("程镇林", 2, 14),
    ("王涛", 3, 26),
    ("彭思宇", 4, 18),
    ("束紫荆", 5, 8),
    ("左翰承", 7, 3),
    ("李泊汛", 7, 3),
    ("袁姝慧", 7, 30),
    ("刘文喆", 8, 16),
    ("王子玥", 8, 20),
    ("吕雪儿", 9, 19),
    ("赵萌", 10, 22),
    ("徐晃", 11, 18),
    ("魏九发", 12, 1),
    ("姜傲云", 12, 7),
    ("侯明敖", 12, 10),
    ("葛心玉", 12, 18),
    ("陈中磊", 12, 21),
]


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


def upgrade():
    connection = op.get_bind()

    if not _table_exists(connection, "user_birthdays"):
        op.create_table(
            "user_birthdays",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("real_name", sa.Text(), nullable=False, unique=True),
            sa.Column("birthday_month", sa.Integer(), nullable=False),
            sa.Column("birthday_day", sa.Integer(), nullable=False),
            sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.CheckConstraint("birthday_month BETWEEN 1 AND 12", name="ck_user_birthdays_month"),
            sa.CheckConstraint("birthday_day BETWEEN 1 AND 31", name="ck_user_birthdays_day"),
        )

    if not _index_exists(connection, "idx_user_birthdays_real_name"):
        op.create_index("idx_user_birthdays_real_name", "user_birthdays", ["real_name"])

    for real_name, month, day in DEFAULT_USER_BIRTHDAYS:
        connection.execute(
            sa.text(
                """
                INSERT INTO user_birthdays (
                    real_name,
                    birthday_month,
                    birthday_day,
                    created_at,
                    updated_at
                )
                VALUES (:real_name, :month, :day, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (real_name) DO NOTHING;
                """
            ),
            {"real_name": real_name, "month": month, "day": day},
        )


def downgrade():
    # Keep birthday records to avoid losing manually maintained employee care data.
    pass
