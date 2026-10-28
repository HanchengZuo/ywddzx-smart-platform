"""17:00 personnel actuals release; real records, coverage and task completion stay live."""
import json
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from datetime import date, datetime, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo
from staff_actuals import actuals_window, merge_actual_modes
from staff_schedule_history import summarize_tasks
from staff_daily_team_http import register_staff_daily_teams
from tests import test_staff_scheduling as staff_tests

SHANGHAI=ZoneInfo('Asia/Shanghai')


class ActualsWindowTests(unittest.TestCase):
    def test_exact_1700_boundary_and_shanghai_timezone(self):
        for now,released in [(datetime(2026,10,19,16,59,59,tzinfo=SHANGHAI),False),
                             (datetime(2026,10,19,17,tzinfo=SHANGHAI),True),
                             (datetime(2026,10,19,9,tzinfo=timezone.utc),True)]:
            with self.subTest(now=now),patch('schedule_common.shanghai_now',return_value=now):
                window=actuals_window()
                self.assertEqual(window.today,date(2026,10,19))
                self.assertEqual(window.as_of,date(2026,10,19 if released else 18))
                self.assertEqual(window.metadata()['actuals_pending'],not released)
                self.assertEqual(window.metadata()['actuals_release_at'],'2026-10-19T17:00:00+08:00')

    def test_month_and_year_rollover_do_not_release_next_day_early(self):
        for now,expected in [(datetime(2027,1,1,0,0,tzinfo=SHANGHAI),date(2026,12,31)),
                             (datetime(2026,11,1,16,tzinfo=SHANGHAI),date(2026,10,31))]:
            with patch('schedule_common.shanghai_now',return_value=now):
                self.assertEqual(actuals_window().as_of,expected)

    def test_personal_and_delegated_modes_union_record_ids_without_duplicates(self):
        work=dict(_actual_record_ids={'offline':[1,2],'online':[8]},
                  actual_modes=[dict(mode='offline',count=2),dict(mode='online',count=1)])
        personal=[dict(mode='offline',count=2,record_ids=[2,3]),dict(mode='online',count=2,record_ids=[8,9])]
        self.assertEqual(merge_actual_modes(personal,work),[dict(mode='offline',count=3),dict(mode='online',count=2)])

    def test_task_summary_deduplicates_evidence_but_retains_every_obligation(self):
        tasks=[dict(station_id=1,table_id=1,column_key=key,station_name='测试站',mode='offline',
                    status='pending',record_count=1,record_ids=[11],plan_team=None) for key in ('a','b')]
        summary=summarize_tasks(tasks)
        self.assertEqual((summary['total'],summary['completed']),(2,2))
        self.assertEqual(summary['actual_modes'],[dict(mode='offline',count=1)])


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST')=='1','isolated database opt-in')
class ActualsDatabaseTests(unittest.TestCase):
    setUp=staff_tests.StaffDatabaseTests.setUp
    setUp_base=staff_tests.StaffDatabaseTests.setUp_base
    connect=staff_tests.StaffDatabaseTests.connect
    tearDown=staff_tests.StaffDatabaseTests.tearDown
    availability=staff_tests.StaffDatabaseTests.availability
    record=staff_tests.StaffDatabaseTests.record
    save=staff_tests.StaffDatabaseTests.save
    board=staff_tests.StaffDatabaseTests.board

    def at(self,hour,minute=0,second=0,day=19):
        return patch('schedule_common.shanghai_now',return_value=datetime(2026,10,day,hour,minute,second,tzinfo=SHANGHAI))

    def detail(self,day='2026-10-19',name='步雪琼'):
        result=self.client.get('/api/staff-availability/detail',query_string=dict(day=day,person_name=name))
        self.assertEqual(result.status_code,200,result.json)
        return result.json

    def people(self):
        result=self.client.get('/api/inspection-schedule/available-people?day=2026-10-19')
        self.assertEqual(result.status_code,200,result.json)
        return {p['display_name']:p for p in result.json['people']}

    def field_teams(self):
        assignments=[dict(id=uid,display_name=name,position='管理人员',mode='offline',leader_id=uid,group_name=f'外勤{name}组')
                     for uid,name in [(2,'步雪琼'),(3,'孔德辰')]]
        self.cur.execute('INSERT INTO staff_daily_teams(day,assignments,revision,updated_by) VALUES(%s,%s,1,2)',
                         ('2026-10-19',json.dumps(assignments)))
        self.admin.commit()

    def test_morning_mixed_records_do_not_lock_availability_but_release_at_1700(self):
        offline=self.record(day='2026-10-19',table=1,inspector=2)
        online=self.record(day='2026-10-19',table=7,inspector=2)
        with self.at(8):
            before=self.detail()
            self.assertTrue(before['actuals_pending'])
            self.assertFalse(before['cell']['read_only']);self.assertFalse(before['cell']['has_actual'])
            self.assertEqual(before['cell']['actual_modes'],[]);self.assertEqual(before['records'],[])
            self.assertEqual(self.people()['步雪琼']['actual_modes'],[])
            self.assertEqual(self.availability(available=False,reason='培训').status_code,200)
            self.assertEqual(self.availability(available=True).status_code,200)
            board=self.client.get('/api/staff-availability?week=2026-10-19').json
            self.assertEqual((board['today_summary']['offline'],board['today_summary']['online']),(0,0))
        with self.at(16,59,59): self.assertFalse(self.detail()['cell']['read_only'])
        with self.at(17):
            after=self.detail()
            self.assertFalse(after['actuals_pending'])
            self.assertTrue(after['cell']['read_only']);self.assertTrue(after['cell']['has_actual'])
            self.assertEqual(after['cell']['actual_modes'],[dict(mode='offline',count=1),dict(mode='online',count=1)])
            self.assertEqual({r['id'] for r in after['records']},{offline,online})
            self.assertEqual(self.availability(available=False).status_code,409)
            board=self.client.get('/api/staff-availability?week=2026-10-19').json
            self.assertEqual((board['today_summary']['offline'],board['today_summary']['online']),(1,1))
        self.cur.execute('SELECT COUNT(*) AS n FROM inspections');self.assertEqual(self.cur.fetchone()['n'],2)

    def test_morning_person_can_be_grouped_and_dispatched_despite_opposite_mode_record(self):
        self.record(day='2026-10-19',table=7,inspector=2)
        register_staff_daily_teams(self.client.application,connect=self.connect,has_permission=lambda _,actor,key:key in self.permissions)
        body=dict(day='2026-10-19',revision=0,manager_modes={'2':'offline','3':'online'})
        with self.at(9):
            preview=self.client.post('/api/staff-availability/today-inspection',json=dict(action='preview',**body))
            self.assertEqual(preview.status_code,200,preview.json)
            result=self.client.post('/api/staff-availability/today-inspection',json=dict(action='confirm',**body,
                token=preview.json['token'],seed=preview.json['seed']))
            self.assertEqual(result.status_code,200,result.json)
            auto=self.client.post('/api/inspection-schedule/auto',json=dict(action='preview',day='2026-10-19')).json
            self.assertTrue(any(g['mode']=='offline' and g['person']['id']==2 for g in auto['groups']))
            result=self.client.post('/api/inspection-schedule/auto',json=dict(action='confirm',day='2026-10-19',token=auto['token']))
            self.assertEqual(result.status_code,200,result.json)
            self.assertEqual(self.detail()['cell']['daily_assignment']['group_name'],'外勤步雪琼组')

    def test_morning_manual_cross_mode_dispatch_ignores_early_actual_not_existing_plan(self):
        self.field_teams();self.record(day='2026-10-19',table=7,inspector=2)
        with self.at(10):
            result=self.save(station_id=2,scheduled_date='2026-10-19')
            self.assertEqual(result.status_code,200,result.json)
            self.assertEqual(self.availability(available=False).status_code,200,'unstarted field leader may leave; old station intent is retired')
            self.assertEqual(self.detail()['cell']['actual_modes'],[])

    def test_release_unions_task_evidence_and_unrelated_personal_work_and_deduplicates(self):
        self.field_teams()
        with self.at(9): self.assertEqual(self.save(scheduled_date='2026-10-19').status_code,200)
        a=self.record(day='2026-10-19',table=1,inspector=2)
        b=self.record(day='2026-10-19',table=2,inspector=3)
        c=self.record(day='2026-10-19',table=7,station=2,inspector=2)
        self.cur.execute('INSERT INTO issues(inspection_id,inspector_id) VALUES(%s,2)',(a,));self.admin.commit()
        with self.at(16):
            cell=self.detail()['cell']
            self.assertFalse(cell['has_actual']);self.assertTrue(cell['read_only'], 'matching post-dispatch work locks before the display cutoff')
            self.assertEqual(cell['dispatch']['completed'],0)
            self.assertTrue(all(t['record_count']==0 and not t['records'] for t in cell['tasks']))
            self.assertEqual(self.board()['rows'][0]['cells']['odor']['status'],'completed','station cells stay real-time')
        with self.at(17):
            detail=self.detail();cell=detail['cell']
            self.assertEqual(cell['actual_modes'],[dict(mode='offline',count=2),dict(mode='online',count=1)])
            self.assertEqual(cell['dispatch']['completed'],2)
            self.assertEqual(cell['field_group_names'],['外勤步雪琼组'])
            self.assertEqual(cell['daily_assignment']['group_name'],'外勤步雪琼组')
            self.assertTrue(cell['read_only'])
            self.assertNotIn('_actual_record_ids',cell['dispatch'])
            self.assertEqual({r['id'] for r in detail['records']},{a,c})
            proof={r['id'] for t in cell['tasks'] for r in t['records']};self.assertEqual(proof,{a,b})
        self.cur.execute('DELETE FROM inspections WHERE id=%s',(c,));self.admin.commit()
        with self.at(18):self.assertEqual(self.detail()['cell']['actual_modes'],[dict(mode='offline',count=2)])

    def test_prior_dispatch_progress_stays_live_and_historical_actuals_are_always_read_only(self):
        self.save()
        # On the 21st before 17:00, a catch-up record for the 20th remains visible in that historical cell.
        for module in ('staff_availability','schedule_common','inspection_schedule_tasks','inspection_schedule'):
            clock=patch(module+'.today',return_value=date(2026,10,21));clock.start();self.addCleanup(clock.stop)
        self.record(day='2026-10-21',table=1,inspector=3)
        self.record(day='2026-10-20',table=7,inspector=2)
        with self.at(8,day=21):
            cell=self.detail(day='2026-10-20')['cell']
            self.assertFalse(cell['actuals_pending']);self.assertTrue(cell['read_only'])
            self.assertEqual(cell['dispatch']['completed'],1)
            self.assertEqual(cell['actual_modes'],[dict(mode='offline',count=1),dict(mode='online',count=1)])

    def test_pre1700_preview_becomes_stale_after_release_and_cannot_override_actuals(self):
        self.field_teams();self.record(day='2026-10-19',table=7,inspector=2)
        with self.at(16):
            preview=self.client.post('/api/inspection-schedule/auto',json=dict(action='preview',day='2026-10-19')).json
            old=self.detail()['cell']['revision']
        with self.at(17):
            result=self.client.post('/api/inspection-schedule/auto',json=dict(action='confirm',day='2026-10-19',token=preview['token']))
            self.assertEqual(result.status_code,409,result.json)
            result=self.client.put('/api/staff-availability',json=dict(available=False,cells=[dict(person_name='步雪琼',day='2026-10-19',revision=old)]))
            self.assertEqual(result.status_code,200,result.json)
        self.cur.execute('SELECT 1 FROM inspection_schedule_cells');self.assertIsNone(self.cur.fetchone())

    def test_no_actual_after_release_remains_editable_and_preconfigured_busy_is_not_erased(self):
        with self.at(17):
            self.assertFalse(self.detail()['cell']['read_only'])
            self.assertEqual(self.availability(available=False,reason='休假').status_code,200)
            cell=self.detail()['cell'];self.assertFalse(cell['available']);self.assertEqual(cell['reason'],'休假')

    def test_request_waiting_for_dispatch_lock_rechecks_release_before_writing(self):
        from schedule_common import lock_schedule
        self.record(day='2026-10-19',table=7,inspector=2)
        with self.at(16,59,59) as clock:
            revision=self.detail()['cell']['revision']
            blocker=self.connect();started=Event()
            def notify_lock(cur):
                started.set();lock_schedule(cur)
            def save():
                return self.client.application.test_client().put('/api/staff-availability',json=dict(available=False,
                    cells=[dict(person_name='步雪琼',day='2026-10-19',revision=revision)]))
            try:
                with blocker.cursor() as cur:cur.execute('SELECT pg_advisory_xact_lock(9801,1)')
                with patch('staff_availability.lock_schedule',side_effect=notify_lock),ThreadPoolExecutor(max_workers=1) as pool:
                    future=pool.submit(save)
                    self.assertTrue(started.wait(2))
                    clock.return_value=datetime(2026,10,19,17,tzinfo=SHANGHAI)
                    blocker.commit()
                    result=future.result(timeout=5)
                    self.assertEqual(result.status_code,409,result.json)
            finally:blocker.close()
        self.cur.execute("SELECT available FROM staff_availability WHERE person_name='步雪琼' AND day='2026-10-19'")
        self.assertTrue(self.cur.fetchone()['available'])

    def test_crossing_cutoff_during_a_save_rolls_back_the_whole_edit_and_audit(self):
        from staff_availability import single_staff_cell
        self.record(day='2026-10-19',table=7,inspector=2)
        with self.at(16,59,59) as clock:
            before=self.detail()['cell']
            def cross_after_read(*args,**kwargs):
                value=single_staff_cell(*args,**kwargs)
                clock.return_value=datetime(2026,10,19,17,tzinfo=SHANGHAI)
                return value
            with patch('staff_availability.single_staff_cell',side_effect=cross_after_read):
                result=self.availability(available=False,reason='出差')
            self.assertEqual(result.status_code,409,result.json)
        self.cur.execute("SELECT available,revision FROM staff_availability WHERE person_name='步雪琼' AND day='2026-10-19'")
        self.assertEqual(dict(self.cur.fetchone()),dict(available=True,revision=before['revision']))
        self.cur.execute("SELECT 1 FROM staff_availability_events WHERE actor_id=2 AND day='2026-10-19'")
        self.assertIsNone(self.cur.fetchone())

    def test_read_permission_still_required_and_audit_failure_rolls_back_morning_edit(self):
        self.record(day='2026-10-19',table=7,inspector=2)
        with self.at(9):
            self.detail()
            self.cur.execute('ALTER TABLE staff_availability_events ADD CHECK(false) NOT VALID');self.admin.commit()
            with self.assertLogs(level='ERROR'): result=self.availability(available=False,reason='培训')
            self.assertEqual(result.status_code,500)
            self.assertTrue(self.detail()['cell']['available'])
            self.permissions.discard('view_staff_availability')
            self.assertEqual(self.client.get('/api/staff-availability/detail?person_name=步雪琼&day=2026-10-19').status_code,403)
