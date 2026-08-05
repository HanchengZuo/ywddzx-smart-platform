"""add Passkey credentials and one-time WebAuthn challenges

Revision ID: 20260804_003
Revises: 20260804_002
Create Date: 2026-08-04 16:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260804_003"
down_revision = "20260804_002"
branch_labels = None
depends_on = None


def _table_exists(connection, table_name):
    return bool(
        connection.execute(
            sa.text(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = :table_name
                LIMIT 1
                """
            ),
            {"table_name": table_name},
        ).first()
    )


def upgrade():
    connection = op.get_bind()

    if not _table_exists(connection, "user_passkeys"):
        op.create_table(
            "user_passkeys",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "user_id",
                sa.BigInteger(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("credential_id", sa.LargeBinary(), nullable=False),
            sa.Column("credential_public_key", sa.LargeBinary(), nullable=False),
            sa.Column("sign_count", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column(
                "transports",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column("device_type", sa.String(length=40), nullable=True),
            sa.Column("backed_up", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("credential_name", sa.String(length=80), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("credential_id", name="uq_user_passkeys_credential_id"),
        )
        op.create_index("idx_user_passkeys_user_id", "user_passkeys", ["user_id"])

    if not _table_exists(connection, "webauthn_challenges"):
        op.create_table(
            "webauthn_challenges",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "user_id",
                sa.BigInteger(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column("purpose", sa.String(length=40), nullable=False),
            sa.Column("challenge", sa.LargeBinary(), nullable=False),
            sa.Column("auth_version", sa.Integer(), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index(
            "idx_webauthn_challenges_expiry",
            "webauthn_challenges",
            ["expires_at"],
        )
        op.create_index(
            "idx_webauthn_challenges_user_purpose",
            "webauthn_challenges",
            ["user_id", "purpose"],
        )


def downgrade():
    connection = op.get_bind()
    if _table_exists(connection, "webauthn_challenges"):
        op.drop_table("webauthn_challenges")
    if _table_exists(connection, "user_passkeys"):
        op.drop_table("user_passkeys")
