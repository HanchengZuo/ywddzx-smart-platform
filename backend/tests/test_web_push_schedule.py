"""Dated arrangements, transactional invalidations and deduplicated outbox, no real sends."""
import importlib.util
import os
from pathlib import Path
from datetime import timedelta
from datetime import date
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import Mock, patch
from psycopg2.extras import Json
from tests import test_web_push as fixtures
from web_push_schedule import current_day, process_schedule_changes, snapshot
from web_push_worker import deliver_one
from tests import test_staff_scheduling as schedule_fixtures


@unittest.skipUnless(os.environ.get('WEB_PUSH_TEST_DSN'),'requires isolated PostgreSQL test database')
class SchedulePushTests(unittest.TestCase):
    connect=classmethod(fixtures.PushDatabaseTests.connect.__func__)
    setUpClass=classmethod(fixtures.PushDatabaseTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.PushDatabaseTests.tearDownClass.__func__)
    call=fixtures.PushDatabaseTests.call
    register=fixtures.PushDatabaseTests.register

    def setUp(self):
        fixtures.PushDatabaseTests.setUp(self)
        self.day=current_day()
        with self.connect() as conn,conn.cursor() as cur:
            cur.execute('TRUNCATE staff_daily_teams,inspection_schedule_tasks,web_push_schedule_changes,web_push_schedule_state')
            cur.execute("UPDATE users SET role=CASE WHEN id=2 THEN 'supervisor_manager' WHEN id=3 THEN 'supervisor' ELSE role END WHERE id IN (2,3)")

    def rows(self,sql,params=()):
        with self.connect() as conn,conn.cursor() as cur:
            cur.execute(sql,params);return cur.fetchall()

    def execute(self,sql,params=()):
        with self.connect() as conn,conn.cursor() as cur:cur.execute(sql,params)

    def people(self):
        return [dict(id=2,mode='offline',group_name='外勤测试组',leader_id=2,display_name='带队人'),
                dict(id=3,mode='offline',group_name='外勤测试组',leader_id=2,display_name='组员')]

    def group(self,people=None,day=None):
        self.execute('''INSERT INTO staff_daily_teams(day,assignments) VALUES(%s,%s)
          ON CONFLICT(day) DO UPDATE SET assignments=EXCLUDED.assignments''',(day or self.day,Json(people if people is not None else self.people())))

    def tasks(self,uid=2,day=None,station=1):
        with self.connect() as conn,conn.cursor() as cur:
            for column in ('safety','metering','service'):
                cur.execute('''INSERT INTO inspection_schedule_tasks(user_id,scheduled_date,mode,station_id,station_name,column_key,table_id,table_name)
                  VALUES(%s,%s,'online',%s,'测试站',%s,1,'视频检查表')''',(uid,day or self.day,station,column))

    def scan(self,day=None):return process_schedule_changes(self.connect,day=day or self.day)

    def messages(self):return self.rows("SELECT * FROM web_push_messages WHERE source='daily_schedule' ORDER BY created_at,id")

    def test_group_confirmation_notifies_only_assigned_supervisor_roles_with_one_personal_message(self):
        self.group(self.people()+[dict(id=1,mode='online',group_name='内勤视频组')])
        self.scan();self.scan()
        self.assertEqual(len(self.messages()),2)
        self.assertEqual({row['user_id'] for row in self.rows('SELECT user_id FROM web_push_recipients')},{2,3})
        self.assertIn('具体站点任务待分配',self.messages()[0]['body'])
        self.assertIn('同行成员',self.messages()[0]['body'])
        self.assertNotIn('带队人',self.messages()[0]['push_hint'])
        record=self.call('/api/management/notifications?log_source=daily_schedule').json
        self.assertEqual(record['records_total'],2)
        self.assertIn('daily_schedule',{entry['key'] for entry in record['sources']})

    def test_multiple_checklist_dispatches_coalesce_and_identical_resaves_or_completion_do_not_notify(self):
        self.tasks();self.scan()
        self.assertEqual(len(self.messages()),1)
        self.assertIn('视频巡检 1 站，共 3 项',self.messages()[0]['body'])
        self.execute("UPDATE inspection_schedule_tasks SET status='completed'");self.scan()
        self.tasks();self.scan()
        self.assertEqual(len(self.messages()),1)
        self.tasks(station=2);self.scan()
        self.assertEqual(len(self.messages()),2)
        self.assertIn('视频巡检 2 站，共 6 项',self.messages()[-1]['body'])

    def test_future_arrangements_wait_until_their_shanghai_date_and_past_changes_do_not_remind(self):
        future=self.day+timedelta(days=3)
        self.group(day=future);self.tasks(day=future)
        self.scan();self.assertFalse(self.messages())
        self.assertTrue(self.rows('SELECT * FROM web_push_schedule_changes'))
        self.scan(future);self.assertEqual(len(self.messages()),2)
        self.execute('DELETE FROM staff_daily_teams');self.scan(future+timedelta(days=1))
        self.assertEqual(len(self.messages()),2)
        self.assertFalse(self.rows('SELECT * FROM web_push_schedule_changes'))

    def test_reordering_unchanged_team_members_is_stable_and_unassigned_roles_are_excluded(self):
        self.group();self.scan()
        self.group(list(reversed(self.people())));self.scan()
        self.assertEqual(len(self.messages()),2)
        self.execute("UPDATE users SET role='station_manager' WHERE id=3")
        with self.connect() as conn,conn.cursor() as cur:self.assertEqual(snapshot(cur,3,self.day)['value'],{})

    def test_rollback_and_worker_error_leave_no_partial_messages_and_retry_is_safe(self):
        conn=self.connect()
        with conn.cursor() as cur:
            cur.execute('INSERT INTO staff_daily_teams(day,assignments) VALUES(%s,%s)',(self.day,Json(self.people())))
        conn.rollback();conn.close();self.scan();self.assertFalse(self.messages())
        self.group()
        with patch('web_push_schedule.enqueue_business',side_effect=RuntimeError('test-only failure')):
            with self.assertRaises(RuntimeError):self.scan()
        self.assertFalse(self.messages());self.assertTrue(self.rows('SELECT * FROM web_push_schedule_changes'))
        self.scan();self.assertEqual(len(self.messages()),2)

    def test_concurrent_workers_do_not_duplicate_personal_reminders(self):
        self.group();self.tasks()
        with ThreadPoolExecutor(4) as pool:list(pool.map(lambda _:self.scan(),range(4)))
        self.assertEqual(len(self.messages()),2)
        self.assertFalse(self.rows('SELECT * FROM web_push_schedule_changes'))

    def test_revoked_changed_or_old_arrangement_is_skipped_before_network_and_fanout_is_retained(self):
        self.register(2);self.register(2,key=fixtures.b64(bytes(range(1,33))),suffix='second')
        self.tasks();self.scan()
        self.assertEqual(len(self.rows('SELECT * FROM web_push_deliveries')),2)
        sender=Mock(return_value=SimpleNamespace(status_code=201))
        with patch('web_push_schedule.current_day',return_value=self.day):
            deliver_one(self.connect,self.app.config['SECRET_KEY'],self.configuration,sender,recipients=lambda *args:[])
        self.assertEqual(sender.call_count,1)
        self.assertEqual(sender.call_args.args[1]['scene'],'daily_schedule')
        self.execute("UPDATE users SET role='station_manager' WHERE id=2")
        with patch('web_push_schedule.current_day',return_value=self.day):
            deliver_one(self.connect,self.app.config['SECRET_KEY'],self.configuration,sender,recipients=lambda *args:[])
        self.assertEqual(sender.call_count,1)
        self.assertEqual(len(self.rows("SELECT * FROM web_push_deliveries WHERE status='skipped'")),1)

    def test_upgrade_does_not_broadcast_existing_today_but_future_plans_remind_when_due(self):
        self.group();future=self.day+timedelta(days=1);self.tasks(day=future)
        path=Path(__file__).parents[1]/'migrations/versions/20261101_003_schedule_push.py'
        spec=importlib.util.spec_from_file_location('schedule_push_baseline',path)
        migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
        with self.connect() as conn,conn.cursor() as cur:
            migration.op=SimpleNamespace(execute=cur.execute);migration.downgrade();migration.upgrade()
        self.scan();self.assertFalse(self.messages())
        self.scan(future);self.assertEqual(len(self.messages()),1)


@unittest.skipUnless(os.environ.get('INSPECTION_SCHEDULE_DB_TEST')=='1','requires isolated test_schedule_ database')
class ScheduleRoutePushTests(unittest.TestCase):
    setUp_base=schedule_fixtures.StaffDatabaseTests.setUp_base
    connect=schedule_fixtures.StaffDatabaseTests.connect
    tearDown=schedule_fixtures.StaffDatabaseTests.tearDown
    save=schedule_fixtures.StaffDatabaseTests.save

    def setUp(self):
        schedule_fixtures.StaffDatabaseTests.setUp(self)
        self.cur.execute("ALTER TABLE inspections ADD COLUMN inspector_completion_status text,ADD COLUMN sign_status text")
        for name in ('20261101_001_web_push','20261101_002_business_push','20261101_003_schedule_push'):
            path=Path(__file__).parents[1]/f'migrations/versions/{name}.py'
            spec=importlib.util.spec_from_file_location(name,path);migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
            migration.op=SimpleNamespace(execute=self.cur.execute);migration.upgrade()
        self.admin.commit()

    def test_actual_whole_row_dispatch_notifies_assignee_once_not_once_per_checklist(self):
        response=self.save();self.assertEqual(response.status_code,200,response.json)
        process_schedule_changes(self.connect,day=date(2026,10,20))
        self.cur.execute("SELECT body FROM web_push_messages WHERE source='daily_schedule'")
        messages=self.cur.fetchall();self.assertEqual(len(messages),1)
        self.assertIn('现场巡检 1 站，视频巡检 0 站，共 6 项',messages[0]['body'])
        self.cur.execute('SELECT user_id FROM web_push_recipients');self.assertEqual(self.cur.fetchall(),[dict(user_id=2)])
        self.assertEqual(self.save(revision=1).status_code,200)
        process_schedule_changes(self.connect,day=date(2026,10,20))
        self.cur.execute('SELECT count(*) AS n FROM web_push_messages');self.assertEqual(self.cur.fetchone()['n'],1)

    def test_late_dispatch_failure_rolls_back_first_checklist_and_its_push_invalidation(self):
        self.cur.execute('''CREATE FUNCTION fail_schedule_push_test() RETURNS trigger AS $$
          BEGIN IF NEW.column_key='finance' THEN RAISE EXCEPTION 'test-only late failure'; END IF; RETURN NEW; END;
          $$ LANGUAGE plpgsql;
          CREATE TRIGGER fail_schedule_push BEFORE INSERT ON inspection_schedule_events
            FOR EACH ROW EXECUTE FUNCTION fail_schedule_push_test();''')
        self.admin.commit()
        with self.assertLogs(level='ERROR'):self.assertEqual(self.save().status_code,500)
        process_schedule_changes(self.connect,day=date(2026,10,20))
        for table in ('inspection_schedule_tasks','web_push_schedule_changes','web_push_messages'):
            self.cur.execute(f'SELECT count(*) AS n FROM {table}');self.assertEqual(self.cur.fetchone()['n'],0)


if __name__=='__main__':unittest.main()
