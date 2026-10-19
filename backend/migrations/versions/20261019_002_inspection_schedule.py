"""Replace plan runtime with an independently authorized scheduling matrix."""
from pathlib import Path
from alembic import op

revision = '20261019_002'
down_revision = '20261019_001'
branch_labels = None
depends_on = None


def upgrade():
    op.execute((Path(__file__).resolve().parents[2] / 'db/init/515_inspection_schedule.sql').read_text())
    # No inheritance from the retired plan permissions. Root assigns access afresh.
    for table in ('user_permissions', 'role_permissions'):
        op.execute(f"DELETE FROM {table} WHERE permission_key IN ('view_inspection_plans', 'manage_inspection_plans')")
    # Legacy rows are inert, but their old restrictive FK must not block record deletion.
    op.execute('''DO $$ DECLARE reference record; BEGIN
      IF to_regclass('inspection_plan_station_items') IS NOT NULL THEN
        FOR reference IN SELECT conname FROM pg_constraint
          WHERE conrelid=to_regclass('inspection_plan_station_items')
            AND confrelid=to_regclass('inspections') AND contype='f'
        LOOP
          EXECUTE format('ALTER TABLE inspection_plan_station_items DROP CONSTRAINT %I',reference.conname);
        END LOOP;
        ALTER TABLE inspection_plan_station_items ADD CONSTRAINT legacy_plan_completed_inspection_fk
          FOREIGN KEY(completed_inspection_id) REFERENCES inspections(id) ON DELETE SET NULL;
      END IF;
    END $$''')


def downgrade():
    # Keep saved schedules and their attribution when rolling back application code.
    pass
