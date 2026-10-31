"""Coalesced personal daily-arrangement notifications, including future dispatch."""
from alembic import op

revision = '20261101_003'
down_revision = '20261101_002'
branch_labels = depends_on = None


def upgrade():
    op.execute('''CREATE TABLE web_push_schedule_changes (
      id BIGSERIAL PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      day DATE NOT NULL);
    CREATE INDEX web_push_schedule_changes_day ON web_push_schedule_changes(day,user_id,id);
    CREATE TABLE web_push_schedule_state (
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,day DATE NOT NULL,
      fingerprint TEXT NOT NULL,PRIMARY KEY(user_id,day));
    CREATE FUNCTION push_schedule_snapshot(target_user INTEGER,target_day DATE) RETURNS jsonb AS $$
      WITH assignment AS (
        SELECT p.value AS person,d.assignments FROM staff_daily_teams d,
          LATERAL jsonb_array_elements(d.assignments) p
          WHERE d.day=target_day AND p.value->>'id'=target_user::text LIMIT 1
      ), personal AS (
        SELECT jsonb_build_object('mode',person->>'mode','group_name',person->>'group_name',
          'leader_id',person->'leader_id','members',CASE WHEN person->>'mode'='offline' THEN (
            SELECT jsonb_agg(jsonb_build_object('id',m->'id','name',m->>'display_name') ORDER BY m->>'id')
            FROM jsonb_array_elements(assignments) m WHERE m->>'mode'='offline' AND m->'leader_id'=person->'leader_id'
          ) ELSE '[]'::jsonb END) AS value FROM assignment
      ), station_tasks AS (
        SELECT DISTINCT jsonb_build_object('mode',mode,'station_id',station_id,'station_name',station_name,
          'column_key',column_key,'table_name',table_name,'group_name',plan_team->>'name') AS value
          FROM inspection_schedule_tasks WHERE user_id=target_user AND scheduled_date=target_day
          AND status<>'cancelled' AND station_id IS NOT NULL AND table_id IS NOT NULL
      )
      SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM users WHERE id=target_user AND account_status='active'
            AND role IN ('supervisor_manager','supervisor')) THEN '{}'::jsonb
        WHEN NOT EXISTS(SELECT 1 FROM personal) AND NOT EXISTS(SELECT 1 FROM station_tasks) THEN '{}'::jsonb
        ELSE jsonb_build_object('assignment',(SELECT value FROM personal),
          'tasks',COALESCE((SELECT jsonb_agg(value ORDER BY value::text) FROM station_tasks),'[]'::jsonb)) END;
    $$ LANGUAGE sql STABLE;
    CREATE FUNCTION push_schedule_changed() RETURNS trigger AS $$
    BEGIN
      IF TG_TABLE_NAME='staff_daily_teams' THEN
        IF TG_OP<>'INSERT' THEN
          INSERT INTO web_push_schedule_changes(user_id,day)
            SELECT DISTINCT u.id,OLD.day FROM jsonb_array_elements(OLD.assignments) p
              JOIN users u ON u.id::text=p->>'id';
        END IF;
        IF TG_OP<>'DELETE' THEN
          INSERT INTO web_push_schedule_changes(user_id,day)
            SELECT DISTINCT u.id,NEW.day FROM jsonb_array_elements(NEW.assignments) p
              JOIN users u ON u.id::text=p->>'id';
        END IF;
      ELSE
        IF TG_OP='UPDATE' THEN
          IF (NEW.user_id,NEW.scheduled_date,NEW.mode,NEW.station_id,NEW.column_key,NEW.table_id,NEW.plan_team,NEW.status='cancelled')
            IS NOT DISTINCT FROM (OLD.user_id,OLD.scheduled_date,OLD.mode,OLD.station_id,OLD.column_key,OLD.table_id,OLD.plan_team,OLD.status='cancelled') THEN
            RETURN NULL;
          END IF;
        END IF;
        IF TG_OP<>'INSERT' THEN
          INSERT INTO web_push_schedule_changes(user_id,day) VALUES(OLD.user_id,OLD.scheduled_date);
        END IF;
        IF TG_OP<>'DELETE' THEN
          INSERT INTO web_push_schedule_changes(user_id,day) VALUES(NEW.user_id,NEW.scheduled_date);
        END IF;
      END IF;
      RETURN NULL;
    END; $$ LANGUAGE plpgsql;
    CREATE TRIGGER push_schedule_team_change AFTER INSERT OR DELETE OR UPDATE OF assignments,day ON staff_daily_teams
      FOR EACH ROW EXECUTE FUNCTION push_schedule_changed();
    CREATE TRIGGER push_schedule_task_change AFTER INSERT OR DELETE OR UPDATE OF user_id,scheduled_date,mode,station_id,column_key,table_id,plan_team,status ON inspection_schedule_tasks
      FOR EACH ROW EXECUTE FUNCTION push_schedule_changed();
    -- Existing today's plans are a baseline, not a mass resend. Future plans remain due on their date.
    INSERT INTO web_push_schedule_changes(user_id,day)
      SELECT user_id,scheduled_date FROM inspection_schedule_tasks
        WHERE scheduled_date>=(CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai')::date AND status<>'cancelled'
      UNION SELECT u.id,d.day FROM staff_daily_teams d,LATERAL jsonb_array_elements(d.assignments) p
        JOIN users u ON u.id::text=p->>'id' WHERE d.day>=(CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai')::date;
    INSERT INTO web_push_schedule_state(user_id,day,fingerprint)
      SELECT DISTINCT user_id,day,md5(push_schedule_snapshot(user_id,day)::text) FROM web_push_schedule_changes
        WHERE day=(CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai')::date;''')


def downgrade():
    op.execute('''DROP TRIGGER push_schedule_team_change ON staff_daily_teams;
    DROP TRIGGER push_schedule_task_change ON inspection_schedule_tasks;
    DROP FUNCTION push_schedule_changed(); DROP FUNCTION push_schedule_snapshot(integer,date);
    DROP TABLE web_push_schedule_changes,web_push_schedule_state;''')
