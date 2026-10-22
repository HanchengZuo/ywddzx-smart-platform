"""Station-based history uses isolated PostgreSQL schemas, never real business data."""
import json
import os
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch
from flask import Flask
from staff_availability import register_staff_availability
from tests import test_staff_scheduling as staff_tests


class DetailAuthenticationTests(unittest.TestCase):
    def test_anonymous_does_not_connect(self):
        app = Flask(__name__); connect = MagicMock()
        register_staff_availability(app,connect=connect,has_permission=lambda *_:True)
        self.assertEqual(app.test_client().get('/api/staff-availability/detail').status_code,401)
        connect.assert_not_called()


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST')=='1','isolated database opt-in')
class HistoryDatabaseTests(unittest.TestCase):
    setUp = staff_tests.StaffDatabaseTests.setUp
    setUp_base = staff_tests.StaffDatabaseTests.setUp_base
    tearDown = staff_tests.StaffDatabaseTests.tearDown
    connect = staff_tests.StaffDatabaseTests.connect
    save = staff_tests.StaffDatabaseTests.save
    availability = staff_tests.StaffDatabaseTests.availability
    record = staff_tests.StaffDatabaseTests.record

    def clock(self,day):
        for module in ('schedule_common','staff_availability','inspection_schedule_tasks','inspection_schedule'):
            clock = patch(module+'.today',return_value=date.fromisoformat(day));clock.start();self.addCleanup(clock.stop)

    def detail(self,name='步雪琼',day='2026-10-20'):
        response=self.client.get('/api/staff-availability/detail',query_string=dict(person_name=name,day=day,user_id=1))
        self.assertEqual(response.status_code,200,response.json)
        return response.json

    def cell(self,name='步雪琼',day='2026-10-20'):
        response=self.client.get('/api/staff-availability',query_string=dict(week=day))
        self.assertEqual(response.status_code,200,response.json)
        return next(p for p in response.json['people'] if p['display_name']==name)['cells'][day]

    def test_field_progress_follows_assigned_station_tables_not_the_person_or_audit(self):
        self.save();self.save(station_id=2)
        self.clock('2026-10-21')
        # Historical field inbox tasks preserve the original obligations and do not imply completion.
        self.client.get('/api/my-schedule-tasks')
        before=self.cell();self.assertEqual(before['dispatch']['total'],12)
        self.assertEqual(before['dispatch']['completed'],0)
        for table in range(1,7):self.record(station=1,table=table,inspector=3,day='2026-10-20')
        self.record(station=3,table=7,inspector=2,day='2026-10-20') # unrelated personal work
        self.cur.execute('DELETE FROM staff_daily_teams');self.admin.commit()
        cell=self.cell()
        self.assertEqual((cell['dispatch']['completed'],cell['dispatch']['total']),(6,12))
        self.assertEqual((cell['dispatch']['station_completed'],cell['dispatch']['station_total']),(1,2))
        self.assertEqual(cell['actual_modes'],[dict(mode='offline',count=6),dict(mode='online',count=1)])
        self.assertEqual(cell['field_group_names'],['外勤步雪琼组'])
        self.assertTrue(cell['read_only'])
        detail=self.detail()
        self.assertEqual(len(detail['cell']['tasks']),12)
        completed=[t for t in detail['cell']['tasks'] if t['record_count']]
        self.assertEqual(len(completed),6)
        self.assertTrue(all(t['records'][0]['inspector_name']=='孔德辰' for t in completed))
        self.assertTrue(all(t['plan_team']['name']=='外勤步雪琼组' for t in completed))
        self.assertEqual(self.availability(day='2026-10-20',history_status='online').status_code,409)
        self.cur.execute("SELECT COUNT(*) AS n FROM staff_availability_events WHERE day='2026-10-20'")
        self.assertEqual(self.cur.fetchone()['n'],0)

    def test_video_catchup_and_record_deletion_change_progress_without_losing_original(self):
        self.cur.execute('DELETE FROM staff_daily_teams');self.admin.commit()
        query=dict(mode='online',year=2026,month=10,inspector_ids=[2],scheduled_date='2026-10-20',
            cells=[dict(station_id=1,column_key=k,revision=0) for k in ('safety','measurement','service')])
        result=self.client.put('/api/inspection-schedule',json=query)
        self.assertEqual(result.status_code,200,result.json)
        self.clock('2026-10-21')
        self.record(table=8,day='2026-10-19',inspector=3) # before dispatch, not creditable
        self.record(table=9,day='2026-10-22',inspector=3) # future evidence, not creditable
        record=self.record(table=7,day='2026-10-21',inspector=3)
        detail=self.detail()
        self.assertEqual(detail['cell']['dispatch']['completed'],1)
        original=[(t['id'],t['assigned_at'],t['team_ids']) for t in detail['cell']['tasks']]
        self.cur.execute('DELETE FROM inspections WHERE id=%s',(record,));self.admin.commit()
        detail=self.detail()
        self.assertEqual(detail['cell']['dispatch']['completed'],0)
        self.assertEqual([(t['id'],t['assigned_at'],t['team_ids']) for t in detail['cell']['tasks']],original)
        self.assertTrue(detail['cell']['read_only'],'historical dispatch remains immutable even without records')

    def test_busy_and_unassigned_free_remain_the_original_state_next_day(self):
        self.availability(available=False,reason='培训')
        self.availability(name='孔德辰')
        self.clock('2026-10-20')
        busy=self.cell(day='2026-10-19')
        self.assertIs(busy['available'],False);self.assertEqual(busy['reason'],'培训')
        self.assertTrue(busy['read_only'])
        self.assertEqual(self.availability(day='2026-10-19',history_status='auto').status_code,409)
        free=self.cell(name='孔德辰',day='2026-10-19')
        self.assertIs(free['available'],True);self.assertFalse(free['dispatch'])
        self.record(day='2026-10-19',inspector=2)
        self.assertEqual(self.detail(day='2026-10-19')['cell']['reason'],'培训')

    def test_actual_record_arriving_after_the_board_prevents_a_stale_edit(self):
        self.clock('2026-10-20')
        before=self.cell();self.assertFalse(before['read_only'])
        record=self.record(day='2026-10-20',inspector=2)
        self.assertEqual(self.availability(day='2026-10-20',available=True).status_code,409)
        cell=self.detail()['cell'];self.assertTrue(cell['read_only']);self.assertTrue(cell['has_actual'])
        detail=self.detail();self.assertEqual(detail['records'][0]['id'],record)

    def test_reassignment_preserves_every_original_task_and_group_snapshot(self):
        self.clock('2026-10-20')
        self.cur.execute("INSERT INTO users VALUES(10,'student','陈中磊','supervisor','active')")
        self.cur.execute("INSERT INTO staff_availability(person_name,day,available,revision,updated_by) VALUES('陈中磊','2026-10-20',true,1,1)")
        groups=[dict(id=i,display_name=n,position=p,mode='offline',leader_id=l,group_name='外勤'+('步雪琼' if l==2 else '孔德辰')+'组')
            for i,n,p,l in [(2,'步雪琼','管理人员',2),(3,'孔德辰','管理人员',3),(10,'陈中磊','大学生',2)]]
        self.cur.execute('UPDATE staff_daily_teams SET assignments=%s',(json.dumps(groups),));self.admin.commit()
        self.assertEqual(self.save(inspector_ids=[2,10]).status_code,200)
        original=self.detail()['cell']['tasks'];original_ids=[t['id'] for t in original]
        groups[-1].update(leader_id=3,group_name='外勤孔德辰组')
        self.cur.execute('UPDATE staff_daily_teams SET assignments=%s,revision=revision+1',(json.dumps(groups),));self.admin.commit()
        self.assertEqual(self.save(inspector_ids=[2],revision=1).status_code,200)
        detail=self.detail()['cell']
        retired=[t for t in detail['tasks'] if t['id'] in original_ids]
        self.assertTrue(all(t['status']=='cancelled' and t['team_ids']==[2,10] for t in retired))
        self.assertTrue(all([p['id'] for p in t['plan_team']['members']]==[2,10] for t in retired))
        self.assertEqual(detail['dispatch']['total'],6)
        self.assertEqual(detail['dispatch']['cancelled'],6)
        self.record(day='2026-10-20',inspector=3)
        self.assertEqual(self.detail()['cell']['dispatch']['completed'],1)
        self.assertTrue(all(t['record_count']==0 for t in self.detail()['cell']['tasks'] if t['status']=='cancelled'))

    def test_migration_recovers_evidence_idempotently_without_changing_records(self):
        self.save();record=self.record(inspector=3)
        self.cur.execute("UPDATE inspection_schedule_tasks SET plan_team=NULL,dispatch_event_id=NULL,team_ids='[999]'")
        sql=(Path(__file__).resolve().parents[1]/'db/init/545_staff_dispatch_history.sql').read_text()
        self.cur.execute(sql);self.cur.execute(sql);self.admin.commit()
        task=self.detail()['cell']['tasks'][0]
        self.assertEqual(task['team_ids'],[2]);self.assertEqual(task['plan_team']['leader_id'],2)
        self.assertIsNotNone(task['dispatch_event_id'])
        self.cur.execute('SELECT id FROM inspections');self.assertEqual(self.cur.fetchone()['id'],record)

    def test_all_field_members_share_station_evidence_even_after_group_snapshot_is_replaced(self):
        self.cur.execute("INSERT INTO users VALUES(10,'student','陈中磊','supervisor','active')")
        self.cur.execute("INSERT INTO staff_availability(person_name,day,available,revision,updated_by) VALUES('陈中磊','2026-10-20',true,1,1)")
        members=[dict(id=uid,display_name=name,position=position,mode='offline',leader_id=2,group_name='外勤步雪琼组',has_driving_permit=uid==2)
            for uid,name,position in [(2,'步雪琼','管理人员'),(10,'陈中磊','大学生')]]
        self.cur.execute('UPDATE staff_daily_teams SET assignments=%s',(json.dumps(members),));self.admin.commit()
        self.assertEqual(self.save(inspector_ids=[2,10]).status_code,200)
        self.clock('2026-10-21')
        self.record(day='2026-10-21',inspector=4)
        self.cur.execute("UPDATE staff_daily_teams SET assignments='[]'");self.admin.commit()
        for name in ('步雪琼','陈中磊'):
            cell=self.detail(name=name)['cell']
            self.assertEqual((cell['dispatch']['completed'],cell['dispatch']['total']),(1,6))
            self.assertEqual(cell['field_group_names'],['外勤步雪琼组'])
            self.assertTrue(cell['read_only'])
            self.assertEqual(cell['tasks'][0]['plan_team']['members'],members)

    def test_personal_issue_participation_also_makes_actual_read_only(self):
        self.clock('2026-10-20')
        record=self.record(day='2026-10-20',inspector=4,table=7)
        self.cur.execute('INSERT INTO issues(inspection_id,inspector_id) VALUES(%s,2)',(record,));self.admin.commit()
        detail=self.detail()
        self.assertTrue(detail['cell']['read_only'])
        self.assertEqual(detail['records'][0]['id'],record)
        self.assertEqual(self.availability(day='2026-10-20',available=False).status_code,409)

    def test_detail_permission_validation_and_failure_are_safe(self):
        self.permissions.discard('view_staff_availability')
        self.assertEqual(self.client.get('/api/staff-availability/detail').status_code,403)
        self.permissions.add('view_staff_availability');self.permissions.discard('edit_staff_availability')
        self.assertFalse(self.detail()['can_edit'])
        for params in [dict(person_name='不在名单',day='2026-10-20'),dict(person_name='步雪琼',day='bad')]:
            self.assertEqual(self.client.get('/api/staff-availability/detail',query_string=params).status_code,400)
        self.cur.execute('ALTER TABLE inspection_schedule_tasks RENAME TO missing_test_tasks');self.admin.commit()
        with self.assertLogs(level='ERROR'):
            response=self.client.get('/api/staff-availability/detail?person_name=步雪琼&day=2026-10-20')
        self.assertEqual(response.status_code,500)
        self.assertNotIn('missing_test_tasks',response.get_data(as_text=True))
