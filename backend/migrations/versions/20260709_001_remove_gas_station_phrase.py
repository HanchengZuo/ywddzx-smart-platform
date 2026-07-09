"""remove gas-station wording from display data

Revision ID: 20260709_001
Revises: 20260707_002
Create Date: 2026-07-09 09:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260709_001"
down_revision = "20260707_002"
branch_labels = None
depends_on = None


REMOVED_PHRASE = "\u52a0\u6cb9\u7ad9"
OIL_STATION_TYPE = "油站"


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


def _strip_column(connection, table_name, column_name):
    if not _table_exists(connection, table_name) or not _column_exists(connection, table_name, column_name):
        return
    connection.execute(
        sa.text(
            f"""
            UPDATE {table_name}
            SET {column_name} = CASE
                WHEN BTRIM(COALESCE({column_name}, '')) = :phrase THEN :fallback
                ELSE REPLACE({column_name}, :phrase, '')
            END
            WHERE {column_name} LIKE :pattern;
            """
        ),
        {
            "phrase": REMOVED_PHRASE,
            "fallback": OIL_STATION_TYPE,
            "pattern": f"%{REMOVED_PHRASE}%",
        },
    )


def upgrade():
    connection = op.get_bind()

    if _table_exists(connection, "stations"):
        connection.execute(sa.text("ALTER TABLE stations DROP CONSTRAINT IF EXISTS stations_station_type_check;"))
        if _column_exists(connection, "stations", "station_type"):
            connection.execute(
                sa.text(
                    """
                    UPDATE stations
                    SET station_type = :oil_type
                    WHERE station_type = :phrase
                       OR station_type IS NULL
                       OR station_type NOT IN (:oil_type, '充电站');
                    """
                ),
                {"oil_type": OIL_STATION_TYPE, "phrase": REMOVED_PHRASE},
            )
            connection.execute(
                sa.text(
                    """
                    ALTER TABLE stations
                    ALTER COLUMN station_type SET DEFAULT '油站';
                    """
                )
            )
            connection.execute(
                sa.text(
                    """
                    ALTER TABLE stations
                    ADD CONSTRAINT stations_station_type_check
                    CHECK (station_type IN ('油站', '充电站'));
                    """
                )
            )

    for table_name, columns in {
        "stations": ("station_name", "region", "address"),
        "inspection_tables": ("table_name",),
        "issues": (
            "standard_detail_text",
            "internal_standard_detail_text",
            "issue_description",
            "station_feedback_description",
            "review_comment",
        ),
        "system_feedbacks": ("title", "description", "module"),
        "system_feedback_comments": ("comment_text",),
        "training_materials": ("title", "file_name"),
        "inspection_internal_standards": ("standard_content", "remark"),
        "inspection_internal_standard_tag_groups": ("group_name",),
        "inspection_internal_standard_tags": ("tag_name",),
    }.items():
        for column_name in columns:
            _strip_column(connection, table_name, column_name)

    if _table_exists(connection, "inspection_tables"):
        dynamic_column_rows = connection.execute(
            sa.text(
                """
                SELECT c.table_name, c.column_name
                FROM information_schema.columns c
                JOIN inspection_tables t
                  ON c.table_name = 'inspection_table_' || t.table_code
                WHERE c.table_schema = 'public'
                  AND c.data_type IN ('text', 'character varying');
                """
            )
        ).fetchall()
        for row in dynamic_column_rows:
            _strip_column(connection, row.table_name, row.column_name)


def downgrade():
    # This migration intentionally does not restore removed display wording.
    pass
