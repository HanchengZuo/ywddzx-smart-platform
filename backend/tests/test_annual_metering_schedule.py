"""Annual/monthly isolation, transactional links, shared dispatch, and quota priority."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from flask import Flask
from unittest.mock import MagicMock
from inspection_schedule_catalog import roster
from inspection_schedule import VIEW_PERMISSION, EDIT_PERMISSION
from annual_metering_plan import register_metering_plan, validate_quotas
from schedule_period import period
from schedule_routes import field_routes
from tests import test_inspection_schedule as base
from tests import test_staff_daily_teams as daily
from tests import test_schedule_v101 as coverage


class MeteringUnitTests(unittest.TestCase):
    def test_annual_period_and_roster_do_not_change_map_periods(self):
        from scheduling_map import period as map_period
        chosen,start,end=period(dict(mode='annual',year=2026))
        self.assertEqual((start,end),(date(2026,1,1),date(2027,1,1)))
        self.assertEqual(chosen['annual'],1)
        self.assertEqual(roster('annual'),roster('offline'))
        self.assertEqual(roster('online'),roster('offline'))
        with self.assertRaises(ValueError): map_period(dict(mode='annual'))
        for year in (True,1999,2101,'bad'):
            with self.assertRaises(ValueError): period(dict(mode='annual',year=year))

    def test_quota_validation_and_auth_precedes_connection(self):
        regions=[dict(region='松金',total=2)]
        self.assertEqual(validate_quotas({'10':{'松金':1}},regions),{'10':{'松金':1}})
        for quotas in ({'13':{}},{'10':{'松金':True}},{'10':{'松金':-1}},{'10':{'其他':1}},
                       {'10':{'松金':2},'11':{'松金':1}}):
            with self.assertRaises(ValueError): validate_quotas(quotas,regions)
        app=Flask(__name__); connect=MagicMock()
        register_metering_plan(app,connect=connect,has_permission=lambda *_:True)
        self.assertEqual(app.test_client().get('/api/inspection-schedule/metering-plan').status_code,401)
        connect.assert_not_called()

    def test_required_stations_are_never_swapped_out_for_nearer_stations(self):
        stations=[dict(station_id=i,region='松金' if i<5 else '浦东',covered=False,longitude=121.1+i*.03,latitude=31.2) for i in range(10)]
        for count,quota,required in ((2,2,{0,9}),(1,2,{8,9}),(2,2,{6,7,8,9})):
            routes=field_routes(stations,count,quota,required_ids=required)
            selected=[s['station_id'] for group in routes for s in group]
            self.assertTrue(required<=set(selected))
            self.assertEqual(len(selected),len(set(selected)))
            self.assertTrue(all(len(g)<=quota for g in routes))


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST')=='1','isolated database opt-in')
class MeteringDatabaseTests(unittest.TestCase):
    setUp=base.ScheduleDatabaseTest.setUp
    connect=base.ScheduleDatabaseTest.connect
    tearDown=base.ScheduleDatabaseTest.tearDown
    board=base.ScheduleDatabaseTest.board
    save=base.ScheduleDatabaseTest.save
    record=base.ScheduleDatabaseTest.record

    def annual(self): return self.board(dict(mode='annual',year=2026))

    def assign_annual(self,sid=1,ids=None,day='2026-10-20'):
        row=next(r for r in self.annual()['rows'] if r['station_id']==sid)
        cells=[dict(station_id=sid,column_key=k,revision=c['revision']) for k,c in row['cells'].items() if c['status'] in ('assigned','unassigned')]
        return self.client.put('/api/inspection-schedule',json=dict(mode='annual',year=2026,inspector_ids=[2] if ids is None else ids,
            scheduled_date=day,cells=cells))

    def plan(self,quota=1,revision=0):
        return self.client.put('/api/inspection-schedule/metering-plan',json=dict(year=2026,month=10,quotas={'10':{'松金':quota}},revision=revision))

    def test_annual_columns_monitor_gate_and_atomic_quarter_link(self):
        board=self.annual()
        self.assertEqual(len(board['rows']),len(self.board()['rows']))
        self.assertEqual(board['rows'][0]['cells']['metering_video']['status'],'unavailable')
        invalid=self.client.put('/api/inspection-schedule',json=dict(mode='annual',year=2026,inspector_ids=[2],scheduled_date='2026-10-20',
            cells=[dict(station_id=1,column_key='metering_video',revision=0)]))
        self.assertEqual(invalid.status_code,409)
        self.cur.execute("UPDATE stations SET monitoring_status='未运行' WHERE id=1"); self.admin.commit()
        half=self.client.put('/api/inspection-schedule',json=dict(mode='annual',year=2026,inspector_ids=[2],scheduled_date='2026-10-20',
            cells=[dict(station_id=1,column_key='metering_site',revision=0)]))
        self.assertEqual(half.status_code,409)
        result=self.assign_annual(); self.assertEqual(result.status_code,200,result.json)
        self.assertTrue(all(c['status']=='assigned' for c in self.annual()['rows'][0]['cells'].values()))
        self.assertTrue(all(c['assignees'][0]['id']==2 for c in self.board()['rows'][0]['cells'].values()))
        self.cur.execute("SELECT DISTINCT mode FROM inspection_schedule_tasks WHERE column_key LIKE 'metering_%'")
        self.assertEqual([r['mode'] for r in self.cur.fetchall()],['offline'])
        result=self.assign_annual(ids=[]); self.assertEqual(result.status_code,200,result.json)
        self.assertTrue(all(c['status']=='unassigned' for c in self.board()['rows'][0]['cells'].values()))
        self.cur.execute("SELECT COUNT(*) AS n FROM inspection_schedule_tasks WHERE status='pending'");self.assertEqual(self.cur.fetchone()['n'],0)

    def test_quarter_only_links_monthly_quota_members_not_every_station(self):
        self.assertEqual(self.save(station_id=1).status_code,200)
        self.assertEqual(self.annual()['rows'][0]['cells']['metering_site']['status'],'unassigned')
        self.assertEqual(self.plan().status_code,200)
        self.assertEqual(self.save(station_id=3).status_code,200)
        annual={r['station_id']:r for r in self.annual()['rows']}
        self.assertEqual(annual[3]['cells']['metering_site']['status'],'assigned')
        self.assertEqual(annual[1]['cells']['metering_site']['status'],'unassigned')
        self.assertEqual(self.save(station_id=2).status_code,200)
        self.assertEqual(next(r for r in self.annual()['rows'] if r['station_id']==2)['cells']['metering_site']['status'],'unassigned')
        state=self.client.get('/api/inspection-schedule/metering-plan?year=2026&month=10').json
        region=next(r for r in state['regions'] if r['region']=='松金')
        self.assertEqual((region['completed'],region['reserved'],region['remaining']),(0,1,0))

    def test_actual_locks_and_audit_failure_roll_back_both_boards(self):
        self.record(table=1)
        self.cur.execute('ALTER TABLE inspection_schedule_events ADD CHECK(false) NOT VALID'); self.admin.commit()
        with self.assertLogs(level='ERROR'):
            self.assertEqual(self.assign_annual().status_code,500)
        self.cur.execute('SELECT COUNT(*) AS n FROM inspection_schedule_cells');self.assertEqual(self.cur.fetchone()['n'],0)
        self.cur.execute('SELECT COUNT(*) AS n FROM inspection_schedule_tasks');self.assertEqual(self.cur.fetchone()['n'],0)
        self.cur.execute('ALTER TABLE inspection_schedule_events DROP CONSTRAINT inspection_schedule_events_check');self.admin.commit()
        self.assertEqual(self.assign_annual().status_code,200)
        cells=self.board()['rows'][0]['cells']
        self.assertEqual(cells['odor']['status'],'completed')
        self.assertEqual(cells['finance']['status'],'assigned')

    def test_shared_shelf_park_place_keeps_both_boards_in_sync(self):
        self.cur.execute("INSERT INTO staff_daily_teams(day,assignments,revision,updated_by) SELECT '2026-10-19',assignments,1,1 FROM staff_daily_teams WHERE day='2026-10-20'")
        self.admin.commit()
        self.assertEqual(self.assign_annual(day='2026-10-19').status_code,200)
        board=self.annual(); row=board['rows'][0]
        parked=self.client.post('/api/inspection-schedule/dispatch',json=dict(mode='annual',year=2026,action='park',cells=[dict(station_id=1,column_key='metering_site',revision=row['cells']['metering_site']['revision'])]))
        self.assertEqual(parked.status_code,200,parked.json)
        self.assertTrue(all(c['status']=='unassigned' for c in self.board()['rows'][0]['cells'].values()))
        shelf=parked.json['board']['shelf'][0]
        self.assertEqual(shelf['id'],self.board()['shelf'][0]['id'])
        target=parked.json['board']['rows'][1]
        placed=self.client.post('/api/inspection-schedule/dispatch',json=dict(mode='annual',year=2026,action='place',shelf_id=shelf['id'],revision=shelf['revision'],
            cells=[dict(station_id=target['station_id'],column_key='metering_site',revision=target['cells']['metering_site']['revision'])]))
        self.assertEqual(placed.status_code,200,placed.json)
        self.assertTrue(all(c['status']=='assigned' for c in self.board()['rows'][1]['cells'].values()))

    def test_month_actual_counts_unaudited_distinct_stations_and_releases_past_reservation(self):
        self.assertEqual(self.plan(2).status_code,200)
        self.cur.execute("SELECT id FROM inspection_tables WHERE table_name='计量稽查检查表（现场）'")
        table=self.cur.fetchone()['id']
        self.record(table=table,day='2026-10-01');self.record(table=table,day='2026-10-02')
        self.record(station=3,table=table,day='2026-09-30')
        state=self.client.get('/api/inspection-schedule/metering-plan?year=2026&month=10').json
        region=next(r for r in state['regions'] if r['region']=='松金')
        self.assertEqual((region['completed'],region['remaining']),(1,1))
        self.cur.execute("INSERT INTO inspection_schedule_cells(mode,year,period_number,station_id,column_key,inspector_ids,revision,scheduled_date) VALUES('annual',2026,1,3,'metering_site','[2]',1,'2026-10-18')")
        self.admin.commit()
        state=self.client.get('/api/inspection-schedule/metering-plan?year=2026&month=10').json
        self.assertEqual(next(r for r in state['regions'] if r['region']=='松金')['reserved'],0)

    def test_plan_permissions_revision_audit_rollback_and_concurrent_edit(self):
        self.permissions.clear()
        self.assertEqual(self.plan().status_code,403)
        self.permissions.add(VIEW_PERMISSION)
        self.assertEqual(self.plan().status_code,403)
        self.permissions.add(EDIT_PERMISSION)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.client.application.test_client().put('/api/inspection-schedule/metering-plan',json=dict(year=2026,month=10,revision=0,quotas={'10':{'松金':1}})).status_code,range(2)))
        self.assertEqual(sorted(results),[200,409])
        self.cur.execute('SELECT actor_id FROM annual_metering_plan_events');self.assertEqual(self.cur.fetchone()['actor_id'],self.actor['id'])
        self.cur.execute('ALTER TABLE annual_metering_plan_events ADD CHECK(false) NOT VALID');self.admin.commit()
        with self.assertLogs(level='ERROR'): self.assertEqual(self.plan(2,1).status_code,500)
        self.cur.execute('SELECT revision,quotas FROM annual_metering_plans');self.assertEqual(self.cur.fetchone()['revision'],1)

    def test_concurrent_quarter_dispatch_reserves_monthly_quota_once(self):
        self.assertEqual(self.plan().status_code,200)
        def assign(sid):
            return self.client.application.test_client().put('/api/inspection-schedule',json=dict(**self.query,inspector_ids=[2],scheduled_date='2026-10-20',cells=[dict(station_id=sid,column_key=key,revision=0) for key,_,_ in base.COLUMNS['offline']])).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(assign,[1,3]))
        self.assertEqual(results,[200,200])
        self.cur.execute("SELECT COUNT(*) AS n FROM inspection_schedule_cells WHERE mode='annual' AND column_key='metering_site' AND inspector_ids<>'[]'::jsonb")
        self.assertEqual(self.cur.fetchone()['n'],1)

    def test_moving_quarter_plan_to_an_unconfigured_month_releases_old_metering_plan(self):
        self.assertEqual(self.plan().status_code,200)
        self.assertEqual(self.save().status_code,200)
        self.cur.execute("INSERT INTO staff_daily_teams(day,assignments,revision,updated_by) SELECT '2026-11-02',assignments,1,1 FROM staff_daily_teams WHERE day='2026-10-20'")
        self.cur.execute("INSERT INTO staff_availability(person_name,day,available,revision,updated_by) VALUES('步雪琼','2026-11-02',true,1,1)")
        self.admin.commit()
        result=self.save(revision=1,scheduled_date='2026-11-02')
        self.assertEqual(result.status_code,200,result.json)
        self.assertEqual(self.annual()['rows'][0]['cells']['metering_site']['status'],'unassigned')
        self.cur.execute("SELECT COUNT(*) AS n FROM inspection_schedule_tasks WHERE status='pending' AND column_key LIKE 'metering_%'")
        self.assertEqual(self.cur.fetchone()['n'],0)

    def test_migration_repeat_and_video_roster_exclusion_explained(self):
        self.assertEqual(self.plan().status_code,200)
        sql=(Path(__file__).resolve().parents[1]/'db/init/560_annual_metering_schedule.sql').read_text()
        self.cur.execute(sql);self.cur.execute(sql)
        self.cur.execute('UPDATE stations SET include_online_plan=false WHERE id=1');self.admin.commit()
        board=self.board(dict(mode='online',year=2026,month=10))
        self.assertEqual(board['roster_total'],155)
        self.assertTrue(any(s['station_name']=='沈浦泾南' for s in board['excluded_stations']))
        self.cur.execute('SELECT revision FROM annual_metering_plans');self.assertEqual(self.cur.fetchone()['revision'],1)


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST')=='1','isolated database opt-in')
class MeteringAutomationTests(unittest.TestCase):
    setUp=coverage.CoverageDatabaseTests.setUp
    setUp_base=coverage.CoverageDatabaseTests.setUp_base
    connect=coverage.CoverageDatabaseTests.connect
    tearDown=coverage.CoverageDatabaseTests.tearDown
    record=coverage.CoverageDatabaseTests.record
    save=coverage.CoverageDatabaseTests.save
    preview=coverage.CoverageDatabaseTests.preview

    def test_unmet_metering_quota_precedes_quarter_coverage_and_stale_plan_rejected(self):
        self.record(table=1,station=1)
        self.record(table=1,station=3)
        result=self.client.put('/api/inspection-schedule/metering-plan',json=dict(year=2026,month=10,revision=0,quotas={'10':{'松金':2}}))
        self.assertEqual(result.status_code,200,result.json)
        preview=self.preview()
        field=[g for g in preview['groups'] if g['mode']=='offline']
        self.assertEqual({g['station_id'] for g in field},{1,3})
        self.assertTrue(all(g['metering_priority'] and g['metering_cells'] for g in field))
        body=dict(action='confirm',day='2026-10-19',offline_count=1,token=preview['token'])
        self.cur.execute("UPDATE annual_metering_plans SET revision=2");self.admin.commit()
        self.assertEqual(self.client.post('/api/inspection-schedule/auto',json=body).status_code,409)
        body['token']=self.preview()['token']
        result=self.client.post('/api/inspection-schedule/auto',json=body)
        self.assertEqual(result.status_code,200,result.json)
        self.cur.execute("SELECT COUNT(*) AS n FROM inspection_schedule_cells WHERE mode='annual' AND inspector_ids<>'[]'::jsonb")
        self.assertEqual(self.cur.fetchone()['n'],2)


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST')=='1','isolated database opt-in')
class DailyShelfTests(unittest.TestCase):
    setUp=daily.DailyTeamDatabaseTests.setUp
    setUp_base=daily.DailyTeamDatabaseTests.setUp_base
    connect=daily.DailyTeamDatabaseTests.connect
    tearDown=daily.DailyTeamDatabaseTests.tearDown
    availability=daily.DailyTeamDatabaseTests.availability
    post=daily.DailyTeamDatabaseTests.post
    confirm=daily.DailyTeamDatabaseTests.confirm

    def test_group_confirmation_publishes_manual_cards_without_auto_dispatch(self):
        result=self.confirm().json
        board=self.client.get('/api/inspection-schedule?mode=offline&year=2026&quarter=4').json
        self.assertEqual(len(board['shelf']),len([g for g in result['groups'] if g['mode']=='offline']))
        item=board['shelf'][0]
        self.assertEqual(item['source_column_key'],'personnel')
        row=board['rows'][0]
        placed=self.client.post('/api/inspection-schedule/dispatch',json=dict(mode='offline',year=2026,quarter=4,action='place',shelf_id=item['id'],revision=item['revision'],
            cells=[dict(station_id=row['station_id'],column_key=k,revision=c['revision']) for k,c in row['cells'].items()]))
        self.assertEqual(placed.status_code,200,placed.json)
        self.assertTrue(any(s['id']==item['id'] for s in placed.json['board']['shelf']))
        video=self.client.get('/api/inspection-schedule?mode=online&year=2026&month=10').json['shelf']
        self.assertTrue(video)
        self.assertTrue(all(len(s['ids'])==1 for s in video))
