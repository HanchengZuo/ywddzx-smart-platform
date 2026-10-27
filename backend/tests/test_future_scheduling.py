"""Future and multi-date scheduling against disposable PostgreSQL schemas only."""
import json
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from unittest.mock import MagicMock, patch
from flask import Flask
from schedule_dates import planning_days
from schedule_automation import register_schedule_automation
from staff_daily_team_http import register_staff_daily_teams
from tests import test_staff_daily_teams as teams
from tests import test_schedule_smart as smart


class DateSelectionTests(unittest.TestCase):
    def test_strict_bounded_unique_today_or_future_dates(self):
        start=date(2026,10,19)
        self.assertEqual(planning_days('["2026-11-02","2026-10-19"]',earliest=start),[start,date(2026,11,2)])
        for value in (None, [], ['2026-10-18'], ['2026-10-20']*2, ['2026-10-20']*32,
                      ['2026-02-30'], ['2026-10-20T00:00:00'], 'not-json'):
            with self.assertRaises(ValueError): planning_days(value,earliest=start)

    def test_new_routes_authenticate_before_opening_database(self):
        app=Flask(__name__);connect=MagicMock()
        register_staff_daily_teams(app,connect=connect,has_permission=lambda *_:True)
        register_schedule_automation(app,connect=connect,has_permission=lambda *_:True)
        for path in ('/api/staff-availability/inspection-dates','/api/inspection-schedule/inspection-dates'):
            self.assertEqual(app.test_client().get(path).status_code,401)
        self.assertEqual(app.test_client().post('/api/inspection-schedule/auto/batch').status_code,401)
        connect.assert_not_called()


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST')=='1','isolated database opt-in')
class FutureSchedulingTests(unittest.TestCase):
    setUp=teams.DailyTeamDatabaseTests.setUp
    setUp_base=teams.DailyTeamDatabaseTests.setUp_base
    connect=teams.DailyTeamDatabaseTests.connect
    tearDown=teams.DailyTeamDatabaseTests.tearDown
    availability=teams.DailyTeamDatabaseTests.availability
    record=teams.DailyTeamDatabaseTests.record
    save=teams.DailyTeamDatabaseTests.save
    post=teams.DailyTeamDatabaseTests.post
    confirm=teams.DailyTeamDatabaseTests.confirm
    assign=smart.SmartDatabaseTests.assign
    board=smart.SmartDatabaseTests.board

    def prepare(self,*days,more_stations=False):
        for day in days:
            self.cur.execute('''INSERT INTO staff_availability(person_name,day,available,revision,updated_by)
              SELECT person_name,%s,available,1,1 FROM staff_availability WHERE day='2026-10-19'
              ON CONFLICT(person_name,day) DO UPDATE SET available=EXCLUDED.available''',(day,))
        if more_stations:
            from inspection_schedule_catalog import roster
            for uid,(region,name) in enumerate(list(roster('offline'))[:40],100):
                self.cur.execute('''INSERT INTO stations(id,region,station_name,longitude,latitude)
                  SELECT %s,%s,%s,%s,31.2 WHERE NOT EXISTS(SELECT 1 FROM stations WHERE region=%s AND station_name=%s)''',
                  (uid,region,name,121+uid/1000,region,name))
        self.admin.commit()

    def team_preview(self,days):
        response=self.client.post('/api/staff-availability/today-inspection',json=dict(action='preview',plans=[
            dict(self.body,day=day) for day in days]))
        self.assertEqual(response.status_code,200,response.json)
        return response.json['results']

    def team_apply(self,previews):
        return self.client.post('/api/staff-availability/today-inspection',json=dict(action='apply',plans=[
            dict(day=p['day'],revision=p['revision'],source='generated',manager_modes=p['manager_modes'],
                 seed=p['seed'],token=p['token'],moves=[]) for p in previews]))

    def station_batch(self,days,previews=None,**extra):
        body=dict(action='confirm' if previews is not None else 'preview',dates=days,
                  offline_count=1,online_count=1,quota_revision=0)
        if previews is not None:
            body.update(tokens={p['day']:p['token'] for p in previews},replace_confirmed=True)
        return self.client.post('/api/inspection-schedule/auto/batch',json={**body,**extra})

    def snapshot(self):
        result=[]
        for table in ('staff_daily_teams','staff_daily_team_events','inspection_schedule_cells',
                      'inspection_schedule_tasks','inspection_schedule_events','inspection_schedule_shelf',
                      'inspection_schedule_shelf_events','inspection_schedule_quotas'):
            self.cur.execute(f'SELECT to_jsonb(t) AS item FROM {table} t ORDER BY to_jsonb(t)::text')
            result.append([r['item'] for r in self.cur.fetchall()])
        return result

    def test_only_fully_confirmed_working_dates_are_selectable_and_permissions_remain_independent(self):
        self.prepare('2026-10-20','2026-10-21','2026-10-24','2027-01-04')
        self.cur.execute("DELETE FROM staff_availability WHERE day='2026-10-21' AND person_name='吕泽昆'")
        self.admin.commit()
        response=self.client.get('/api/staff-availability/inspection-dates')
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual([d['day'] for d in response.json['dates']],['2026-10-19','2026-10-20'])
        self.assertEqual(response.headers['Cache-Control'],'private, no-store')
        self.assertEqual(self.post(day='2026-10-21').status_code,409)
        self.assertEqual(self.post(day='2026-10-24').status_code,400)
        self.assertEqual(self.post(day='2027-01-04').status_code,400)
        self.assertEqual(self.client.get('/api/inspection-schedule/inspection-dates').json['dates'],[])
        self.permissions.discard('edit_staff_availability')
        self.assertEqual(self.client.get('/api/staff-availability/inspection-dates').status_code,200)
        self.assertEqual(self.post(day='2026-10-20').status_code,403)
        self.permissions.discard('view_staff_availability')
        self.assertEqual(self.client.get('/api/staff-availability/inspection-dates').status_code,403)
        self.permissions.discard('edit_inspection_schedule')
        self.assertEqual(self.station_batch(['2026-10-20']).status_code,403)
        self.permissions.discard('view_inspection_schedule')
        self.assertEqual(self.client.get('/api/inspection-schedule/inspection-dates').status_code,403)

    def test_future_team_batch_is_pure_until_adoption_and_publishes_independent_dated_cards(self):
        days=['2026-10-20','2026-10-21']
        self.prepare(*days)
        before=self.snapshot(); previews=self.team_preview(list(reversed(days)))
        self.assertEqual(self.snapshot(),before)
        self.assertEqual([p['day'] for p in previews],days)
        self.assertNotEqual(previews[0]['token'],previews[1]['token'])
        adopted=self.team_apply(previews)
        self.assertEqual(adopted.status_code,200,adopted.json)
        dates=self.client.get('/api/inspection-schedule/inspection-dates').json['dates']
        self.assertEqual([d['day'] for d in dates],days)
        results=self.client.get('/api/staff-availability/today-inspection',query_string={'dates':json.dumps(days)}).json['results']
        self.assertEqual([r['revision'] for r in results],[1,1])
        for mode in ('offline','online'):
            cards=self.board(mode)['shelf']
            self.assertEqual({c['day'] for c in cards},set(days))
            self.assertEqual(len({(c['day'],tuple(c['ids'])) for c in cards}),len(cards))
        conflict=self.team_apply(previews)
        self.assertEqual(conflict.status_code,409)
        self.assertIn('2026-10-20',conflict.json['error'])

    def test_personnel_batch_conflict_or_second_date_audit_failure_rolls_back_all_dates(self):
        days=['2026-10-20','2026-10-21'];self.prepare(*days)
        previews=self.team_preview(days)
        self.assertEqual(self.availability(name='陈中磊',day=days[1],available=False).status_code,200)
        before=self.snapshot()
        self.assertEqual(self.team_apply(previews).status_code,409)
        self.assertEqual(self.snapshot(),before)
        previews=self.team_preview(days)
        self.cur.execute("ALTER TABLE staff_daily_team_events ADD CHECK(day<>'2026-10-21') NOT VALID");self.admin.commit()
        with self.assertLogs(level='ERROR'): result=self.team_apply(previews)
        self.assertEqual(result.status_code,500,result.json)
        self.assertEqual(self.snapshot(),before)

    def test_smart_batch_reserves_prior_dates_without_writes_and_adopts_with_date_scoped_tasks(self):
        days=['2026-10-20','2026-10-21'];self.prepare(*days,more_stations=True)
        self.assertEqual(self.team_apply(self.team_preview(days)).status_code,200)
        before=self.snapshot();response=self.station_batch(days)
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(self.snapshot(),before,'preview must not save cells, quotas, tasks or audit')
        results=response.json['results']
        for mode in ('offline','online'):
            stations=[{g['station_id'] for g in p['groups'] if g['mode']==mode} for p in results]
            self.assertTrue(all(stations))
            self.assertTrue(stations[0].isdisjoint(stations[1]))
        adopted=self.station_batch(days,results)
        self.assertEqual(adopted.status_code,200,adopted.json)
        self.cur.execute("SELECT DISTINCT scheduled_date::text AS day FROM inspection_schedule_tasks WHERE status='pending' ORDER BY day")
        self.assertEqual([r['day'] for r in self.cur.fetchall()],days)
        # Replacing both saved dates projects out both old plans; the same scheme is reproducible.
        again=self.station_batch(days,quota_revision=1)
        self.assertEqual(again.status_code,200,again.json)
        signature=lambda data:[[(g['mode'],g['station_id'],g['inspector_ids']) for g in p['groups']] for p in data]
        self.assertEqual(signature(again.json['results']),signature(results))
        self.assertEqual(self.station_batch(days,again.json['results'],quota_revision=1).status_code,200)

    def test_stale_second_date_rejects_whole_station_batch_and_injected_failure_rolls_back(self):
        days=['2026-10-20','2026-10-21'];self.prepare(*days,more_stations=True)
        self.assertEqual(self.team_apply(self.team_preview(days)).status_code,200)
        previews=self.station_batch(days).json['results']
        self.availability(name='陈中磊',day=days[1],available=False)
        before=self.snapshot()
        self.assertEqual(self.station_batch(days,previews).status_code,409)
        self.assertEqual(self.snapshot(),before)
        previews=self.station_batch(days).json['results']
        from schedule_smart import apply_smart_plan
        def fail_second(cur,actor,result,periods,day):
            count=apply_smart_plan(cur,actor,result,periods,day)
            if day==date(2026,10,21): raise RuntimeError('isolated injected failure after second write')
            return count
        with patch('schedule_batch.apply_smart_plan',side_effect=fail_second),self.assertLogs(level='ERROR'):
            result=self.station_batch(days,previews)
        self.assertEqual(result.status_code,500,result.json)
        self.assertEqual(self.snapshot(),before)

    def test_cross_month_quarter_projection_and_shelf_capacity_are_date_scoped(self):
        days=['2026-12-31','2027-01-04'];self.prepare(*days,more_stations=True)
        # This isolated fixture explicitly publishes these days; unknown real calendars remain denied.
        self.cur.execute("DELETE FROM quality_work_calendar WHERE day='2027-01-04'")
        self.cur.execute("INSERT INTO quality_work_calendar(day,working,source) VALUES('2027-01-04',true,'test')")
        self.admin.commit()
        self.assertEqual(self.team_apply(self.team_preview(days)).status_code,200)
        response=self.station_batch(days)
        self.assertEqual(response.status_code,200,response.json)
        results=response.json['results']
        self.assertEqual([p['quarter'] for p in results],['2026年第4季度','2027年第1季度'])
        for mode in ('offline','online'):
            first={g['station_id'] for g in results[0]['groups'] if g['mode']==mode}
            second={g['station_id'] for g in results[1]['groups'] if g['mode']==mode}
            self.assertTrue(first & second,'new period can cover stations again')
        applied=self.station_batch(days,results)
        self.assertEqual(applied.status_code,200,applied.json)
        self.cur.execute("SELECT DISTINCT year,period_number FROM inspection_schedule_cells WHERE mode='online' ORDER BY year,period_number")
        self.assertEqual([(r['year'],r['period_number']) for r in self.cur.fetchall()],[(2026,12),(2027,1)])

    def test_concurrent_batch_adoption_only_one_snapshot_commits(self):
        days=['2026-10-20','2026-10-21'];self.prepare(*days)
        previews=self.team_preview(days)
        body=dict(action='apply',plans=[dict(day=p['day'],revision=p['revision'],source='generated',
                  manager_modes=p['manager_modes'],seed=p['seed'],token=p['token']) for p in previews])
        with ThreadPoolExecutor(max_workers=2) as pool:
            codes=list(pool.map(lambda _:self.client.application.test_client().post('/api/staff-availability/today-inspection',json=body).status_code,range(2)))
        self.assertEqual(sorted(codes),[200,409])
        self.cur.execute('SELECT COUNT(*) AS n FROM staff_daily_team_events')
        self.assertEqual(self.cur.fetchone()['n'],2)

    def test_future_manual_dispatch_uses_card_date_and_separate_daily_capacity(self):
        days=['2026-10-20','2026-10-21'];self.prepare(*days,more_stations=True)
        self.assertEqual(self.team_apply(self.team_preview(days)).status_code,200)
        query=dict(mode='online',year=2026,month=10)
        cards=[c for c in self.board('online')['shelf'] if c['ids']==[6]]
        self.assertEqual([(c['day'],c['remaining']) for c in cards],[(days[0],3),(days[1],3)])
        first=cards[0]
        for sid in (1,2,5):
            board=self.board('online');row=next(r for r in board['rows'] if r['station_id']==sid)
            response=self.client.post('/api/inspection-schedule/dispatch',json=dict(query,action='place',
                shelf_id=first['id'],revision=first['revision'],cells=[dict(station_id=sid,column_key=k,revision=c['revision']) for k,c in row['cells'].items()]))
            self.assertEqual(response.status_code,200,response.json)
            self.cur.execute('SELECT revision FROM inspection_schedule_shelf WHERE id=%s',(first['id'],))
            first['revision']=self.cur.fetchone()['revision']
        cards=[c for c in self.board('online')['shelf'] if c['ids']==[6]]
        self.assertEqual([(c['day'],c['remaining']) for c in cards],[(days[1],3)])
        row=next(r for r in self.board('online')['rows'] if r['station_id']==1)
        self.assertTrue(all(c['scheduled_date']==days[0] for c in row['cells'].values()))
        parked=self.client.post('/api/inspection-schedule/dispatch',json=dict(query,action='park',cells=[
            dict(station_id=1,column_key=k,revision=c['revision']) for k,c in row['cells'].items()]))
        self.assertEqual(parked.status_code,200,parked.json)
        cards=[c for c in parked.json['board']['shelf'] if c['ids']==[6]]
        self.assertEqual([(c['day'],c['remaining']) for c in cards],[(days[0],1),(days[1],3)])
        from schedule_shelf_store import expire_shelf
        with patch('schedule_shelf_store.today',return_value=date(2026,10,21)):
            expire_shelf(self.cur)
        self.admin.commit()
        self.cur.execute("SELECT DISTINCT scheduled_date::text AS day FROM inspection_schedule_shelf WHERE status='waiting'")
        self.assertEqual({r['day'] for r in self.cur.fetchall()},{days[1]})

    def test_monthly_metering_reservations_are_shared_by_selected_days_and_recomputed_on_replacement(self):
        days=['2026-10-20','2026-10-21'];self.prepare(*days,more_stations=True)
        saved=self.team_apply(self.team_preview(days));self.assertEqual(saved.status_code,200,saved.json)
        plan=self.client.put('/api/inspection-schedule/metering-plan',json=dict(year=2026,month=10,revision=0,quotas={'10':{'松金':3}}))
        self.assertEqual(plan.status_code,200,plan.json)
        preview=self.station_batch(days)
        self.assertEqual(preview.status_code,200,preview.json)
        results=preview.json['results']
        self.assertEqual([sum(bool(g.get('metering_cells')) for g in p['groups']) for p in results],[2,1])
        adopted=self.station_batch(days,results);self.assertEqual(adopted.status_code,200,adopted.json)
        again=self.station_batch(days,quota_revision=1)
        self.assertEqual(again.status_code,200,again.json)
        self.assertEqual([sum(bool(g.get('metering_cells')) for g in p['groups']) for p in again.json['results']],[2,1])

    def test_concurrent_station_batch_confirms_only_once_and_driver_change_invalidates_entire_batch(self):
        days=['2026-10-20','2026-10-21'];self.prepare(*days,more_stations=True)
        self.assertEqual(self.team_apply(self.team_preview(days)).status_code,200)
        previews=self.station_batch(days).json['results']
        before=self.snapshot()
        self.cur.execute('UPDATE users SET has_driving_permit=false');self.admin.commit()
        self.assertEqual(self.station_batch(days,previews).status_code,409)
        self.assertEqual(self.snapshot(),before)
        self.cur.execute('UPDATE users SET has_driving_permit=true WHERE id IN (2,3)');self.admin.commit()
        previews=self.station_batch(days).json['results']
        body=dict(action='confirm',dates=days,offline_count=1,online_count=1,quota_revision=0,
                  replace_confirmed=True,tokens={p['day']:p['token'] for p in previews})
        with ThreadPoolExecutor(max_workers=2) as pool:
            codes=list(pool.map(lambda _:self.client.application.test_client().post('/api/inspection-schedule/auto/batch',json=body).status_code,range(2)))
        self.assertEqual(sorted(codes),[200,409])
