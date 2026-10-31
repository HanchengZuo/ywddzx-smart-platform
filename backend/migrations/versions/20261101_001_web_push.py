"""Multi-device browser push, personal inbox and durable delivery outbox."""
from alembic import op

revision = '20261101_001'
down_revision = '20261031_001'
branch_labels = depends_on = None


def upgrade():
    op.execute('''CREATE TABLE web_push_preferences (
      user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
      enabled BOOLEAN NOT NULL DEFAULT TRUE, updated_at TIMESTAMPTZ NOT NULL DEFAULT now());
    CREATE TABLE web_push_devices (
      id UUID PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      device_hash TEXT NOT NULL UNIQUE, endpoint_hash TEXT UNIQUE, subscription_cipher TEXT,
      revision UUID NOT NULL, platform TEXT NOT NULL, browser TEXT NOT NULL,
      capability TEXT NOT NULL, permission TEXT NOT NULL, active BOOLEAN NOT NULL DEFAULT FALSE,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(), last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      last_sent_at TIMESTAMPTZ, last_error TEXT NOT NULL DEFAULT '');
    CREATE INDEX web_push_devices_user ON web_push_devices(user_id,last_seen_at DESC);
    CREATE TABLE web_push_messages (
      id UUID PRIMARY KEY, request_id UUID NOT NULL, sender_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
      sender_name TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
      kind TEXT NOT NULL CHECK(kind IN ('manual','test')), created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      UNIQUE(sender_id,request_id));
    CREATE TABLE web_push_recipients (
      message_id UUID NOT NULL REFERENCES web_push_messages(id) ON DELETE CASCADE,
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      read_at TIMESTAMPTZ, confirmed_at TIMESTAMPTZ, PRIMARY KEY(message_id,user_id));
    CREATE INDEX web_push_recipients_user ON web_push_recipients(user_id);
    CREATE INDEX web_push_messages_sender ON web_push_messages(sender_id,created_at DESC);
    CREATE TABLE web_push_deliveries (
      id BIGSERIAL PRIMARY KEY, message_id UUID NOT NULL REFERENCES web_push_messages(id) ON DELETE CASCADE,
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      device_id UUID NOT NULL REFERENCES web_push_devices(id) ON DELETE CASCADE,
      device_revision UUID NOT NULL, status TEXT NOT NULL DEFAULT 'queued'
        CHECK(status IN ('queued','sending','accepted','failed','expired','skipped')),
      attempts INTEGER NOT NULL DEFAULT 0, available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      lease UUID, lease_until TIMESTAMPTZ, http_status INTEGER, last_error TEXT NOT NULL DEFAULT '',
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(message_id,device_id));
    CREATE INDEX web_push_deliveries_pending ON web_push_deliveries(available_at,id)
      WHERE status IN ('queued','sending');''')


def downgrade():
    op.execute('DROP TABLE web_push_deliveries,web_push_recipients,web_push_messages,web_push_devices,web_push_preferences')
