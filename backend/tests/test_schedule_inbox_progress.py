"""v10.7 inbox coverage/history, with isolated schemas and no production writes."""
import os
import unittest
from datetime import date
from unittest.mock import patch
from tests import test_staff_scheduling as staff_tests
from inspection_schedule_tasks import task_count


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST')=='1','isolated database opt-in')
class InboxDatabaseTests(unittest.TestCase):
    setUp=staff_tests.StaffDatabaseTests.setUp
    setUp_base=staff_tests.StaffDatabaseTests.setUp_base
    connect=staff_tests.StaffDatabaseTests.connect
    tearDown=staff_tests.StaffDatabaseTests.tearDown
    availability=staff_tests.StaffDatabaseTests.availability
    save=staff_tests.StaffDatabaseTests.save
    board=staff_tests.StaffDatabaseTests.board
    record=staff_tests.StaffDatabaseTests.record

    def clock(self,day):
        clock=patch('inspection_schedule_tasks.today',return_value=date.fromisoformat(day))
        clock.start();self.addCleanup(clock.stop)

    def inbox(self,**query):
        response=self.client.get('/api/my-schedule-tasks',query_string=query)
        self.assertEqual(response.status_code,200,response.json)
        return response.json

    def video(self):
        self.cur.execute('DELETE FROM staff_daily_teams');self.admin.commit()
        response=self.client.put('/api/inspection-schedule',json=dict(mode='online',year=2026,month=10,
            inspector_ids=[2],scheduled_date='2026-10-20',cells=[dict(station_id=1,column_key=k,revision=0)
            for k in ('safety','measurement','service')]))
        self.assertEqual(response.status_code,200,response.json)

    def test_today_partial_field_matches_board_and_carries_all_siblings_into_history(self):
        self.save();self.clock('2026-10-20')
        rid=self.record(station=1,table=1,inspector=3,day='2026-10-01')
        data=self.inbox(bucket='today_offline',user_id=3)
        self.assertEqual((data['count'],len(data['tasks'])),(5,6))
        completed=[t for t in data['tasks'] if t['status']=='completed']
        self.assertEqual(completed[0]['completion_inspection_id'],rid)
        board=self.board()['rows'][0]
        self.assertEqual({t['column_key']:t['status'] for t in data['tasks']},
                         {k:'completed' if c['record_count'] else 'pending' for k,c in board['cells'].items()})
        self.clock('2026-10-21')
        history=self.inbox(bucket='history_offline')
        self.assertEqual(len(history['tasks']),6)
        self.assertEqual(history['buckets']['history_offline'],dict(total=6,pending=5,completed=1,stations=1))
        self.assertEqual(self.inbox(bucket='today_offline')['tasks'],[])
        self.assertEqual(history['agenda']['offline'],dict(count=5,overdue=5))

    def test_completed_today_is_visible_then_disappears_from_history_and_reopens_on_delete(self):
        self.save();self.clock('2026-10-20')
        records=[self.record(station=1,table=table,inspector=3,day='2026-10-20') for table in range(1,7)]
        data=self.inbox()
        self.assertEqual((data['count'],len(data['tasks'])),(0,6))
        self.assertTrue(all(t['status']=='completed' for t in data['tasks']))
        self.clock('2026-10-21')
        self.assertEqual(self.inbox()['tasks'],[])
        self.cur.execute('DELETE FROM inspections WHERE id=%s',(records[0],));self.admin.commit()
        history=self.inbox(bucket='history_offline')
        self.assertEqual((history['count'],len(history['tasks'])),(1,6))
        self.assertEqual(history['buckets']['history_offline']['completed'],5)

    def test_video_history_keeps_period_boundary_and_deleted_evidence_reopens(self):
        self.video();self.clock('2026-10-21')
        record=self.record(table=7,inspector=3,day='2026-10-01')
        self.record(table=8,inspector=3,day='2026-11-01')
        self.record(table=9,inspector=3,day='2026-09-30')
        data=self.inbox(bucket='history_online')
        self.assertEqual((data['count'],len(data['tasks'])),(2,3))
        self.assertEqual(data['buckets']['history_online']['completed'],1)
        self.assertTrue(all(t['coverage_to']=='2026-10-31' for t in data['tasks']))
        self.cur.execute('DELETE FROM inspections WHERE id=%s',(record,));self.admin.commit()
        self.assertEqual(self.inbox()['count'],3)

    def test_completion_record_id_and_date_stay_paired_when_latest_record_changes(self):
        self.save();self.clock('2026-10-20')
        first=self.record(table=1,day='2026-10-01')
        last=self.record(table=1,day='2026-10-02')
        task=next(t for t in self.inbox()['tasks'] if t['column_key']=='odor')
        self.assertEqual((task['record_count'],task['completion_inspection_id'],task['last_inspection_date']),(2,last,'2026-10-02'))
        self.cur.execute('DELETE FROM inspections WHERE id=%s',(last,));self.admin.commit()
        data=self.inbox();task=next(t for t in data['tasks'] if t['column_key']=='odor')
        self.assertEqual((data['count'],task['completion_inspection_id'],task['last_inspection_date']),(5,first,'2026-10-01'))

    def test_annual_tasks_use_the_year_while_quarterly_siblings_use_the_quarter(self):
        response=self.client.get('/api/inspection-schedule?mode=annual&year=2026')
        self.assertEqual(response.status_code,200,response.json)
        board=response.json;row=next(r for r in board['rows'] if r['station_id']==1)
        edits=[dict(station_id=1,column_key=k,revision=c['revision']) for k,c in row['cells'].items() if c['applicable']]
        saved=self.client.put('/api/inspection-schedule',json=dict(mode='annual',year=2026,
            inspector_ids=[2],scheduled_date='2026-10-20',cells=edits))
        self.assertEqual(saved.status_code,200,saved.json)
        site=next(c['table_id'] for c in board['columns'] if c['key']=='metering_site')
        self.record(table=site,day='2026-02-01',inspector=3)
        self.record(table=1,day='2026-09-30',inspector=3)
        self.clock('2026-10-21');data=self.inbox(bucket='history_offline')
        annual=next(t for t in data['tasks'] if t['column_key']=='metering_site')
        self.assertEqual((annual['status'],annual['coverage_to']),('completed','2026-12-31'))
        ordinary=next(t for t in data['tasks'] if t['column_key']=='odor')
        self.assertEqual((ordinary['status'],ordinary['coverage_from']),('pending','2026-10-01'))

    def test_legacy_expired_field_recovers_only_the_current_plan_not_reassigned_owners(self):
        self.save();self.clock('2026-10-21')
        self.cur.execute("UPDATE inspection_schedule_tasks SET status='expired',expired_at=CURRENT_TIMESTAMP");self.admin.commit()
        self.assertEqual(self.inbox()['count'],6)
        self.cur.execute("SELECT DISTINCT status FROM inspection_schedule_tasks")
        self.assertEqual([r['status'] for r in self.cur.fetchall()],['pending'])
        self.cur.execute("UPDATE inspection_schedule_tasks SET status='expired'");self.admin.commit()
        self.assertEqual(self.save(revision=1,inspector_ids=[3]).status_code,200)
        self.assertEqual(self.inbox()['count'],0)
        self.actor=dict(id=3,username='lead',real_name='孔德辰',role='supervisor_manager')
        self.assertEqual(self.inbox(user_id=2)['count'],6)

    def test_pagination_never_splits_station_tables_and_counts_are_global_for_the_user(self):
        self.save();self.save(station_id=2);self.clock('2026-10-20')
        first=self.inbox(page_size=1,page=1)
        second=self.inbox(page_size=1,page=2)
        self.assertEqual((first['count'],first['total_groups'],len(first['tasks'])),(12,2,6))
        self.assertEqual((second['count'],second['page'],len(second['tasks'])),(12,2,6))
        self.assertNotEqual(first['tasks'][0]['station_id'],second['tasks'][0]['station_id'])
        self.assertEqual(self.inbox(page_size=1,page=999)['page'],2)
        for query in ({'page':0},{'page_size':51},{'bucket':'somebody_else'}):
            self.assertEqual(self.client.get('/api/my-schedule-tasks',query_string=query).status_code,400)

    def test_lock_contention_uses_live_read_projection_without_blocking_or_cache_writes(self):
        self.save();self.clock('2026-10-20')
        self.record(table=1,inspector=3,day='2026-10-20')
        writer=self.connect();reader=self.connect()
        try:
            writer.cursor().execute('SELECT pg_advisory_xact_lock(9801,1)')
            cur=reader.cursor();cur.execute("SET LOCAL statement_timeout='1s'")
            self.assertEqual(task_count(cur,2),5)
            self.cur.execute("SELECT COUNT(*) AS n FROM inspection_schedule_tasks WHERE status='completed'")
            self.assertEqual(self.cur.fetchone()['n'],0)
        finally:writer.close();reader.close()

    def test_sync_failure_rolls_back_task_state_without_touching_actual_records(self):
        self.save();self.clock('2026-10-20')
        rid=self.record(table=1,day='2026-10-20')
        self.cur.execute("ALTER TABLE inspection_schedule_tasks ADD CHECK(status<>'completed') NOT VALID");self.admin.commit()
        with self.assertLogs(level='ERROR'):
            response=self.client.get('/api/my-schedule-tasks')
        self.assertEqual(response.status_code,500)
        self.cur.execute("SELECT COUNT(*) AS n FROM inspection_schedule_tasks WHERE status='pending'");self.assertEqual(self.cur.fetchone()['n'],6)
        self.cur.execute('SELECT id FROM inspections WHERE id=%s',(rid,));self.assertEqual(self.cur.fetchone()['id'],rid)

    def test_disabled_or_ambiguous_table_does_not_claim_matrix_completion(self):
        self.save();self.clock('2026-10-20');self.record(table=1,day='2026-10-20')
        self.cur.execute("UPDATE inspection_tables SET is_active=FALSE WHERE id=1");self.admin.commit()
        self.assertEqual(self.inbox()['count'],6)
        self.cur.execute("UPDATE inspection_tables SET is_active=TRUE WHERE id=1")
        self.cur.execute("INSERT INTO inspection_tables(table_name,checklist_mode) SELECT table_name,checklist_mode FROM inspection_tables WHERE id=1");self.admin.commit()
        self.assertEqual(self.inbox()['count'],6)
