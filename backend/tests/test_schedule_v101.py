"""v10.1 default availability and coverage-first compact dispatch regression tests."""
import os
import time
import unittest
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from unittest.mock import patch

from schedule_routes import regional_coverage, regional_targets, field_routes, cluster_diameter
from staff_availability import VIEW, EDIT, ensure_today_availability
from tests import test_staff_scheduling as staff_tests


class CoverageTests(unittest.TestCase):
    def stations(self, region, count, offset=0, covered=False):
        return [dict(station_id=offset+i,region=region,covered=covered,
                     longitude=121.2+offset*.001+i*.001,latitude=31.2) for i in range(count)]

    def test_water_fill_balances_rates_not_equal_counts(self):
        stations = self.stations('小片区',2)+self.stations('大片区',10,10)
        targets,stats = regional_targets(stations,6,[dict(region='小片区',total=2,checked=0,reserved=0),
                                                  dict(region='大片区',total=10,checked=0,reserved=0)])
        self.assertEqual(dict(targets),{('小片区',False):1,('大片区',False):5})
        self.assertEqual([r['projected_rate'] for r in stats],[50,50])

    def test_low_coverage_has_priority_over_nearby_high_coverage_and_reservations_count(self):
        stations = self.stations('近',2)+self.stations('远',10,100)
        coverage = [dict(region='近',total=10,checked=8,reserved=0),dict(region='远',total=10,checked=0,reserved=0)]
        groups = field_routes(stations,2,2,(121.2,31.2),coverage=coverage)
        self.assertEqual({s['region'] for g in groups for s in g},{'远'})
        coverage[0]['checked']=0; coverage[0]['reserved']=8
        self.assertEqual({s['region'] for g in field_routes(stations,2,2,coverage=coverage) for s in g},{'远'})

    def test_partial_station_not_counted_twice_and_new_stations_selected_before_partial(self):
        stations = self.stations('甲',2)+self.stations('甲',1,10,covered=True)
        targets,stats = regional_targets(stations,2,[dict(region='甲',total=3,checked=1,reserved=0)])
        self.assertEqual(dict(targets),{('甲',False):2})
        self.assertEqual(stats[0]['projected_rate'],100)
        targets,stats = regional_targets(stations,10,[dict(region='甲',total=3,checked=1,reserved=0)])
        self.assertEqual(stats[0]['selected'],3)
        self.assertEqual(stats[0]['projected_rate'],100)
        self.assertEqual(targets[('甲',True)],1)

    def test_coverage_uses_unreviewed_records_and_only_live_plan_reservations(self):
        def cell(status,day=None): return dict(status=status,scheduled_date=day)
        rows = [dict(region='甲',cells={'a':cell('completed'),'b':cell('assigned','2026-10-20')}),
                dict(region='甲',cells={'a':cell('assigned','2026-10-19')}),
                dict(region='甲',cells={'a':cell('assigned','2026-10-18')}),
                dict(region='乙',cells={'a':cell('unassigned')})]
        self.assertEqual(regional_coverage(rows,date(2026,10,19)),
                         [dict(region='甲',total=3,checked=1,reserved=1),dict(region='乙',total=1,checked=0,reserved=0)])

    def test_compact_clustering_keeps_region_quotas_caps_and_determinism(self):
        stations = self.stations('甲',20)+self.stations('乙',10,100)
        coverage = [dict(region='甲',total=20,checked=0,reserved=0),dict(region='乙',total=10,checked=0,reserved=0)]
        groups = field_routes(stations,3,2,coverage=coverage)
        self.assertEqual([len(g) for g in groups],[2,2,2])
        self.assertEqual(Counter(s['region'] for g in groups for s in g),{'甲':4,'乙':2})
        self.assertTrue(all(cluster_diameter(g)<1 for g in groups))
        self.assertEqual(groups,field_routes(list(reversed(stations)),3,2,(122,32),coverage=coverage))
        self.assertEqual(len({s['station_id'] for g in groups for s in g}),6)

    def test_shortage_missing_coordinates_zero_quota_and_bounded_runtime(self):
        stations = self.stations('甲',2)
        self.assertEqual([len(g) for g in field_routes(stations,7,2)],[1,1])
        self.assertEqual(field_routes(stations,7,0),[])
        self.assertEqual(field_routes([dict(station_id=1)],2,2),[])
        stations = [s for i in range(7) for s in self.stations(str(i),22,i*22)]
        started=time.monotonic()
        groups=field_routes(stations,7,10)
        self.assertEqual(sum(map(len,groups)),70)
        self.assertLess(time.monotonic()-started,3)


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST')=='1','isolated database opt-in')
class DefaultAvailabilityDatabaseTests(unittest.TestCase):
    setUp=staff_tests.StaffDatabaseTests.setUp
    setUp_base=staff_tests.StaffDatabaseTests.setUp_base
    connect=staff_tests.StaffDatabaseTests.connect
    tearDown=staff_tests.StaffDatabaseTests.tearDown
    availability=staff_tests.StaffDatabaseTests.availability
    record=staff_tests.StaffDatabaseTests.record

    def test_today_defaults_persist_but_manual_busy_future_and_past_are_unchanged(self):
        self.availability(name='孔德辰',available=False,reason='培训')
        self.availability(name='赵之龙',day='2026-10-20',available=False,reason='出差')
        response=self.client.get('/api/staff-availability?week=2026-10-19')
        self.assertEqual(response.status_code,200,response.json)
        people={p['display_name']:p for p in response.json['people']}
        self.assertEqual(people['步雪琼']['cells']['2026-10-19']['available'],True)
        self.assertEqual(people['步雪琼']['cells']['2026-10-19']['updated_by_name'],'系统默认')
        self.assertTrue(people['步雪琼']['cells']['2026-10-19']['is_default'])
        self.assertFalse(people['孔德辰']['cells']['2026-10-19']['available'])
        self.assertEqual(people['孔德辰']['cells']['2026-10-19']['reason'],'培训')
        self.assertIsNone(people['陈中磊']['cells']['2026-10-20']['available'])
        self.cur.execute("SELECT COUNT(*) AS n FROM staff_availability WHERE day='2026-10-19'")
        self.assertEqual(self.cur.fetchone()['n'],25)
        self.cur.execute("SELECT COUNT(*) AS n FROM staff_availability WHERE day<'2026-10-19'")
        self.assertEqual(self.cur.fetchone()['n'],0)
        self.cur.execute("SELECT actor_id,actor_name FROM staff_availability_events WHERE after_value->>'is_default'='true'")
        events=self.cur.fetchall(); self.assertEqual(len(events),24)
        self.assertTrue(all(e['actor_id'] is None and e['actor_name']=='系统默认有空' for e in events))
        self.client.get('/api/staff-availability?week=2026-10-19')
        self.cur.execute("SELECT COUNT(*) AS n FROM staff_availability_events WHERE after_value->>'is_default'='true'")
        self.assertEqual(self.cur.fetchone()['n'],24)
        with patch('staff_availability.today',return_value=date(2026,10,20)):
            next_day=self.client.get('/api/staff-availability?week=2026-10-19').json
            cell=next_day['people'][0]['cells']['2026-10-19']
            self.assertTrue(cell['available']); self.assertTrue(cell['is_default'])
            busy=next_day['people'][2]['cells']['2026-10-20']
            self.assertFalse(busy['available']); self.assertEqual(busy['reason'],'出差')

    def test_manual_busy_replaces_default_with_actor_audit_and_rejects_stale_revision(self):
        self.client.get('/api/staff-availability?week=2026-10-19')
        response=self.availability(available=False,reason='出差')
        self.assertEqual(response.status_code,200,response.json)
        self.cur.execute("SELECT available,reason,is_default,revision,updated_by FROM staff_availability WHERE person_name='步雪琼' AND day='2026-10-19'")
        self.assertEqual(dict(self.cur.fetchone()),dict(available=False,reason='出差',is_default=False,revision=2,updated_by=2))
        result=self.client.put('/api/staff-availability',json=dict(available=True,cells=[dict(person_name='步雪琼',day='2026-10-19',revision=1)]))
        self.assertEqual(result.status_code,409)
        self.cur.execute('SELECT before_value,after_value,actor_id FROM staff_availability_events ORDER BY id DESC LIMIT 1')
        event=self.cur.fetchone(); self.assertTrue(event['before_value']['is_default'])
        self.assertFalse(event['after_value']['available']); self.assertEqual(event['actor_id'],2)

    def test_default_audit_failure_rolls_back_and_permission_denial_does_not_initialize(self):
        self.permissions.discard(VIEW)
        self.assertEqual(self.client.get('/api/staff-availability').status_code,403)
        self.cur.execute("SELECT 1 FROM staff_availability WHERE day='2026-10-19'");self.assertIsNone(self.cur.fetchone())
        self.permissions.add(VIEW); self.permissions.discard(EDIT)
        self.cur.execute('ALTER TABLE staff_availability_events ADD CHECK(false) NOT VALID');self.admin.commit()
        with self.assertLogs(level='ERROR'):
            self.assertEqual(self.client.get('/api/staff-availability').status_code,500)
        self.cur.execute("SELECT 1 FROM staff_availability WHERE day='2026-10-19'");self.assertIsNone(self.cur.fetchone())

    def test_concurrent_readers_seed_once_without_changing_preconfigured_busy(self):
        self.availability(available=False,reason='休假')
        def seed(_):
            conn=self.connect()
            try:
                with conn.cursor() as cur: ensure_today_availability(cur)
                conn.commit()
            finally: conn.close()
        with ThreadPoolExecutor(max_workers=4) as pool: list(pool.map(seed,range(8)))
        self.cur.execute("SELECT COUNT(*) AS n FROM staff_availability_events WHERE after_value->>'is_default'='true'")
        self.assertEqual(self.cur.fetchone()['n'],24)
        self.cur.execute("SELECT available,reason,revision FROM staff_availability WHERE person_name='步雪琼' AND day='2026-10-19'")
        self.assertEqual(dict(self.cur.fetchone()),dict(available=False,reason='休假',revision=1))

    def test_default_initialization_does_not_wait_behind_dispatch_lock(self):
        other=self.connect()
        try:
            with other.cursor() as cur: cur.execute('SELECT pg_advisory_xact_lock(9801,1)')
            started=time.monotonic()
            response=self.client.get('/api/staff-availability?week=2026-10-19')
            self.assertEqual(response.status_code,200,response.json)
            self.assertTrue(response.json['people'][0]['cells']['2026-10-19']['available'])
            self.assertEqual(response.json['people'][0]['cells']['2026-10-19']['revision'],0)
            self.assertLess(time.monotonic()-started,1)
        finally: other.close()
        self.client.get('/api/staff-availability?week=2026-10-19')
        self.cur.execute("SELECT COUNT(*) AS n FROM staff_availability WHERE day='2026-10-19'")
        self.assertEqual(self.cur.fetchone()['n'],25)

    def test_preview_available_people_detail_and_own_agenda_persist_defaults(self):
        for path,method,body in [('/api/inspection-schedule/available-people?day=2026-10-19','get',None),
                ('/api/staff-availability/detail?person_name=步雪琼&day=2026-10-19','get',None),
                ('/api/inspection-schedule/auto','post',dict(action='preview',day='2026-10-19')),
                ('/api/my-schedule-tasks','get',None)]:
            self.cur.execute("DELETE FROM staff_availability WHERE day='2026-10-19'"); self.admin.commit()
            response=getattr(self.client,method)(path,json=body)
            self.assertEqual(response.status_code,200,response.json)
            self.cur.execute("SELECT COUNT(*) AS n FROM staff_availability WHERE day='2026-10-19'")
            self.assertEqual(self.cur.fetchone()['n'],25,path)

    def test_repeatable_migration_preserves_manual_choices(self):
        self.availability(available=False,reason='事假')
        sql=(Path(__file__).resolve().parents[1]/'db/init/550_staff_default_availability.sql').read_text()
        self.cur.execute(sql); self.cur.execute(sql);self.admin.commit()
        self.cur.execute("SELECT available,reason,is_default FROM staff_availability WHERE person_name='步雪琼' AND day='2026-10-19'")
        self.assertEqual(dict(self.cur.fetchone()),dict(available=False,reason='事假',is_default=False))


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST')=='1','isolated database opt-in')
class CoverageDatabaseTests(unittest.TestCase):
    setUp_base=staff_tests.StaffDatabaseTests.setUp_base
    connect=staff_tests.StaffDatabaseTests.connect
    tearDown=staff_tests.StaffDatabaseTests.tearDown
    record=staff_tests.StaffDatabaseTests.record
    save=staff_tests.StaffDatabaseTests.save

    def setUp(self):
        import json
        staff_tests.StaffDatabaseTests.setUp(self)
        self.cur.execute('INSERT INTO staff_daily_teams(day,assignments,revision,updated_by) VALUES(%s,%s,1,2)',
            ('2026-10-19',json.dumps([dict(id=uid,display_name=name,position='管理人员',mode='offline',leader_id=uid,group_name=f'外勤{name}组')
                                    for uid,name in [(2,'步雪琼'),(3,'孔德辰')]])))
        self.cur.execute('UPDATE stations SET longitude=121.9 WHERE id=2')
        self.admin.commit()

    def preview(self):
        response=self.client.post('/api/inspection-schedule/auto',json=dict(action='preview',day='2026-10-19',offline_count=1))
        self.assertEqual(response.status_code,200,response.json)
        return response.json

    def test_real_unreviewed_coverage_and_live_plans_balance_regions_before_distance(self):
        result=self.save(scheduled_date='2026-10-19',inspector_ids=[3])
        self.assertEqual(result.status_code,200,result.json)
        preview=self.preview()
        field=[g for g in preview['groups'] if g['mode']=='offline']
        self.assertEqual([g['station_id'] for g in field],[2])
        stats={r['region']:r for r in preview['regional_coverage']}
        self.assertEqual((stats['松金']['total'],stats['松金']['checked'],stats['松金']['reserved']),(2,0,1))
        self.assertEqual(stats['浦东']['selected'],1)
        self.assertEqual(field[0]['driving_seconds'],0)
        self.assertEqual(field[0]['driving_meters'],0)
        self.record(station=1,table=1,inspector=3)
        stats={r['region']:r for r in self.preview()['regional_coverage']}
        self.assertEqual((stats['松金']['checked'],stats['松金']['reserved']),(1,0))

    def test_coverage_change_invalidates_preview_and_does_not_write_dispatch(self):
        preview=self.preview()
        self.record(station=3,table=1,inspector=3)
        result=self.client.post('/api/inspection-schedule/auto',json=dict(action='confirm',day='2026-10-19',offline_count=1,token=preview['token']))
        self.assertEqual(result.status_code,409,result.json)
        self.cur.execute('SELECT 1 FROM inspection_schedule_cells'); self.assertIsNone(self.cur.fetchone())
        preview=self.preview()
        result=self.client.post('/api/inspection-schedule/auto',json=dict(action='confirm',day='2026-10-19',offline_count=1,token=preview['token']))
        self.assertEqual(result.status_code,200,result.json)
        self.cur.execute('SELECT actor_id FROM inspection_schedule_events')
        self.assertTrue(all(r['actor_id']==2 for r in self.cur.fetchall()))
