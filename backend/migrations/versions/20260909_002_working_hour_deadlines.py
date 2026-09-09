"""Independent review clocks and holiday-aware working hours (Shanghai timezone)."""
from datetime import date, timedelta
import chinese_calendar as calendar
from alembic import op

revision = '20260909_002'
down_revision = '20260909_001'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE IF NOT EXISTS quality_work_calendar (
      day date PRIMARY KEY, working boolean NOT NULL, source text NOT NULL);
      ALTER TABLE quality_deadline_policy ADD COLUMN IF NOT EXISTS working_hours_migrated boolean NOT NULL DEFAULT false;
      ALTER TABLE inspection_issue_appeals ADD COLUMN IF NOT EXISTS review_phase text;
      ALTER TABLE inspection_issue_appeals ADD COLUMN IF NOT EXISTS area_timeout_at timestamptz;
      ALTER TABLE inspection_issue_appeals ADD COLUMN IF NOT EXISTS quality_timeout_at timestamptz;
    ''')
    # A complete year includes weekend make-up days, not just the holiday list.
    first = min(calendar.holidays).year
    last = max(calendar.holidays).year
    rows = []
    day = date(first, 1, 1)
    while day <= date(last, 12, 31):
        rows.append(f"('{day.isoformat()}',{str(calendar.is_workday(day)).lower()},'chinesecalendar-{calendar.__version__}')")
        day += timedelta(days=1)
    op.execute('INSERT INTO quality_work_calendar(day,working,source) VALUES ' + ','.join(rows) + ' ON CONFLICT(day) DO NOTHING')
    for stage in ('acceptance', 'appeal', 'area_review', 'quality_review'):
        op.execute(f'''ALTER TABLE quality_deadline_policy ADD COLUMN IF NOT EXISTS {stage}_hours integer NOT NULL DEFAULT 72 CHECK ({stage}_hours BETWEEN 1 AND 8760);''')
        if stage.endswith('review'):
            op.execute(f'''ALTER TABLE quality_deadline_policy ADD COLUMN IF NOT EXISTS {stage}_enabled boolean NOT NULL DEFAULT true;
              ALTER TABLE quality_deadline_policy ADD COLUMN IF NOT EXISTS {stage}_enabled_at timestamptz;
              ALTER TABLE quality_deadline_policy ADD COLUMN IF NOT EXISTS {stage}_enabled_policy jsonb;
              ALTER TABLE quality_deadline_policy ADD COLUMN IF NOT EXISTS {stage}_timeout_action text NOT NULL DEFAULT 'manual'
                CHECK ({stage}_timeout_action IN ('manual','approve','reject'));''')
        old = 'review' if stage.endswith('review') else stage
        op.execute(f'''UPDATE quality_deadline_policy SET {stage}_hours={old}_days*24,
          {stage}_enabled={old}_enabled, {stage}_enabled_at=CURRENT_TIMESTAMP,
          {stage}_enabled_policy=jsonb_build_object('{stage}_hours',{old}_days*24,'version',version+1,'timeout_action',timeout_action)
          {f", {stage}_timeout_action=timeout_action" if stage.endswith('review') else ''}
          WHERE NOT working_hours_migrated;''')
    op.execute('''WITH changed AS (
      UPDATE quality_deadline_policy SET working_hours_migrated=true,version=version+1,updated_at=CURRENT_TIMESTAMP,updated_by=NULL
      WHERE NOT working_hours_migrated RETURNING *)
      INSERT INTO quality_deadline_events(kind,detail,policy,actor)
      SELECT 'policy_migrated','v7.1迁移：两级独立工作小时计时，旧天数乘24，未结束任务获得完整新期限，原开关与超时方式保留。',to_jsonb(changed),
        '{"name":"系统版本迁移"}'::jsonb FROM changed;

    CREATE OR REPLACE FUNCTION quality_add_work_hours(start_at timestamptz, hours integer)
    RETURNS timestamptz LANGUAGE plpgsql STABLE AS $$
    DECLARE cursor_at timestamp := start_at AT TIME ZONE 'Asia/Shanghai';
      remaining_seconds double precision := hours * 3600.0; available double precision; work boolean;
    BEGIN
      IF start_at IS NULL OR hours IS NULL OR hours < 1 THEN RETURN NULL; END IF;
      WHILE remaining_seconds > 0 LOOP
        SELECT working INTO work FROM quality_work_calendar WHERE day=cursor_at::date;
        -- Missing official calendar is not permission to auto-approve or reject.
        IF NOT FOUND THEN RETURN NULL; END IF;
        available := EXTRACT(EPOCH FROM (cursor_at::date + 1)::timestamp - cursor_at);
        IF work THEN
          IF remaining_seconds <= available THEN
            RETURN (cursor_at + make_interval(secs=>remaining_seconds)) AT TIME ZONE 'Asia/Shanghai';
          END IF;
          remaining_seconds := remaining_seconds - available;
        END IF;
        cursor_at := (cursor_at::date + 1)::timestamp;
      END LOOP;
      RETURN cursor_at AT TIME ZONE 'Asia/Shanghai';
    END $$;

    CREATE OR REPLACE FUNCTION quality_effective_deadline(phase text, deadline timestamptz, started timestamptz)
    RETURNS timestamptz AS $$
    DECLARE cfg jsonb; enabled_at timestamptz;
    BEGIN
      SELECT to_jsonb(p) INTO cfg FROM quality_deadline_policy p WHERE id=1;
      IF NOT COALESCE((cfg->>(phase || '_enabled'))::boolean,false) THEN RETURN NULL; END IF;
      enabled_at := (cfg->>(phase || '_enabled_at'))::timestamptz;
      IF started IS NULL OR started < enabled_at THEN
        RETURN quality_add_work_hours(enabled_at,(cfg->(phase || '_enabled_policy')->>(phase || '_hours'))::integer);
      END IF;
      RETURN deadline;
    END; $$ LANGUAGE plpgsql STABLE;
    ''')
    # Keep existing trigger guards, lock ordering and audit integration intact.
    op.execute("""DO $$ DECLARE definition text; signature text; BEGIN
      FOREACH signature IN ARRAY ARRAY['refresh_quality_acceptance(integer)','quality_issue_appeal_window()'] LOOP
        SELECT pg_get_functiondef(to_regprocedure(signature)) INTO definition;
        definition := replace(replace(definition,'acceptance_days','acceptance_hours'),'appeal_days','appeal_hours');
        definition := replace(definition,'ready_at + make_interval(days=>CASE','quality_add_work_hours(ready_at,CASE');
        definition := replace(definition,'ELSIF rec.quality_accept_started_at IS NULL OR ready_at > rec.quality_accept_started_at THEN',
          'ELSIF rec.quality_accept_started_at IS NULL OR ready_at > rec.quality_accept_started_at OR rec.quality_accept_deadline_at IS NULL THEN');
        definition := replace(definition,'quality_add_work_hours(ready_at,CASE WHEN ready_at=cfg.acceptance_enabled_at',
          'quality_add_work_hours(ready_at,CASE WHEN rec.quality_accept_started_at=ready_at AND rec.quality_accept_policy ? ''acceptance_hours'' THEN (rec.quality_accept_policy->>''acceptance_hours'')::integer WHEN ready_at=cfg.acceptance_enabled_at');
        definition := replace(definition,'quality_accept_policy=CASE WHEN ready_at=cfg.acceptance_enabled_at',
          'quality_accept_policy=CASE WHEN rec.quality_accept_started_at=ready_at AND rec.quality_accept_policy ? ''acceptance_hours'' THEN rec.quality_accept_policy WHEN ready_at=cfg.acceptance_enabled_at');
        IF position('previous_start timestamptz' in definition)=0 THEN
          definition := replace(definition,'DECLARE ins record; cfg record;',
            'DECLARE ins record; cfg record; previous_start timestamptz := NEW.quality_appeal_started_at;');
        END IF;
        definition := replace(definition,'NEW.quality_appeal_policy := CASE WHEN NEW.quality_appeal_started_at=cfg.appeal_enabled_at',
          'NEW.quality_appeal_policy := CASE WHEN previous_start=NEW.quality_appeal_started_at AND NEW.quality_appeal_policy ? ''appeal_hours'' THEN NEW.quality_appeal_policy WHEN NEW.quality_appeal_started_at=cfg.appeal_enabled_at');
        definition := replace(definition,
          'NEW.quality_appeal_started_at + make_interval(days=>(NEW.quality_appeal_policy->>''appeal_hours'')::integer)',
          'quality_add_work_hours(NEW.quality_appeal_started_at,(NEW.quality_appeal_policy->>''appeal_hours'')::integer)');
        EXECUTE definition;
      END LOOP;
    END $$;""")


def downgrade():
    # Do not discard calendar, hour policies or lifecycle evidence. Stop workers before rollback.
    pass
