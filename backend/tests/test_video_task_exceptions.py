"""Station waivers: self-only authority, intact evidence and cross-worker serialization."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from flask import Flask, g
from tests import test_schedule_inbox_progress as inbox_tests
from schedule_video_exceptions import register_video_exceptions, report_exception
from staff_schedule_history import dispatch_history


class ExceptionAuthTests(unittest.TestCase):
    def test_auth_precedes_database_and_connection_errors_are_redacted(self):
        app = Flask(__name__)
        actor = None
        app.before_request(lambda: setattr(g, 'current_user', actor))
        connect = MagicMock(side_effect=RuntimeError('private credentials'))
        register_video_exceptions(app, connect=connect)
        client = app.test_client()
        self.assertEqual(client.post('/api/my-schedule-tasks/1/video-exception', json={'reason': '故障'}).status_code, 401)
        connect.assert_not_called()
        actor = {'id': 2}
        with self.assertLogs(level='ERROR'):
            response = client.post('/api/my-schedule-tasks/1/video-exception', json={'reason': '故障'})
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('private', response.get_data(as_text=True))


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST') == '1', 'isolated database opt-in')
class ExceptionDatabaseTests(unittest.TestCase):
    setUp_base = inbox_tests.InboxDatabaseTests.setUp_base
    connect = inbox_tests.InboxDatabaseTests.connect
    tearDown = inbox_tests.InboxDatabaseTests.tearDown
    availability = inbox_tests.InboxDatabaseTests.availability
    save = inbox_tests.InboxDatabaseTests.save
    board = inbox_tests.InboxDatabaseTests.board
    record = inbox_tests.InboxDatabaseTests.record
    video = inbox_tests.InboxDatabaseTests.video
    inbox = inbox_tests.InboxDatabaseTests.inbox
    def setUp(self):
        inbox_tests.InboxDatabaseTests.setUp(self)
        for module in ('inspection_schedule_tasks', 'schedule_video_exceptions', 'inspection_schedule', 'schedule_common', 'inspection_schedule_dispatch', 'schedule_automation'):
            clock = patch(module + '.today', return_value=date(2026, 10, 20))
            clock.start(); self.addCleanup(clock.stop)
        self.video()
        self.task_id = self.inbox()['tasks'][0]['id']

    def report(self, reason='监控故障，无法查看视频。', task_id=None):
        return self.client.post(f'/api/my-schedule-tasks/{task_id or self.task_id}/video-exception',
                                json=dict(reason=reason, user_id=1))

    def online(self):
        return self.board(dict(mode='online', year=2026, month=10))

    def test_station_waiver_closes_three_pending_tasks_without_faking_records_or_deleting_plan(self):
        before = self.online()
        self.permissions.clear()  # A task owner needs no schedule administration permission.
        response = self.report('  监控故障  ')
        self.assertEqual(response.status_code, 200, response.json)
        audit = response.json['video_exception']
        self.assertEqual((audit['reason'], audit['reported_by'], audit['reporter_name']), ('监控故障', 2, '步雪琼'))
        data = self.inbox()
        self.assertEqual((data['count'], data['agenda']['online']['count']), (0, 0))
        self.assertEqual([t['status'] for t in data['tasks']], ['exception'] * 3)
        self.assertEqual(data['exception_counts']['today_online'], 3)
        self.assertTrue(all(not t['record_count'] and t['completion_inspection_id'] is None for t in data['tasks']))
        self.permissions.add('view_inspection_schedule')
        after = self.online()
        row = next(r for r in after['rows'] if r['station_id'] == 1)
        self.assertTrue(row['locked'])
        self.assertTrue(all(c['status'] == 'exception' and c['video_exception']['id'] == audit['id'] for c in row['cells'].values()))
        self.assertTrue(all(c['assignees'][0]['id'] == 2 and c['revision'] == 1 for c in row['cells'].values()))
        self.assertNotEqual(before['board_token'], after['board_token'])
        self.cur.execute('SELECT task_ids,dispatch_snapshot FROM inspection_schedule_video_exceptions')
        stored = self.cur.fetchone()
        self.assertEqual(len(stored['task_ids']), 3)
        self.assertEqual(len(stored['dispatch_snapshot']['cells']), 3)
        self.cur.execute('SELECT COUNT(*) AS n FROM inspections'); self.assertEqual(self.cur.fetchone()['n'], 0)
        self.cur.execute("SELECT COUNT(*) AS n FROM inspection_schedule_tasks WHERE status='pending'")
        self.assertEqual(self.cur.fetchone()['n'], 3)  # Cache is not mislabelled 'completed'.

    def test_partial_real_evidence_survives_and_history_is_resolved_without_actuals_fabrication(self):
        rid = self.record(table=7, day='2026-10-20')
        self.assertEqual(self.report().status_code, 200)
        data = self.inbox()
        self.assertEqual(next(t for t in data['tasks'] if t['record_count'])['completion_inspection_id'], rid)
        with self.connect() as conn:
            history = dispatch_history(conn.cursor(), [2], date(2026,10,20), date(2026,10,21), date(2026,10,21), details=True)
        summary = history[(2, '2026-10-20')]['summary']
        self.assertEqual((summary['completed'], summary['exempted'], summary['resolved'], summary['percent']), (1, 2, 3, 100))
        self.cur.execute('DELETE FROM inspections'); self.admin.commit()
        with self.connect() as conn:
            summary = dispatch_history(conn.cursor(), [2], date(2026,10,20), date(2026,10,21), date(2026,10,21))[(2,'2026-10-20')]['summary']
        self.assertFalse(summary['has_actual'])
        self.assertEqual(summary['actual_modes'], [])
        self.assertEqual(self.inbox()['count'], 0)

    def test_wrong_owner_cancelled_future_incomplete_and_field_tasks_cannot_waive(self):
        self.actor = dict(id=3, username='lead', real_name='孔德辰', role='supervisor_manager')
        self.assertEqual(self.report().status_code, 403)
        self.actor = dict(id=2, username='staff', real_name='步雪琼', role='supervisor')
        for update in ("status='cancelled'", "scheduled_date='2026-10-21'", "mode='offline'"):
            self.cur.execute(f'UPDATE inspection_schedule_tasks SET {update} WHERE id=%s', (self.task_id,)); self.admin.commit()
            self.assertIn(self.report().status_code, (400,409))
            self.cur.execute("UPDATE inspection_schedule_tasks SET status='pending',scheduled_date='2026-10-20',mode='online' WHERE id=%s", (self.task_id,)); self.admin.commit()
        self.cur.execute("UPDATE inspection_schedule_cells SET inspector_ids='[3]' WHERE column_key='service'"); self.admin.commit()
        self.assertEqual(self.report().status_code, 409)
        self.cur.execute('SELECT COUNT(*) AS n FROM inspection_schedule_video_exceptions'); self.assertEqual(self.cur.fetchone()['n'], 0)

    def test_reason_required_and_completed_station_cannot_be_waived(self):
        for reason in ('', '   ', None, 2, '长' * 501):
            self.assertEqual(self.report(reason).status_code, 400)
        for table in (7, 8, 9): self.record(table=table, day='2026-10-20')
        self.assertEqual(self.report().status_code, 409)

    def test_duplicate_is_idempotent_different_reason_conflicts_and_concurrent_submissions_create_one_audit(self):
        actor = dict(self.actor)
        def submit():
            conn = self.connect()
            try:
                result = report_exception(conn.cursor(), actor, self.task_id, '监控故障')
                conn.commit()
                return result['id']
            finally: conn.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(lambda _: submit(), range(2)))
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(self.report('监控故障').status_code, 200)
        self.assertEqual(self.report('另一个原因').status_code, 409)
        self.cur.execute('SELECT COUNT(*) AS n FROM inspection_schedule_video_exceptions'); self.assertEqual(self.cur.fetchone()['n'], 1)

    def test_exception_is_month_specific_and_history_no_longer_pending(self):
        with patch('schedule_video_exceptions.today', return_value=date(2026,10,21)), patch('inspection_schedule_tasks.today', return_value=date(2026,10,21)):
            self.assertEqual(self.inbox(bucket='history_online')['count'], 3)
            self.assertEqual(self.report().status_code, 200)
            self.assertEqual(self.inbox(bucket='history_online')['tasks'], [])
        november = self.board(dict(mode='online', year=2026, month=11))
        self.assertTrue(all(c['status']=='unassigned' for r in november['rows'] for c in r['cells'].values()))
        self.assertTrue(all(c['status']=='unassigned' for r in self.board()['rows'] for c in r['cells'].values()))

    def test_direct_edit_dispatch_and_clear_cannot_remove_exception(self):
        self.assertEqual(self.report().status_code, 200)
        edits = [dict(station_id=1, column_key=k, revision=1) for k in ('safety','measurement','service')]
        response = self.client.put('/api/inspection-schedule', json=dict(mode='online', year=2026, month=10, cells=edits, inspector_ids=[]))
        self.assertEqual(response.status_code, 409)
        response = self.client.post('/api/inspection-schedule/dispatch', json=dict(action='park', mode='online', year=2026, month=10, cells=edits))
        self.assertEqual(response.status_code, 409, response.json)
        response = self.client.post('/api/inspection-schedule/dispatch', json=dict(action='clear_today',mode='online',year=2026,month=10))
        self.assertEqual(response.status_code,409)
        response = self.client.post('/api/inspection-schedule/dispatch', json=dict(action='clear_today',mode='online',year=2026,month=10,board_token=self.online()['board_token']))
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(response.json['cleared_count'],0)
        self.assertTrue(next(r for r in self.online()['rows'] if r['station_id']==1)['locked'])

    def test_smart_projection_and_today_confirmation_keep_exception_separate(self):
        from schedule_smart import planning_board, apply_smart_plan
        from schedule_row_state import today_assignments
        from schedule_period import period
        self.assertEqual(self.report().status_code,200)
        board=self.online()
        row=next(r for r in planning_board(board,date(2026,10,20))['rows'] if r['station_id']==1)
        self.assertTrue(row['locked'])
        self.assertTrue(all(c['status']=='exception' for c in row['cells'].values()))
        confirmation=today_assignments([board],date(2026,10,20))
        self.assertEqual((confirmation[0]['completed'],confirmation[0]['exempted']),(0,3))
        self.assertEqual(confirmation[0]['stations'][0]['video_exception']['reason'],'监控故障，无法查看视频。')
        periods={mode:period(dict(mode=mode,year=2026,**({'quarter':4} if mode=='offline' else {'month':10} if mode=='online' else {})))
                 for mode in ('offline','online','annual')}
        with self.connect() as conn:
            self.assertEqual(apply_smart_plan(conn.cursor(),self.actor,dict(groups=[]),periods,date(2026,10,20)),0)
        self.assertEqual(self.online()['rows'],board['rows'])

    def test_error_after_insert_rolls_back_the_audit_and_does_not_resolve_pending(self):
        real_report=report_exception
        def fail_after_insert(*args):
            real_report(*args)
            raise RuntimeError('private post-insert failure')
        with patch('schedule_video_exceptions.report_exception',side_effect=fail_after_insert), self.assertLogs(level='ERROR'):
            response=self.report()
        self.assertEqual(response.status_code,500)
        self.assertNotIn('private',response.get_data(as_text=True))
        self.cur.execute('SELECT COUNT(*) AS n FROM inspection_schedule_video_exceptions');self.assertEqual(self.cur.fetchone()['n'],0)
        self.assertEqual(self.inbox()['count'],3)

    def test_audit_failure_rolls_back_and_schema_is_idempotent(self):
        self.cur.execute((Path(__file__).resolve().parents[1] / 'db/init/570_video_task_exceptions.sql').read_text())
        self.cur.execute('ALTER TABLE inspection_schedule_video_exceptions ADD CHECK(false) NOT VALID'); self.admin.commit()
        with self.assertLogs(level='ERROR'):
            response = self.report()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.inbox()['count'], 3)
        self.assertTrue(all(c['status']=='assigned' for r in self.online()['rows'] if r['station_id']==1 for c in r['cells'].values()))
        self.cur.execute('SELECT COUNT(*) AS n FROM inspection_schedule_video_exceptions'); self.assertEqual(self.cur.fetchone()['n'], 0)
