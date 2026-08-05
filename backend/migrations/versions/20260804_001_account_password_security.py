"""add account password security management

Revision ID: 20260804_001
Revises: 20260729_001
Create Date: 2026-08-04 00:00:00
"""

import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from werkzeug.security import generate_password_hash


revision = "20260804_001"
down_revision = "20260729_001"
branch_labels = None
depends_on = None


DEFAULT_WEAK_PASSWORDS = [
    "123456",
    "12345678",
    "123456789",
    "password",
    "password123",
    "admin",
    "admin123",
    "qwerty",
    "abc123",
    "111111",
]
PRIVILEGED_ROLES = {"root", "supervisor"}


def _table_exists(connection, table_name):
    return bool(
        connection.execute(
            sa.text(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = :table_name
                LIMIT 1
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
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table_name
                  AND column_name = :column_name
                LIMIT 1
                """
            ),
            {"table_name": table_name, "column_name": column_name},
        ).first()
    )


def _add_column_if_missing(connection, table_name, column):
    if not _column_exists(connection, table_name, column.name):
        op.add_column(table_name, column)


def _is_password_hash(value):
    text = str(value or "")
    return text.startswith(("scrypt:", "pbkdf2:", "$argon2"))


def _normalize_identity(value):
    import re

    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", str(value or "").casefold())


def _is_identity_related(password, user):
    normalized_password = _normalize_identity(password)
    for value in (user.get("username"), user.get("phone"), user.get("hos_station_code"), "ywddzx"):
        normalized_value = _normalize_identity(value)
        if len(normalized_value) < 4:
            continue
        candidates = {normalized_value}
        if normalized_value.isdigit() and len(normalized_value) >= 6:
            candidates.add(normalized_value[-6:])
        if any(
            candidate in normalized_password
            or (len(normalized_password) >= 4 and normalized_password in candidate)
            for candidate in candidates
            if len(candidate) >= 4
        ):
            return True
    return False


def _risk_flags(password, user):
    text = str(password or "")
    flags = []
    if text == "123456":
        flags.append("initial_password")
    elif text.casefold() in {item.casefold() for item in DEFAULT_WEAK_PASSWORDS}:
        flags.append("common_password")
    minimum = 15 if user.get("role") in PRIVILEGED_ROLES else 12
    if len(text) < minimum:
        flags.append("too_short")
    if _is_identity_related(text, user):
        flags.append("identity_related")
    flags.append("policy_outdated")
    return list(dict.fromkeys(flags))


def _create_tables(connection):
    if not _table_exists(connection, "password_security_policies"):
        op.create_table(
            "password_security_policies",
            sa.Column("id", sa.SmallInteger(), nullable=False),
            sa.Column("enforcement_mode", sa.Text(), nullable=False, server_default="observe"),
            sa.Column("normal_min_length", sa.SmallInteger(), nullable=False, server_default="12"),
            sa.Column("privileged_min_length", sa.SmallInteger(), nullable=False, server_default="15"),
            sa.Column("max_length", sa.SmallInteger(), nullable=False, server_default="64"),
            sa.Column(
                "weak_passwords",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column("forbid_identity_similarity", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("history_count", sa.SmallInteger(), nullable=False, server_default="5"),
            sa.Column("grace_period_days", sa.SmallInteger(), nullable=False, server_default="30"),
            sa.Column("logout_other_sessions", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("updated_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint("id = 1", name="ck_password_security_policies_singleton"),
            sa.CheckConstraint(
                "enforcement_mode IN ('observe', 'enforce')",
                name="ck_password_security_policies_mode",
            ),
        )

    if not _table_exists(connection, "user_password_history"):
        op.create_table(
            "user_password_history",
            sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("password_hash", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "idx_user_password_history_user_created",
            "user_password_history",
            ["user_id", "created_at"],
        )

    if not _table_exists(connection, "security_audit_logs"):
        op.create_table(
            "security_audit_logs",
            sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
            sa.Column("actor_user_id", sa.Integer(), nullable=True),
            sa.Column("actor_username", sa.Text(), nullable=False),
            sa.Column("actor_role", sa.Text(), nullable=False),
            sa.Column("target_user_id", sa.Integer(), nullable=True),
            sa.Column("target_username", sa.Text(), nullable=True),
            sa.Column("action_type", sa.Text(), nullable=False),
            sa.Column("action_result", sa.Text(), nullable=False),
            sa.Column("failure_reason", sa.Text(), nullable=True),
            sa.Column("request_ip", sa.Text(), nullable=True),
            sa.Column("user_agent", sa.Text(), nullable=True),
            sa.Column("affected_count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column(
                "details",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint(
                "action_result IN ('success', 'failure')",
                name="ck_security_audit_logs_result",
            ),
        )
        op.create_index("idx_security_audit_logs_created", "security_audit_logs", ["created_at"])
        op.create_index(
            "idx_security_audit_logs_target_created",
            "security_audit_logs",
            ["target_user_id", "created_at"],
        )


def upgrade():
    connection = op.get_bind()
    if not _table_exists(connection, "users"):
        raise RuntimeError("required table public.users does not exist")

    _add_column_if_missing(connection, "users", sa.Column("password_hash", sa.Text(), nullable=True))
    _add_column_if_missing(
        connection,
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    _add_column_if_missing(
        connection,
        "users",
        sa.Column("force_change_immediately", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    _add_column_if_missing(connection, "users", sa.Column("password_changed_at", sa.DateTime(), nullable=True))
    _add_column_if_missing(
        connection,
        "users",
        sa.Column("password_policy_version", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        connection,
        "users",
        sa.Column("auth_version", sa.Integer(), nullable=False, server_default="1"),
    )
    _add_column_if_missing(
        connection,
        "users",
        sa.Column("account_status", sa.Text(), nullable=False, server_default="active"),
    )
    _add_column_if_missing(
        connection,
        "users",
        sa.Column(
            "password_risk_flags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    _add_column_if_missing(connection, "users", sa.Column("last_login_at", sa.DateTime(), nullable=True))

    _create_tables(connection)
    connection.execute(
        sa.text(
            """
            INSERT INTO password_security_policies (
                id, enforcement_mode, normal_min_length, privileged_min_length,
                max_length, weak_passwords, forbid_identity_similarity,
                history_count, grace_period_days, logout_other_sessions, version
            )
            VALUES (
                1, 'observe', 12, 15, 64, CAST(:weak_passwords AS jsonb),
                TRUE, 5, 30, TRUE, 1
            )
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"weak_passwords": json.dumps(DEFAULT_WEAK_PASSWORDS, ensure_ascii=False)},
    )

    # Remove the legacy NOT NULL constraint before clearing plaintext values.
    # The whole migration is transactional, so a later failure restores it.
    op.alter_column("users", "password", existing_type=sa.Text(), nullable=True)

    users = connection.execute(
        sa.text(
            """
            SELECT u.id, u.username, u.password, u.password_hash, u.role, u.phone,
                   s.hos_station_code
            FROM users u
            LEFT JOIN stations s ON s.id = u.station_id
            ORDER BY u.id
            """
        )
    ).mappings().all()

    migrated_count = 0
    for user in users:
        existing_hash = str(user.get("password_hash") or "")
        legacy_value = str(user.get("password") or "")
        if _is_password_hash(existing_hash):
            password_hash = existing_hash
            flags = ["policy_outdated"]
        elif _is_password_hash(legacy_value):
            password_hash = legacy_value
            flags = ["policy_outdated"]
        elif legacy_value:
            password_hash = generate_password_hash(legacy_value, method="scrypt")
            flags = _risk_flags(legacy_value, user)
            migrated_count += 1
        else:
            raise RuntimeError(f"user {user['id']} has no credential to migrate")

        connection.execute(
            sa.text(
                """
                UPDATE users
                SET password_hash = :password_hash,
                    password = NULL,
                    must_change_password = TRUE,
                    password_policy_version = 0,
                    password_risk_flags = CAST(:risk_flags AS jsonb),
                    auth_version = GREATEST(COALESCE(auth_version, 1), 1),
                    account_status = COALESCE(NULLIF(account_status, ''), 'active')
                WHERE id = :user_id
                """
            ),
            {
                "password_hash": password_hash,
                "risk_flags": json.dumps(flags, ensure_ascii=False),
                "user_id": user["id"],
            },
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO user_password_history (user_id, password_hash, created_at)
                SELECT :user_id, :password_hash, CURRENT_TIMESTAMP
                WHERE NOT EXISTS (
                    SELECT 1 FROM user_password_history
                    WHERE user_id = :user_id AND password_hash = :password_hash
                )
                """
            ),
            {"user_id": user["id"], "password_hash": password_hash},
        )

    op.alter_column("users", "password_hash", existing_type=sa.Text(), nullable=False)
    connection.execute(
        sa.text(
            """
            INSERT INTO security_audit_logs (
                actor_username, actor_role, action_type, action_result,
                affected_count, details
            )
            SELECT 'SYSTEM', 'system', 'plaintext_password_migration', 'success',
                   :affected_count,
                   CAST(:details AS jsonb)
            WHERE NOT EXISTS (
                SELECT 1 FROM security_audit_logs
                WHERE action_type = 'plaintext_password_migration'
            )
            """
        ),
        {
            "affected_count": migrated_count,
            "details": json.dumps(
                {"hash_method": "scrypt", "legacy_plaintext_cleared": True},
                ensure_ascii=False,
            ),
        },
    )


def downgrade():
    # Password hashes cannot be safely converted back to plaintext. Keeping the
    # security schema is the only non-destructive rollback behavior.
    pass
