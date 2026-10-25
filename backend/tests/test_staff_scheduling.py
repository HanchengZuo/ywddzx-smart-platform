"""Isolated PostgreSQL tests. Never run against the application database."""
import os
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch, MagicMock
from flask import Flask, g
import psycopg2
from tests import test_inspection_schedule as schedule_tests
from staff_availability import STAFF, VIEW, EDIT, register_staff_availability, save_availability
from schedule_automation import balanced_allocation, register_schedule_automation
from inspection_schedule_tasks import register_schedule_tasks, task_count


class BalanceTests(unittest.TestCase):
    def test_ordered_roster_and_balanced_initial_day_then_rotation(self):
        self.assertEqual(len(STAFF), 25)
        self.assertEqual(STAFF[0], ('步雪琼', '管理人员'))
        self.assertEqual(STAFF[6], ('芦斌', '管理人员'))
        self.assertTrue(all(position == '管理人员' for _, position in STAFF[:7]))
        self.assertTrue(all(position == '大学生' for _, position in STAFF[7:]))
        self.assertNotIn('孙慧佳', [name for name, _ in STAFF])
        people = [dict(id=i, sequence=i) for i in range(1, 27)]
        demands = {mode: [dict(station_id=i, cells=[1, 2]) for i in range(40)] for mode in ('offline', 'online')}
        loads = {p['id']: dict(offline=0, online=0) for p in people}
        first = balanced_allocation(people, demands, loads)
        self.assertEqual(sum(g['mode'] == 'offline' for g in first), 13)
        self.assertEqual(len({g['person']['id'] for g in first}), 26)
        loads = {g['person']['id']: g['after'] for g in first}
        second = balanced_allocation(people, demands, loads)
        self.assertTrue(all(g['after'] == dict(offline=1, online=1) for g in second))
        self.assertEqual(first, balanced_allocation(people, demands, {p['id']: dict(offline=0, online=0) for p in people}))

    def test_skew_is_corrected_and_exhausted_demand_is_not_fabricated(self):
        p = dict(id=1, sequence=1)
        result = balanced_allocation([p], {'offline': [dict(station_id=1)], 'online': [dict(station_id=2)]}, {1: dict(offline=9, online=1)})
        self.assertEqual(result[0]['mode'], 'online')
        result = balanced_allocation([p], {'offline': [dict(station_id=1)], 'online': []}, {1: dict(offline=9, online=1)})
        self.assertEqual(result[0]['mode'], 'offline')
        self.assertEqual(balanced_allocation([], {}, {}), [])

    def test_authentication_precedes_database_for_all_new_routes(self):
        app = Flask(__name__); connect = MagicMock()
        register_staff_availability(app, connect=connect, has_permission=lambda *_: True)
        register_schedule_automation(app, connect=connect, has_permission=lambda *_: True)
        register_schedule_tasks(app, connect=connect)
        for path, method in [('/api/staff-availability', 'get'), ('/api/staff-availability', 'put'), ('/api/inspection-schedule/auto', 'post'), ('/api/my-schedule-tasks', 'get')]:
            self.assertEqual(getattr(app.test_client(), method)(path).status_code, 401)
        connect.assert_not_called()


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST') == '1', 'isolated database opt-in')
class StaffDatabaseTests(unittest.TestCase):
    setUp_base = schedule_tests.ScheduleDatabaseTest.setUp
    connect = schedule_tests.ScheduleDatabaseTest.connect
    tearDown = schedule_tests.ScheduleDatabaseTest.tearDown
    save = schedule_tests.ScheduleDatabaseTest.save
    board = schedule_tests.ScheduleDatabaseTest.board
    record = schedule_tests.ScheduleDatabaseTest.record

    def setUp(self):
        self.setUp_base()
        self.permissions.update({VIEW, EDIT})
        app = self.client.application
        from tempfile import TemporaryDirectory
        from tests.driving_fakes import fake_driving_service
        self.driving_folder = TemporaryDirectory()
        self.addCleanup(self.driving_folder.cleanup)
        self.driving_service = fake_driving_service(self.driving_folder.name)
        register_staff_availability(app, connect=self.connect, has_permission=lambda _, actor, key: key in self.permissions)
        register_schedule_automation(app, connect=self.connect, has_permission=lambda _, actor, key: key in self.permissions,
                                     driving_service=self.driving_service)
        register_schedule_tasks(app, connect=self.connect)

    def availability(self, name='步雪琼', day='2026-10-19', available=True, **extra):
        self.cur.execute('SELECT revision FROM staff_availability WHERE person_name=%s AND day=%s', (name, day))
        old = self.cur.fetchone()
        return self.client.put('/api/staff-availability', json=dict(cells=[dict(person_name=name, day=day, revision=old['revision'] if old else 0)], available=available, **extra))

    def counts(self):
        self.cur.execute("SELECT (SELECT count(*) FROM inspection_schedule_cells) AS cells,(SELECT count(*) FROM inspection_schedule_tasks WHERE status='pending') AS tasks")
        return dict(self.cur.fetchone())

    def test_permissions_are_independent_and_edit_requires_view(self):
        self.permissions.discard(EDIT)
        self.assertEqual(self.availability().status_code, 403)
        self.assertEqual(self.client.get('/api/staff-availability').status_code, 200)
        self.permissions.discard(VIEW)
        self.assertEqual(self.client.get('/api/staff-availability').status_code, 403)
        self.permissions.discard('edit_inspection_schedule')
        self.assertEqual(self.client.post('/api/inspection-schedule/auto', json=dict(action='preview')).status_code, 403)
        import app as core
        for key in (VIEW, EDIT):
            for role in core.ROLE_OPTIONS: self.assertEqual(core.role_default_permission(role, key), role == 'root')
        self.assertEqual(core.PERMISSION_DEPENDENCIES[EDIT], VIEW)

    def test_calendar_week_holidays_makeup_unknown_and_four_character_reason(self):
        board = self.client.get('/api/staff-availability?week=2025-10-04').json
        self.assertTrue(board['calendar_known'])
        self.assertEqual([d['day'] for d in board['days']], ['2025-09-29', '2025-09-30'])
        board = self.client.get('/api/staff-availability?week=2025-09-28').json
        self.assertIn(dict(day='2025-09-28', weekday='星期日', source=board['days'][-1]['source']), board['days'])
        self.assertFalse(self.client.get('/api/staff-availability?week=2027-01-04').json['calendar_known'])
        self.assertEqual(self.availability(day='2027-01-04').status_code, 400)
        self.assertEqual(self.availability(day='2026-10-24').status_code, 400)
        self.assertEqual(self.availability(day='2026-10-16').status_code, 400)
        self.assertEqual(self.availability(available=False, reason='超过四个汉字').status_code, 400)
        self.assertEqual(self.availability(available=False, reason='外出培训').status_code, 200)
        person = self.client.get('/api/staff-availability?week=2026-10-19').json['people'][0]
        self.assertEqual(person['cells']['2026-10-19']['reason'], '外出培训')
        self.assertEqual(person['cells']['2026-10-19']['updated_by_name'], '步雪琼')

    def test_today_indicators_do_not_change_with_viewed_week_or_count_other_dates(self):
        self.availability(name='步雪琼')
        self.availability(name='孔德辰')
        self.availability(name='赵之龙',available=False,reason='培训')
        self.availability(name='陈中磊',day='2026-10-20',available=False)
        self.record(inspector=2,day='2026-10-16')
        for _ in range(3): self.record(inspector=3,day='2026-10-19')
        expected = dict(free=23,busy=1,unknown=0,offline=1,online=0)
        for week in ('2026-10-12','2026-10-19','2026-10-26'):
            response = self.client.get('/api/staff-availability',query_string=dict(week=week))
            self.assertEqual(response.status_code,200,response.json)
            self.assertEqual(response.json['today_summary'],expected)
        self.record(inspector=2,table=7,day='2026-10-19')
        response = self.client.get('/api/staff-availability?week=2026-10-19')
        self.assertEqual(response.json['today_summary'],dict(free=22,busy=1,unknown=0,offline=1,online=1))

    def test_availability_is_single_cell_only_and_schedule_bulk_stays_atomic(self):
        body = dict(available=True, cells=[dict(person_name='步雪琼', day='2026-10-19', revision=0), dict(person_name='孔德辰', day='2026-10-20', revision=0)])
        response = self.client.put('/api/staff-availability', json=body)
        self.assertEqual(response.status_code, 400)
        self.assertIn('每次只能保存一个单元格', response.json['error'])
        self.cur.execute("SELECT 1 FROM staff_availability WHERE day='2026-10-19'")
        self.assertIsNone(self.cur.fetchone())
        edits = [dict(station_id=sid, column_key=key, revision=9 if sid==2 else 0) for sid in (1,2) for key,_,_ in schedule_tests.COLUMNS['offline']]
        self.assertEqual(self.save(cells=edits).status_code, 409)
        self.assertEqual(self.counts(), dict(cells=0, tasks=0))
        for edit in edits: edit['revision'] = 0
        response = self.save(cells=edits)
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['saved_count'], 12)
        self.assertEqual(self.counts(), dict(cells=12, tasks=12))
        self.assertEqual(self.availability(day='2026-10-20', available=False).status_code, 409)
        self.cur.execute('ALTER TABLE inspection_schedule_tasks ADD CHECK(false) NOT VALID'); self.admin.commit()
        with self.assertLogs(level='ERROR'):
            self.assertEqual(self.save(station_id=3).status_code, 500)
        self.assertEqual(self.counts()['cells'], 12)

    def test_single_availability_save_is_versioned_and_rolls_back_on_audit_failure(self):
        self.assertEqual(self.availability(available=False, reason='出差').status_code, 200)
        response = self.client.put('/api/staff-availability', json=dict(available=True,
            cells=[dict(person_name='步雪琼', day='2026-10-19', revision=0)]))
        self.assertEqual(response.status_code, 409)
        self.cur.execute("SELECT available,reason FROM staff_availability WHERE person_name='步雪琼' AND day='2026-10-19'")
        self.assertEqual(dict(self.cur.fetchone()), dict(available=False, reason='出差'))
        self.cur.execute('ALTER TABLE staff_availability_events ADD CHECK(false) NOT VALID'); self.admin.commit()
        with self.assertLogs(level='ERROR'):
            self.assertEqual(self.availability(available=True).status_code, 500)
        self.cur.execute("SELECT available,reason FROM staff_availability WHERE person_name='步雪琼' AND day='2026-10-19'")
        self.assertEqual(dict(self.cur.fetchone()), dict(available=False, reason='出差'))

    def test_staff_board_separates_saved_modes_from_actual_records_and_cancellation_removes_plan(self):
        self.assertEqual(self.save(inspector_ids=[2]).status_code, 200)
        person = self.client.get('/api/staff-availability?week=2026-10-19').json['people'][0]
        self.assertEqual(person['cells']['2026-10-20']['planned_modes'], ['offline'])
        self.assertEqual(person['cells']['2026-10-20']['actual_modes'], [])
        self.record(day='2026-10-19', inspector=2, table=7)
        person = self.client.get('/api/staff-availability?week=2026-10-19').json['people'][0]
        self.assertEqual(person['cells']['2026-10-19']['planned_modes'], [])
        self.assertEqual(person['cells']['2026-10-19']['actual_modes'], [dict(mode='online', count=1)])
        self.assertEqual(self.save(inspector_ids=[], revision=1).status_code, 200)
        person = self.client.get('/api/staff-availability?week=2026-10-19').json['people'][0]
        self.assertEqual(person['cells']['2026-10-20']['planned_modes'], ['offline'], 'daily team remains separate from station cancellation')

    def test_automatic_schedule_uses_the_same_full_board_for_authorized_area_users(self):
        self.availability(); self.availability(name='孔德辰')
        before = self.client.post('/api/inspection-schedule/auto', json=dict(action='preview', day='2026-10-19')).json
        self.actor = dict(id=4, username='area', real_name='片区用户', role='area_account', station_id=2)
        response = self.client.post('/api/inspection-schedule/auto', json=dict(action='preview', day='2026-10-19'))
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['groups'], before['groups'])
        self.assertEqual(response.json['available_count'], before['available_count'])
        self.assertEqual(self.counts(), dict(cells=0, tasks=0))
        response = self.client.post('/api/inspection-schedule/auto', json=dict(action='confirm', day='2026-10-19', token=response.json['token']))
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(self.counts()['cells'], before['cell_count'])

    def test_availability_and_cross_mode_cannot_be_bypassed_and_shared_lock_serializes(self):
        self.assertEqual(self.save(scheduled_date='2026-10-19').status_code, 400, 'a saved field team is still required')
        self.assertEqual(self.save().status_code, 200)
        response = self.client.put('/api/inspection-schedule', json=dict(mode='online', year=2026, month=10,
            station_id=1, column_key='safety', inspector_ids=[2], scheduled_date='2026-10-20', revision=0,
            cells=[dict(station_id=1,column_key=k,revision=0) for k,_,_ in schedule_tests.COLUMNS['online']]))
        self.assertEqual(response.status_code, 409, response.json)
        conn = self.connect(); other = self.connect()
        try:
            with conn.cursor() as cur: cur.execute('SELECT pg_advisory_xact_lock(9801,1)')
            with other.cursor() as cur:
                cur.execute("SET LOCAL lock_timeout='100ms'")
                with self.assertRaises(psycopg2.errors.LockNotAvailable):
                    save_availability(cur, self.actor, dict(available=False, cells=[dict(person_name='孔德辰', day='2026-10-19', revision=0)]))
        finally: conn.close(); other.close()

    def test_staff_history_is_actual_record_data_not_audit_or_plan(self):
        record = self.record(day='2026-10-19', inspector=2)
        self.cur.execute("INSERT INTO issues(inspection_id,inspector_id,audit_status) VALUES(%s,3,'pending')", (record,)); self.admin.commit()
        self.record(day='2026-10-19', inspector=2, table=7)
        people = self.client.get('/api/staff-availability?week=2026-10-19').json['people']
        self.assertEqual({m['mode'] for m in people[0]['cells']['2026-10-19']['actual_modes']}, {'offline', 'online'})
        self.assertEqual(people[1]['cells']['2026-10-19']['actual_modes'][0]['mode'], 'offline')
        self.assertEqual(people[2]['binding'], 'missing')

    def test_duplicate_or_disabled_accounts_never_receive_automatic_assignment(self):
        self.cur.execute("INSERT INTO users VALUES(90,'same-name','步雪琼','supervisor','active')"); self.admin.commit()
        board = self.client.get('/api/staff-availability?week=2026-10-19').json
        self.assertEqual(board['people'][0]['binding'], 'ambiguous')
        self.assertIsNone(board['people'][0]['id'])
        self.assertEqual(self.save(inspector_ids=[2]).status_code, 400)

    def test_auto_preview_does_not_write_confirm_checks_token_and_repeated_click_is_safe(self):
        self.assertEqual(self.availability().status_code, 200)
        self.assertEqual(self.availability(name='孔德辰').status_code, 200)
        response = self.client.post('/api/inspection-schedule/auto', json=dict(action='preview', day='2026-10-19'))
        self.assertEqual(response.status_code, 200, response.json)
        preview = response.json
        self.assertEqual({g['mode'] for g in preview['groups']}, {'online'}, 'no saved field team today: only video is allowed')
        self.assertEqual(self.counts(), dict(cells=0, tasks=0))
        self.assertEqual(self.availability(available=False).status_code, 200)
        self.assertEqual(self.client.post('/api/inspection-schedule/auto', json=dict(action='confirm', day='2026-10-19', token=preview['token'])).status_code, 409)
        self.assertEqual(self.counts()['cells'], 0)
        self.availability()
        preview = self.client.post('/api/inspection-schedule/auto', json=dict(action='preview', day='2026-10-19')).json
        body = dict(action='confirm', day='2026-10-19', token=preview['token'])
        response = self.client.post('/api/inspection-schedule/auto', json=body)
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(self.counts()['cells'], preview['cell_count'])
        self.assertEqual(self.client.post('/api/inspection-schedule/auto', json=body).status_code, 409)
        self.assertEqual(self.counts()['cells'], preview['cell_count'])

    def test_tasks_persist_overdue_complete_unreviewed_and_reopen_after_record_delete(self):
        def video_save(**overrides):
            return self.client.put('/api/inspection-schedule',json=dict(mode='online',year=2026,month=10,inspector_ids=[2],scheduled_date='2026-10-20',
                cells=[dict(station_id=1,column_key=k,revision=0) for k in ('safety','measurement','service')],**overrides))
        self.cur.execute('DELETE FROM staff_daily_teams'); self.admin.commit()
        self.assertEqual(video_save().status_code, 200)
        # After dispatch, two actual records finish their tasks; the whole row is now immutable.
        self.record(day='2026-10-01',table=8)
        self.record(day='2026-10-01',table=9)
        self.assertEqual(self.client.get('/api/my-schedule-tasks').json['count'], 0, 'future task is not due yet')
        with patch('inspection_schedule_tasks.today', return_value=date(2026, 10, 23)):
            response = self.client.get('/api/my-schedule-tasks?user_id=3')
            self.assertEqual(response.json['count'], 1)
            self.assertEqual(response.json['tasks'][0]['scheduled_date'], '2026-10-20')
            self.assertEqual(response.headers['Cache-Control'], 'private, no-store')
            record = self.record(day='2026-10-21', inspector=4, table=7)  # A different colleague can satisfy coverage.
            self.assertEqual(self.client.get('/api/my-schedule-tasks').json['count'], 0)

            self.cur.execute('DELETE FROM inspections WHERE id=%s', (record,)); self.admin.commit()
            self.assertEqual(self.client.get('/api/my-schedule-tasks').json['count'], 1)
        with patch('inspection_schedule_tasks.today', return_value=date(2027, 1, 6)):
            self.assertEqual(self.client.get('/api/my-schedule-tasks').json['count'], 1)
            self.record(day='2027-01-05', inspector=2,table=7)
            self.assertEqual(self.client.get('/api/my-schedule-tasks').json['count'], 1, 'another month cannot finish the October matrix cell')
            self.record(day='2026-10-31', inspector=2,table=7)
            self.assertEqual(self.client.get('/api/my-schedule-tasks').json['count'], 0)

    def test_auto_exclusions_share_busy_unknown_and_existing_work_reasons(self):
        self.availability(name='步雪琼',available=False)
        self.availability(name='孔德辰',available=False,reason='出差')
        preview = self.client.post('/api/inspection-schedule/auto',json=dict(action='preview',day='2026-10-19'))
        self.assertEqual(preview.status_code,200,preview.json)
        reasons = {p['name']:p['reason'] for p in preview.json['excluded']}
        self.assertEqual(reasons['步雪琼'],'没空')
        self.assertEqual(reasons['孔德辰'],'没空（出差）')
        self.assertEqual(reasons['陈中磊'],'账号未唯一匹配')
        self.availability(name='步雪琼',available=True)
        self.record(inspector=2,day='2026-10-19')
        preview = self.client.post('/api/inspection-schedule/auto',json=dict(action='preview',day='2026-10-19'))
        reasons = {p['name']:p['reason'] for p in preview.json['excluded']}
        self.assertEqual(reasons['步雪琼'],'当天已有站点安排或巡检实绩')

    def test_reassignment_cancels_old_task_with_audit_and_new_task_is_personal(self):
        self.save(inspector_ids=[2])
        response = self.save(revision=1, inspector_ids=[3])
        self.assertEqual(response.status_code, 200, response.json)
        with patch('inspection_schedule_tasks.today', return_value=date(2026, 10, 20)):
            self.assertEqual(self.client.get('/api/my-schedule-tasks?user_id=3').json['count'], 0)
            self.actor = dict(id=3, username='lead', real_name='孔德辰', role='supervisor_manager')
            self.assertEqual(self.client.get('/api/my-schedule-tasks?user_id=2').json['count'], 6)
        self.cur.execute('SELECT status FROM inspection_schedule_tasks ORDER BY id')
        self.assertEqual([r['status'] for r in self.cur.fetchall()], ['cancelled']*6 + ['pending']*6)
        self.cur.execute('SELECT before_ids,after_ids,before_date,after_date FROM inspection_schedule_events ORDER BY id DESC LIMIT 1')
        event = self.cur.fetchone()
        self.assertEqual((event['before_ids'], event['after_ids']), ([2], [3]))
        self.assertEqual(event['after_date'], date(2026, 10, 20))

    def test_migration_rerun_preserves_data_and_never_guesses_legacy_dispatch_dates(self):
        self.cur.execute("INSERT INTO inspection_schedule_cells(mode,year,period_number,station_id,column_key,inspector_ids,revision) VALUES('offline',2026,4,1,'odor','[2]',1)")
        sql = (Path(__file__).resolve().parents[1] / 'db/init/520_staff_scheduling.sql').read_text()
        self.cur.execute(sql); self.cur.execute(sql); self.admin.commit()
        self.assertIsNone(self.board()['rows'][0]['cells']['odor']['scheduled_date'])
        self.assertEqual(self.counts()['tasks'], 0)

    def test_notifications_never_wait_for_an_in_progress_dispatch(self):
        self.save(inspector_ids=[2])
        writer = self.connect(); reader = self.connect()
        try:
            with writer.cursor() as cur: cur.execute('SELECT pg_advisory_xact_lock(9801,1)')
            with reader.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout='300ms'")
                with patch('inspection_schedule_tasks.today', return_value=date(2026,10,20)):
                    self.assertEqual(task_count(cur, 2), 6)
        finally: writer.close(); reader.close()

    def test_reassign_after_deleted_completion_does_not_resurrect_duplicate_pending_tasks(self):
        self.save(inspector_ids=[2])
        record = self.record(day='2026-10-19', inspector=2)
        self.client.get('/api/my-schedule-tasks')
        self.cur.execute('DELETE FROM inspections WHERE id=%s', (record,)); self.admin.commit()
        response = self.save(revision=1, inspector_ids=[3])
        self.assertEqual(response.status_code, 200, response.json)
        with patch('inspection_schedule_tasks.today', return_value=date(2026,10,20)):
            self.assertEqual(self.client.get('/api/my-schedule-tasks').json['count'], 0)
            self.actor = dict(id=3,username='lead',real_name='孔德辰',role='supervisor_manager')
            self.assertEqual(self.client.get('/api/my-schedule-tasks').json['count'], 6)
        self.cur.execute("SELECT status FROM inspection_schedule_tasks ORDER BY id")
        self.assertEqual([r['status'] for r in self.cur.fetchall()], ['cancelled']*6+['pending']*6)
