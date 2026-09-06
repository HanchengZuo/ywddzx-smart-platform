"""One appeal per issue, per-user reads, and atomic appeal lifecycle events."""
from alembic import op

revision = '20260906_001'
down_revision = '20260905_003'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
      CREATE TABLE IF NOT EXISTS inspection_issue_appeal_claims (
        issue_id INTEGER PRIMARY KEY REFERENCES issues(id) ON DELETE CASCADE
      );
      INSERT INTO inspection_issue_appeal_claims(issue_id)
        SELECT DISTINCT issue_id FROM inspection_issue_appeals ON CONFLICT DO NOTHING;
      CREATE OR REPLACE FUNCTION claim_issue_appeal_once() RETURNS trigger AS $$
      DECLARE claimed integer;
      BEGIN
        INSERT INTO inspection_issue_appeal_claims(issue_id) VALUES (NEW.issue_id)
          ON CONFLICT DO NOTHING RETURNING issue_id INTO claimed;
        IF claimed IS NULL THEN
          RAISE EXCEPTION 'Issue already participated in an appeal' USING ERRCODE = '23505';
        END IF;
        RETURN NEW;
      END; $$ LANGUAGE plpgsql;
      DROP TRIGGER IF EXISTS issue_appeal_once ON inspection_issue_appeals;
      CREATE TRIGGER issue_appeal_once BEFORE INSERT ON inspection_issue_appeals
        FOR EACH ROW EXECUTE FUNCTION claim_issue_appeal_once();
      CREATE TABLE IF NOT EXISTS inspection_issue_appeal_reads (
        appeal_id INTEGER NOT NULL REFERENCES inspection_issue_appeals(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        read_version TIMESTAMPTZ NOT NULL,
        read_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (appeal_id, user_id)
      );
      CREATE INDEX IF NOT EXISTS idx_appeal_reads_user ON inspection_issue_appeal_reads(user_id,appeal_id);
      DO $$ DECLARE definition text; BEGIN
        SELECT pg_get_functiondef('log_issue_lifecycle()'::regprocedure) INTO definition;
        IF position('app.appeal_event' IN definition) = 0 THEN
          definition := replace(definition, 'IF TG_OP = ''INSERT'' THEN',
            'IF TG_OP = ''UPDATE'' AND current_setting(''app.appeal_event'', true) = ''1'' THEN RETURN NEW; END IF; IF TG_OP = ''INSERT'' THEN');
          EXECUTE definition;
        END IF;
      END $$;
    """)


def downgrade():
    op.execute('DROP TRIGGER IF EXISTS issue_appeal_once ON inspection_issue_appeals; DROP FUNCTION IF EXISTS claim_issue_appeal_once();')
    # Keep lifetime claims, read receipts, and original lifecycle evidence.
