"""v11.6 unstarted dispatch reassignment; isolated PostgreSQL schemas only."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from time import sleep
from unittest.mock import patch
from zoneinfo import ZoneInfo
from tests import test_staff_team_execution as execution


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST') == '1', 'isolated database opt-in')
class ReassignmentTests(unittest.TestCase):
    setUp = execution.TeamExecutionTests.setUp
    setUp_base = execution.TeamExecutionTests.setUp_base
    tearDown = execution.TeamExecutionTests.tearDown
    connect = execution.TeamExecutionTests.connect
    availability = execution.TeamExecutionTests.availability
    save = execution.TeamExecutionTests.save
    post = execution.TeamExecutionTests.post
    confirm = execution.TeamExecutionTests.confirm
    board = execution.TeamExecutionTests.board
    assign = execution.TeamExecutionTests.assign
    current = execution.TeamExecutionTests.current
    adopt = execution.TeamExecutionTests.adopt
    dispatched = execution.TeamExecutionTests.dispatched
    record = execution.TeamExecutionTests.record
    assign_annual = execution.TeamExecutionTests.assign_annual

    def video_dispatch(self, sid=2):
        current = self.current()
        group = next(g for g in current['groups'] if g['mode'] == 'online')
        person = next(p for p in group['members'] if p['position'] == '大学生')
        result = self.assign(dict(group, members=[person]), sid=sid)
        self.assertEqual(result.status_code, 200, result.json)
        return person

    def active_tasks(self, uid, mode=None):
        self.cur.execute("SELECT * FROM inspection_schedule_tasks WHERE user_id=%s AND status<>'cancelled' ORDER BY id", (uid,))
        return [dict(r) for r in self.cur.fetchall() if not mode or r['mode'] == mode]

    def test_dispatched_field_student_busy_keeps_station_and_retires_only_their_tasks(self):
        group, _ = self.dispatched()
        child = next(p for p in group['members'] if p['position'] == '大学生')
        result = self.availability(name=child['display_name'], available=False, reason='培训')
        self.assertEqual(result.status_code, 200, result.json)
        expected = {p['id'] for p in group['members']} - {child['id']}
        self.cur.execute("SELECT inspector_ids FROM inspection_schedule_cells WHERE station_id=1 AND mode='offline'")
        cells = self.cur.fetchall()
        self.assertEqual(len(cells), 6)
        self.assertTrue(all(set(r['inspector_ids']) == expected for r in cells))
        self.assertEqual(self.active_tasks(child['id']), [])
        self.cur.execute('SELECT status,plan_team FROM inspection_schedule_tasks WHERE user_id=%s', (child['id'],))
        retired = self.cur.fetchall()
        self.assertEqual(len(retired), 6)
        self.assertTrue(all(r['status'] == 'cancelled' and child['id'] in {p['id'] for p in r['plan_team']['members']} for r in retired))
        self.assertEqual(len(self.active_tasks(2)), 6)

    def test_video_busy_clears_whole_station_preserves_history_and_can_return_to_pool(self):
        self.confirm()
        person = self.video_dispatch()
        result = self.availability(name=person['display_name'], available=False, reason='休假')
        self.assertEqual(result.status_code, 200, result.json)
        self.cur.execute("SELECT inspector_ids,scheduled_date FROM inspection_schedule_cells WHERE mode='online' AND station_id=2")
        rows = self.cur.fetchall()
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(not r['inspector_ids'] and r['scheduled_date'] is None for r in rows))
        self.assertEqual(self.active_tasks(person['id']), [])
        self.cur.execute('SELECT COUNT(*) n FROM inspection_schedule_tasks WHERE user_id=%s AND status=\'cancelled\'', (person['id'],))
        self.assertEqual(self.cur.fetchone()['n'], 3)
        self.assertNotIn(person['id'], {p['id'] for g in self.current()['groups'] for p in g['members']})
        self.assertEqual(self.availability(name=person['display_name'], available=True).status_code, 200)
        self.assertIn(person['id'], {p['id'] for p in self.current()['unassigned_people']})

    def test_video_to_field_clears_video_and_takes_group_tasks_in_one_commit(self):
        group, _ = self.dispatched()
        person = self.video_dispatch()
        result = self.adopt(self.current(), [dict(person_id=person['id'], leader_id=2)])
        self.assertEqual(result.status_code, 200, result.json)
        self.assertEqual(self.active_tasks(person['id'], 'online'), [])
        self.assertEqual(len(self.active_tasks(person['id'], 'offline')), 6)
        self.cur.execute("SELECT inspector_ids FROM inspection_schedule_cells WHERE mode='online' AND station_id=2")
        self.assertTrue(all(not r['inspector_ids'] for r in self.cur.fetchall()))
        self.cur.execute("SELECT inspector_ids,plan_team FROM inspection_schedule_cells WHERE mode='offline' AND station_id=1")
        expected = {p['id'] for p in group['members']} | {person['id']}
        self.assertTrue(all(set(r['inspector_ids']) == expected and {p['id'] for p in r['plan_team']['members']} == expected for r in self.cur.fetchall()))

    def test_field_to_video_cancels_old_personal_tasks_without_inventing_video_stations(self):
        group, _ = self.dispatched()
        child = next(p for p in group['members'] if p['position'] == '大学生')
        result = self.adopt(self.current(), [dict(person_id=child['id'], leader_id=None)])
        self.assertEqual(result.status_code, 200, result.json)
        self.assertEqual(self.active_tasks(child['id']), [])
        self.cur.execute("SELECT inspector_ids FROM inspection_schedule_cells WHERE mode='offline' AND station_id=1")
        self.assertTrue(all(child['id'] not in r['inspector_ids'] and 2 in r['inspector_ids'] for r in self.cur.fetchall()))
        self.cur.execute("SELECT inspector_ids FROM inspection_schedule_shelf WHERE mode='online' AND status='waiting'")
        self.assertTrue(any(r['inspector_ids'] == [child['id']] for r in self.cur.fetchall()))

    def test_today_video_retirement_preserves_future_dispatch_and_other_dates_pending_tasks(self):
        self.confirm()
        person = self.video_dispatch()
        self.cur.execute('''INSERT INTO staff_availability(person_name,day,available,revision,updated_by)
          SELECT person_name,'2026-10-20',available,1,1 FROM staff_availability WHERE day='2026-10-19'
          ON CONFLICT(person_name,day) DO UPDATE SET available=EXCLUDED.available''')
        self.cur.execute('''INSERT INTO staff_daily_teams(day,assignments,revision,updated_by)
          SELECT '2026-10-20',assignments,1,1 FROM staff_daily_teams WHERE day='2026-10-19' ''')
        self.cur.execute('UPDATE stations SET include_online_plan=true WHERE id=3')
        self.cur.execute('''INSERT INTO inspection_schedule_tasks(mode,year,period_number,station_id,column_key,
          station_name,table_id,table_name,user_id,team_ids,scheduled_date,period_start,created_by)
          SELECT mode,year,period_number,station_id,column_key,station_name,table_id,table_name,3,'[3]',
            '2026-10-16',period_start,1 FROM inspection_schedule_tasks WHERE user_id=%s AND mode='online' LIMIT 1 RETURNING id''', (person['id'],))
        historical = self.cur.fetchone()['id']
        self.admin.commit()
        board = self.board('online')
        row = next(r for r in board['rows'] if r['station_id'] == 3)
        result = self.client.put('/api/inspection-schedule', json=dict(mode='online',year=2026,month=10,
            scheduled_date='2026-10-20',inspector_ids=[person['id']],cells=[dict(station_id=3,column_key=k,revision=c['revision']) for k,c in row['cells'].items()]))
        self.assertEqual(result.status_code, 200, result.json)
        result = self.availability(name=person['display_name'], available=False)
        self.assertEqual(result.status_code, 200, result.json)
        remaining = self.active_tasks(person['id'])
        self.assertEqual(len(remaining), 3)
        self.assertTrue(all(str(t['scheduled_date']) == '2026-10-20' and t['station_id'] == 3 for t in remaining))
        self.cur.execute('SELECT status FROM inspection_schedule_tasks WHERE id=%s', (historical,))
        self.assertEqual(self.cur.fetchone()['status'], 'pending')
        result = self.availability(name=person['display_name'], day='2026-10-20', available=False)
        self.assertEqual(result.status_code, 200, result.json)
        self.assertEqual(self.active_tasks(person['id']), [])
        self.cur.execute('SELECT status FROM inspection_schedule_tasks WHERE id=%s', (historical,))
        self.assertEqual(self.cur.fetchone()['status'], 'pending')

    def test_leader_busy_dissolves_group_and_cancels_both_linked_field_boards(self):
        saved = self.confirm().json
        group = next(g for g in saved['groups'] if g['leader_id'] == 2)
        self.assign_annual(group)
        result = self.availability(available=False, reason='请假')
        self.assertEqual(result.status_code, 200, result.json)
        current = self.current()
        self.assertFalse(any(g['leader_id'] == 2 for g in current['groups']))
        video = {p['id'] for g in current['groups'] if g['mode'] == 'online' for p in g['members']}
        self.assertTrue({p['id'] for p in group['members']} - {2} <= video)
        self.cur.execute('SELECT inspector_ids FROM inspection_schedule_cells WHERE station_id=1')
        rows = self.cur.fetchall()
        self.assertEqual(len(rows), 8)
        self.assertTrue(all(not r['inspector_ids'] for r in rows))
        self.assertEqual(self.active_tasks(2), [])

    def test_only_own_post_dispatch_video_evidence_locks_before_1700(self):
        self.confirm()
        person = self.video_dispatch()
        # Neither another inspector at this station nor this inspector elsewhere locks them.
        self.record(station=1, table=7, inspector=person['id'], day='2026-10-19')
        self.record(station=2, table=7, inspector=1, day='2026-10-19')
        current = self.current()
        member = next(p for g in current['groups'] for p in g['members'] if p['id'] == person['id'])
        self.assertFalse(member['dispatch_locked'])
        rid = self.record(station=2, table=7, inspector=person['id'], day='2026-10-19')
        current = self.current()
        member = next(p for g in current['groups'] for p in g['members'] if p['id'] == person['id'])
        self.assertTrue(member['dispatch_locked'])
        self.assertEqual(self.adopt(current, [dict(person_id=person['id'], leader_id=2)]).status_code, 409)
        self.assertEqual(self.availability(name=person['display_name'], available=False).status_code, 409)
        detail = self.client.get('/api/staff-availability/detail', query_string=dict(person_name=person['display_name'], day='2026-10-19')).json
        self.assertTrue(detail['cell']['read_only'])
        self.assertFalse(detail['cell']['has_actual'], '17:00 display delay is not a write-lock delay')
        self.cur.execute('SELECT id FROM inspections WHERE id=%s', (rid,))
        self.assertIsNotNone(self.cur.fetchone())

    def test_new_issue_on_old_video_record_locks_but_unrelated_released_actuals_do_not(self):
        self.confirm()
        person = self.video_dispatch()
        rid = self.record(station=2, table=7, inspector=person['id'], day='2026-10-01')
        self.cur.execute("UPDATE inspections SET created_at=(SELECT MIN(updated_at)-INTERVAL '1 hour' FROM inspection_schedule_cells) WHERE id=%s", (rid,))
        self.admin.commit()
        self.record(station=1,table=7,inspector=person['id'],day='2026-10-19')
        with patch('schedule_common.shanghai_now', return_value=datetime(2026,10,19,18,tzinfo=ZoneInfo('Asia/Shanghai'))):
            detail = self.client.get('/api/staff-availability/detail', query_string=dict(person_name=person['display_name'], day='2026-10-19')).json
            self.assertTrue(detail['cell']['has_actual'])
            self.assertFalse(detail['cell']['read_only'])
        self.cur.execute('INSERT INTO issues(inspection_id,inspector_id) VALUES(%s,%s)', (rid,person['id']))
        self.admin.commit()
        self.assertEqual(self.availability(name=person['display_name'], available=False).status_code, 409)

    def test_failure_after_video_retirement_rolls_back_cells_tasks_groups_and_events(self):
        self.dispatched()
        person = self.video_dispatch()
        before = self.current()
        tables = ['inspection_schedule_cells', 'inspection_schedule_tasks', 'inspection_schedule_events', 'inspection_schedule_shelf', 'staff_daily_team_events']
        snapshots = {}
        for table in tables:
            self.cur.execute(f'SELECT * FROM {table} ORDER BY 1,2,3')
            snapshots[table] = [dict(r) for r in self.cur.fetchall()]
        self.cur.execute('ALTER TABLE staff_availability_events ADD CHECK(false) NOT VALID')
        self.admin.commit()
        with self.assertLogs(level='ERROR'):
            result = self.availability(name=person['display_name'], available=False)
        self.assertEqual(result.status_code, 500, result.json)
        self.assertEqual(self.current()['revision'], before['revision'])
        for table in tables:
            self.cur.execute(f'SELECT * FROM {table} ORDER BY 1,2,3')
            self.assertEqual([dict(r) for r in self.cur.fetchall()], snapshots[table], table)

    def test_record_commit_racing_busy_change_is_checked_before_any_cancellation(self):
        self.confirm()
        person = self.video_dispatch()
        writer = self.connect()
        try:
            with writer.cursor() as cur:
                cur.execute("INSERT INTO inspections(station_id,inspection_table_id,inspector_id,inspection_date) VALUES(2,7,%s,'2026-10-19')", (person['id'],))
            with ThreadPoolExecutor(max_workers=1) as pool:
                job = pool.submit(self.availability, name=person['display_name'], available=False)
                sleep(.15)
                self.assertFalse(job.done(), 'busy change must wait at the record-table boundary')
                writer.commit()
                self.assertEqual(job.result().status_code, 409)
            self.assertEqual(len(self.active_tasks(person['id'])), 3)
        finally:
            writer.close()
