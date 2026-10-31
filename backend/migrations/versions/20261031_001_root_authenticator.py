"""Root-only encrypted Authenticator binding and replay protection."""
from alembic import op

revision = '20261031_001'
down_revision = '20261030_001'
branch_labels = depends_on = None


def upgrade():
    op.execute('''CREATE TABLE root_authenticators (
        user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        secret_ciphertext TEXT,
        last_counter BIGINT NOT NULL DEFAULT -1,
        enabled_at TIMESTAMPTZ,
        last_used_at TIMESTAMPTZ,
        pending_ciphertext TEXT,
        pending_id TEXT,
        pending_expires_at TIMESTAMPTZ,
        pending_attempts INTEGER NOT NULL DEFAULT 0 CHECK (pending_attempts BETWEEN 0 AND 5)
    )''')


def downgrade():
    op.execute('DROP TABLE root_authenticators')
