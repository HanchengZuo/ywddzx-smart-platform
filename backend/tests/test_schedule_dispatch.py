"""v9.9 dispatch contracts, real PostgreSQL rollback/locks and network-free route tests."""
import json
import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from unittest.mock import patch

from tests import test_staff_daily_teams as team_tests
from tests import test_staff_scheduling as staff_tests
from inspection_schedule_catalog import COLUMNS
from schedule_routes import ORIGIN_POINT, coordinate, distance, field_routes, cluster_diameter


class RouteTests(unittest.TestCase):
    def test_coordinates_and_distance(self):
        self.assertEqual(ORIGIN_POINT,(121.53144968,31.22541333))
        for invalid in (None, [True, 31], [0,0], [float('nan'),31], [31,121], ['oops',31]):
            self.assertIsNone(coordinate(invalid))
        self.assertEqual(distance((121.5,31.2),(121.5,31.2)), 0)
        self.assertGreater(distance((121.5,31.2),(121.6,31.2)), 9)

    def test_compact_groups_have_quotas_no_duplicates_and_ignore_departure_point(self):
        origin=(121.5,31.2)
        stations=[dict(station_id=i,longitude=121.2+i*.002,latitude=31.2) for i in range(4)]
        stations += [dict(station_id=i+4,longitude=121.8+i*.002,latitude=31.2) for i in range(4)]
        result=field_routes(stations,2,3,origin)
        self.assertEqual([len(r) for r in result],[3,3])
        self.assertEqual(len({s['station_id'] for r in result for s in r}),6)
        self.assertTrue(all(len({s['station_id']<4 for s in r})==1 for r in result))
        self.assertTrue(all(cluster_diameter(group)<1 for group in result))
        self.assertEqual(result,field_routes(stations,2,3,(122.1,32)))
        self.assertEqual(result,field_routes(stations,2,3,origin))

    def test_empty_missing_coordinates_small_demand_and_runtime(self):
        self.assertEqual(field_routes([dict(station_id=1)],3,2,(121.5,31.2)),[])
        stations=[dict(station_id=i,longitude=121.2+i*.001,latitude=31.1+i*.002) for i in range(155)]
        started=time.monotonic(); routes=field_routes(stations,7,10,(121.5,31.2))
        self.assertEqual(sum(map(len,routes)),70)
        self.assertLess(time.monotonic()-started,3)


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST')=='1','isolated database opt-in')
class DispatchDatabaseTests(unittest.TestCase):
    setUp=staff_tests.StaffDatabaseTests.setUp
    setUp_base=staff_tests.StaffDatabaseTests.setUp_base
    connect=staff_tests.StaffDatabaseTests.connect
    tearDown=staff_tests.StaffDatabaseTests.tearDown
    availability=staff_tests.StaffDatabaseTests.availability
    board=staff_tests.StaffDatabaseTests.board
    save=staff_tests.StaffDatabaseTests.save
    record=staff_tests.StaffDatabaseTests.record

    def video(self, **extra):
        body=dict(mode='online',year=2026,month=10,station_id=1,column_key='safety',inspector_ids=[2],scheduled_date='2026-10-20',revision=0)
        body.update(extra)
        if 'cells' not in body:
            body['cells'] = [dict(station_id=body['station_id'],column_key=k,revision=body['revision']) for k,_,_ in COLUMNS['online']]
        return self.client.put('/api/inspection-schedule',json=body)

    def row_cells(self, sid, revision=0, skip=()):
        return [dict(station_id=sid,column_key=k,revision=revision) for k,_,_ in COLUMNS['offline'] if k not in skip]

    def test_video_one_person_even_in_bulk_and_signed_identity(self):
        self.cur.execute('DELETE FROM staff_daily_teams'); self.admin.commit()
        self.assertEqual(self.video(inspector_ids=[2,3]).status_code,400)
        self.assertEqual(self.video(inspector_ids=[True]).status_code,400)
        result=self.video(); self.assertEqual(result.status_code,200,result.json)
        self.assertEqual(self.video(revision=1,inspector_ids=[3]).status_code,200)
        self.cur.execute('SELECT actor_id FROM inspection_schedule_events')
        self.assertTrue(all(r['actor_id']==2 for r in self.cur.fetchall()))

    def test_field_cannot_split_rows_or_invent_teams_and_snapshot_survives_actual(self):
        body=dict(**self.query,station_id=1,column_key='odor',revision=0,inspector_ids=[2],scheduled_date='2026-10-20')
        self.assertEqual(self.client.put('/api/inspection-schedule',json=body).status_code,409)
        self.assertEqual(self.save(inspector_ids=[2,3]).status_code,400)
        self.assertEqual(self.save().status_code,200)
        self.record(inspector=3)
        cell=self.board()['rows'][0]['cells']['odor']
        self.assertEqual(cell['status'],'completed')
        self.assertEqual(cell['plan_team']['name'],'外勤步雪琼组')
        self.assertEqual([p['id'] for p in cell['assignees']],[2])
        self.assertEqual([p['id'] for p in cell['completed_inspectors']],[3])
        # Partial completion is immutable while the remaining five cells may move to another whole team.
        response=self.save(inspector_ids=[3],cells=self.row_cells(1,1,skip=('odor',)))
        self.assertEqual(response.status_code,200,response.json)
        cells=self.board()['rows'][0]['cells']
        self.assertEqual(cells['odor']['assignees'][0]['id'],2)
        self.assertEqual(cells['finance']['assignees'][0]['id'],3)

    def test_field_move_is_atomic_and_stale_or_audit_failure_preserves_both_rows(self):
        self.assertEqual(self.save().status_code,200)
        body=dict(**self.query,cells=self.row_cells(2),source=dict(cells=self.row_cells(1,1)),inspector_ids=[2],scheduled_date='2026-10-20')
        stale={**body,'source':dict(cells=self.row_cells(1,0))}
        self.assertEqual(self.client.put('/api/inspection-schedule',json=stale).status_code,409)
        self.cur.execute("ALTER TABLE inspection_schedule_events ADD CHECK(station_id<>2) NOT VALID"); self.admin.commit()
        with self.assertLogs(level='ERROR'):
            self.assertEqual(self.client.put('/api/inspection-schedule',json=body).status_code,500)
        self.cur.execute('SELECT inspector_ids FROM inspection_schedule_cells WHERE station_id=1')
        self.assertTrue(all(r['inspector_ids']==[2] for r in self.cur.fetchall()))
        self.cur.execute('SELECT 1 FROM inspection_schedule_cells WHERE station_id=2'); self.assertIsNone(self.cur.fetchone())
        self.cur.execute('ALTER TABLE inspection_schedule_events DROP CONSTRAINT inspection_schedule_events_station_id_check'); self.admin.commit()
        result=self.client.put('/api/inspection-schedule',json=body)
        self.assertEqual(result.status_code,200,result.json)
        self.cur.execute('SELECT inspector_ids FROM inspection_schedule_cells WHERE station_id=1')
        self.assertTrue(all(r['inspector_ids']==[] for r in self.cur.fetchall()))
        self.cur.execute("SELECT status,COUNT(*) AS n FROM inspection_schedule_tasks GROUP BY status")
        self.assertEqual({r['status']:r['n'] for r in self.cur.fetchall()},dict(cancelled=6,pending=6))

    def test_concurrent_moves_only_one_destination_commits(self):
        self.save()
        def move(sid):
            return self.client.application.test_client().put('/api/inspection-schedule',json=dict(**self.query,
                cells=self.row_cells(sid),source=dict(cells=self.row_cells(1,1)),inspector_ids=[2],scheduled_date='2026-10-20')).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(move,[2,3])),[200,409])

    def test_row_only_bulk_rejects_a_column_even_for_video(self):
        self.cur.execute('DELETE FROM staff_daily_teams'); self.admin.commit()
        response=self.video(cells=[dict(station_id=sid,column_key='safety',revision=0) for sid in (1,2)])
        self.assertEqual(response.status_code,409)
        self.cur.execute('SELECT 1 FROM inspection_schedule_cells'); self.assertIsNone(self.cur.fetchone())
        self.assertEqual(self.video(cells=123).status_code,400)

    def test_legacy_transfer_api_also_moves_the_whole_video_row(self):
        self.cur.execute('DELETE FROM staff_daily_teams'); self.admin.commit()
        self.assertEqual(self.video().status_code,200)
        source=dict(cells=[dict(station_id=1,column_key=k,revision=1) for k,_,_ in COLUMNS['online']])
        result=self.video(station_id=2,source=source)
        self.assertEqual(result.status_code,200,result.json)
        self.cur.execute('SELECT station_id,inspector_ids FROM inspection_schedule_cells ORDER BY station_id')
        self.assertEqual([dict(r) for r in self.cur.fetchall()],[dict(station_id=1,inspector_ids=[])]*3+[dict(station_id=2,inspector_ids=[2])]*3)
        self.assertEqual(self.video(source=dict(cells=source['cells'][:1]),inspector_ids=None).status_code,409)

    def test_field_expires_next_day_without_creating_actual_records_video_remains(self):
        self.save()
        with patch('inspection_schedule_tasks.today',return_value=date(2026,10,20)):
            inbox=self.client.get('/api/my-schedule-tasks').json
            self.assertEqual(inbox['count'],6)
            self.assertEqual(inbox['agenda']['assignment']['group_name'],'外勤步雪琼组')
        with patch('inspection_schedule_tasks.today',return_value=date(2026,10,21)):
            self.assertEqual(self.client.get('/api/my-schedule-tasks').json['count'],0)
        self.cur.execute("SELECT COUNT(*) AS n FROM inspection_schedule_tasks WHERE status='expired' AND expired_at IS NOT NULL")
        self.assertEqual(self.cur.fetchone()['n'],6)
        self.cur.execute('SELECT COUNT(*) AS n FROM inspections'); self.assertEqual(self.cur.fetchone()['n'],0)

    def test_migration_is_repeatable_and_keeps_plans(self):
        self.save()
        sql=(Path(__file__).resolve().parents[1]/'db/init/530_schedule_dispatch.sql').read_text()
        self.cur.execute(sql); self.cur.execute(sql); self.admin.commit()
        self.assertEqual(self.board()['rows'][0]['cells']['odor']['plan_team']['leader_id'],2)


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST')=='1','isolated database opt-in')
class TeamAdjustmentDatabaseTests(unittest.TestCase):
    setUp=team_tests.DailyTeamDatabaseTests.setUp
    setUp_base=staff_tests.StaffDatabaseTests.setUp_base
    connect=staff_tests.StaffDatabaseTests.connect
    tearDown=staff_tests.StaffDatabaseTests.tearDown
    availability=staff_tests.StaffDatabaseTests.availability
    post=team_tests.DailyTeamDatabaseTests.post
    confirm=team_tests.DailyTeamDatabaseTests.confirm

    def move(self, uid, leader, revision=1):
        return self.post('move',student_id=uid,leader_id=leader,revision=revision)

    def test_student_moves_between_groups_and_persists_with_audit(self):
        saved=self.confirm().json
        student=next(p for g in saved['groups'] if g['mode']=='offline' for p in g['members'] if p['position']=='大学生')
        result=self.move(student['id'],None); self.assertEqual(result.status_code,200,result.json)
        self.assertEqual(result.json['revision'],2)
        stored=self.client.get('/api/staff-availability/today-inspection').json
        self.assertTrue(any(p['id']==student['id'] for g in stored['groups'] if g['mode']=='online' for p in g['members']))
        self.assertEqual(self.move(student['id'],2).status_code,409,'stale version')
        self.assertEqual(self.move(2,None,2).status_code,400,'manager cannot be dragged as a student')
        self.cur.execute('SELECT before_value,after_value FROM staff_daily_team_events ORDER BY id DESC LIMIT 1')
        event=self.cur.fetchone(); self.assertNotEqual(event['before_value'],event['after_value'])

    def test_move_conflict_permission_and_audit_failure(self):
        saved=self.confirm().json
        student=next(p for g in saved['groups'] if g['mode']=='offline' for p in g['members'] if p['position']=='大学生')
        self.cur.execute('ALTER TABLE staff_daily_team_events ADD CHECK(false) NOT VALID'); self.admin.commit()
        with self.assertLogs(level='ERROR'):
            self.assertEqual(self.move(student['id'],None).status_code,500)
        self.cur.execute("SELECT revision FROM staff_daily_teams WHERE day='2026-10-19'"); self.assertEqual(self.cur.fetchone()['revision'],1)
        self.permissions.discard('edit_staff_availability')
        self.assertEqual(self.move(student['id'],None).status_code,403)

    def test_auto_quota_routes_video_single_person_token_and_post_dispatch_team_guard(self):
        self.confirm()
        options=dict(day='2026-10-19',offline_count=2,online_count=3)
        response=self.client.post('/api/inspection-schedule/auto',json=dict(action='preview',**options))
        self.assertEqual(response.status_code,200,response.json)
        preview=response.json
        self.assertTrue(any(g['mode']=='offline' for g in preview['groups']))
        self.assertTrue(all(len(g['inspector_ids'])==1 for g in preview['groups'] if g['mode']=='online'))
        altered=self.client.post('/api/inspection-schedule/auto',json=dict(action='confirm',**{**options,'offline_count':1},token=preview['token']))
        self.assertEqual(altered.status_code,409)
        result=self.client.post('/api/inspection-schedule/auto',json=dict(action='confirm',**options,token=preview['token']))
        self.assertEqual(result.status_code,200,result.json)
        group=next(g for g in result.json['groups'] if g['mode']=='offline')
        student=next((p for p in group['team_members'] if p['position']=='大学生'),None)
        self.assertIsNotNone(student)
        self.assertEqual(self.move(student['id'],None).status_code,409)

    def test_invalid_quota_and_missing_coordinates_are_explicit(self):
        self.confirm()
        for extra in [dict(offline_count=0),dict(online_count=True),dict(online_count=11)]:
            response=self.client.post('/api/inspection-schedule/auto',json=dict(action='preview',day='2026-10-19',**extra))
            self.assertEqual(response.status_code,400,response.json)
        self.cur.execute('UPDATE stations SET longitude=NULL'); self.admin.commit()
        response=self.client.post('/api/inspection-schedule/auto',json=dict(action='preview',day='2026-10-19'))
        self.assertFalse(any(g['mode']=='offline' for g in response.json['groups']))
        self.assertTrue(any('缺少有效坐标' in w for w in response.json['warnings']))

    def test_field_student_transfer_updates_unfinished_station_plans_and_tasks_atomically(self):
        self.confirm()
        options=dict(day='2026-10-19')
        preview=self.client.post('/api/inspection-schedule/auto',json=dict(action='preview',**options)).json
        self.assertEqual(self.client.post('/api/inspection-schedule/auto',json=dict(action='confirm',**options,token=preview['token'])).status_code,200)
        field=[g for g in preview['groups'] if g['mode']=='offline']
        source=field[0]
        student=next(p for p in source['team_members'] if p['position']=='大学生')
        target=next(g for g in field if g['person']['id']!=source['person']['id'])
        # First verify station-task write failure rolls the team move back too.
        self.cur.execute('ALTER TABLE inspection_schedule_events ADD CHECK(false) NOT VALID'); self.admin.commit()
        with self.assertLogs(level='ERROR'):
            self.assertEqual(self.move(student['id'],target['person']['id']).status_code,500)
        self.cur.execute("SELECT revision FROM staff_daily_teams WHERE day='2026-10-19'"); self.assertEqual(self.cur.fetchone()['revision'],1)
        self.cur.execute('ALTER TABLE inspection_schedule_events DROP CONSTRAINT inspection_schedule_events_check'); self.admin.commit()
        result=self.move(student['id'],target['person']['id']); self.assertEqual(result.status_code,200,result.json)
        self.cur.execute('SELECT inspector_ids FROM inspection_schedule_cells WHERE mode=%s AND station_id=%s',('offline',source['station_id']))
        self.assertTrue(all(student['id'] not in r['inspector_ids'] for r in self.cur.fetchall()))
        self.cur.execute('SELECT inspector_ids FROM inspection_schedule_cells WHERE mode=%s AND station_id=%s',('offline',target['station_id']))
        self.assertTrue(all(student['id'] in r['inspector_ids'] for r in self.cur.fetchall()))
        self.cur.execute("SELECT station_id FROM inspection_schedule_tasks WHERE mode='offline' AND user_id=%s AND status='pending'",(student['id'],))
        self.assertEqual({r['station_id'] for r in self.cur.fetchall()},{g['station_id'] for g in field if g['person']['id']==target['person']['id']})
