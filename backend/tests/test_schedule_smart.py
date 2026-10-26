"""v10.6 smart replacement and dispatch-bound personnel, isolated PostgreSQL only."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from flask import Flask
from unittest.mock import MagicMock
from schedule_automation import register_schedule_automation
from tests import test_staff_daily_teams as teams


class AuthenticationTests(unittest.TestCase):
    def test_saved_today_auth_precedes_database(self):
        app=Flask(__name__);connect=MagicMock()
        register_schedule_automation(app,connect=connect,has_permission=lambda *_:True)
        self.assertEqual(app.test_client().get('/api/inspection-schedule/today').status_code,401)
        connect.assert_not_called()


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST')=='1','isolated database opt-in')
class SmartDatabaseTests(unittest.TestCase):
    setUp=teams.DailyTeamDatabaseTests.setUp
    setUp_base=teams.DailyTeamDatabaseTests.setUp_base
    connect=teams.DailyTeamDatabaseTests.connect
    tearDown=teams.DailyTeamDatabaseTests.tearDown
    post=teams.DailyTeamDatabaseTests.post
    confirm=teams.DailyTeamDatabaseTests.confirm
    availability=teams.DailyTeamDatabaseTests.availability
    record=teams.DailyTeamDatabaseTests.record
    save=teams.DailyTeamDatabaseTests.save

    def smart(self,action='preview',**extra):
        return self.client.post('/api/inspection-schedule/auto',json=dict(action=action,
            strategy='replace_today',day='2026-10-19',offline_count=2,online_count=3,**extra))

    def board(self,mode='offline'):
        return self.client.get('/api/inspection-schedule',query_string=dict(mode=mode,year=2026,**(
            dict(quarter=4) if mode=='offline' else dict(month=10) if mode=='online' else {}))).json

    def assign(self,group,sid=1,day='2026-10-19'):
        mode=group['mode']
        board=self.board(mode)
        row=next(r for r in board['rows'] if r['station_id']==sid)
        return self.client.put('/api/inspection-schedule',json=dict(mode=mode,year=2026,
            **(dict(quarter=4) if mode=='offline' else dict(month=10)),scheduled_date=day,
            inspector_ids=[p['id'] for p in group['members']] if mode=='offline' else [group['members'][0]['id']],
            cells=[dict(station_id=sid,column_key=k,revision=c['revision']) for k,c in row['cells'].items() if c['status'] in ('assigned','unassigned')]))

    def signature(self,result):
        return sorted((g['mode'],g['station_id'],tuple(sorted(g['inspector_ids'])),tuple(c['column_key'] for c in g['cells']),
            tuple(c['column_key'] for c in g.get('metering_cells',[]))) for g in result['groups'])

    def apply(self,preview):
        return self.smart('confirm',token=preview['token'],replace_confirmed=True)

    def test_smart_scheme_ignores_today_manual_intent_and_explicitly_replaces_it(self):
        saved=self.confirm().json
        base=self.smart().json
        self.assertTrue(base['groups'])
        field=[g for g in saved['groups'] if g['mode']=='offline']
        self.assertEqual(self.assign(field[1],sid=1).status_code,200)
        after=self.smart().json
        self.assertEqual(self.signature(after),self.signature(base))
        self.assertNotEqual(after['token'],base['token'],'unchanged station choices still recheck concurrent board edits')
        self.assertEqual(self.apply(base).status_code,409)
        self.assertEqual(self.smart('confirm',token=after['token']).status_code,400)
        old=self.board()['rows'][0]['cells']
        self.assertTrue(all(c['assignees'] for c in old.values()))
        applied=self.apply(after)
        self.assertEqual(applied.status_code,200,applied.json)
        self.assertGreater(applied.json['replaced_cell_count'],0)
        self.assertEqual(self.client.get('/api/staff-availability/today-inspection').json['revision'],1)
        again=self.smart().json
        self.assertEqual(self.signature(again),self.signature(base))
        self.assertTrue(self.client.get('/api/inspection-schedule/today').json['groups'])
        self.cur.execute("SELECT COUNT(*) AS n FROM inspection_schedule_tasks WHERE status='cancelled'")
        self.assertGreater(self.cur.fetchone()['n'],0)
        self.assertEqual(self.apply(again).status_code,200)
        self.cur.execute("SELECT mode,station_id,column_key,user_id,COUNT(*) AS n FROM inspection_schedule_tasks WHERE status='pending' GROUP BY 1,2,3,4 HAVING COUNT(*)>1")
        self.assertEqual(self.cur.fetchall(),[])

    def test_failure_after_old_plan_removal_rolls_back_cells_tasks_and_audit(self):
        saved=self.confirm().json
        group=next(g for g in saved['groups'] if g['mode']=='offline')
        self.assign(group)
        before=self.board()
        self.cur.execute('SELECT COUNT(*) AS n FROM inspection_schedule_events');events=self.cur.fetchone()['n']
        self.cur.execute("SELECT COUNT(*) AS n FROM inspection_schedule_tasks WHERE status='pending'");pending=self.cur.fetchone()['n']
        self.cur.execute("ALTER TABLE inspection_schedule_events ADD CHECK(after_ids='[]'::jsonb) NOT VALID");self.admin.commit()
        proposal=self.smart().json
        with self.assertLogs(level='ERROR'):
            result=self.apply(proposal)
        self.assertEqual(result.status_code,500,result.json)
        self.assertEqual(self.board()['rows'],before['rows'])
        self.cur.execute('SELECT COUNT(*) AS n FROM inspection_schedule_events');self.assertEqual(self.cur.fetchone()['n'],events)
        self.cur.execute("SELECT COUNT(*) AS n FROM inspection_schedule_tasks WHERE status='pending'");self.assertEqual(self.cur.fetchone()['n'],pending)

    def test_metering_monthly_priority_ignores_today_manual_reservation_and_links_both_boards(self):
        saved=self.confirm().json
        field=[g for g in saved['groups'] if g['mode']=='offline']
        self.cur.execute("UPDATE stations SET monitoring_status='未运行' WHERE id=1");self.admin.commit()
        plan=self.client.put('/api/inspection-schedule/metering-plan',json=dict(year=2026,month=10,revision=0,quotas={'10':{'松金':2}}))
        self.assertEqual(plan.status_code,200,plan.json)
        base=self.smart().json
        annual=self.board('annual')['rows'][0]
        assigned=self.client.put('/api/inspection-schedule',json=dict(mode='annual',year=2026,
            scheduled_date='2026-10-19',inspector_ids=[p['id'] for p in field[1]['members']],
            cells=[dict(station_id=1,column_key=k,revision=c['revision']) for k,c in annual['cells'].items() if c['status']=='unassigned']))
        self.assertEqual(assigned.status_code,200,assigned.json)
        proposal=self.smart().json
        self.assertEqual(self.signature(proposal),self.signature(base))
        region=next(r for r in proposal['metering_plan']['regions'] if r['region']=='松金')
        self.assertEqual((region['reserved'],region['proposed']),(0,2))
        applied=self.apply(proposal)
        self.assertEqual(applied.status_code,200,applied.json)
        current=self.board('annual')['rows'][0]
        self.assertTrue(all(c['status']=='assigned' for c in current['cells'].values()))
        self.assertTrue(all(c['status']=='assigned' for c in self.board()['rows'][0]['cells'].values()))

    def test_started_rows_are_protected_and_count_toward_group_daily_capacity(self):
        saved=self.confirm().json
        group=next(g for g in saved['groups'] if g['mode']=='offline')
        self.assign(group)
        self.record(station=1,table=1,inspector=group['leader_id'],day='2026-10-19')
        before=self.board()['rows'][0]
        proposal=self.smart().json
        proposed_for_group=[g for g in proposal['groups'] if g['mode']=='offline' and g['person']['id']==group['leader_id']]
        self.assertLessEqual(len(proposed_for_group),1,'one protected station already consumes one of two daily slots')
        self.assertTrue(all(g['station_id']!=1 for g in proposal['groups'] if g['mode']=='offline'))
        result=self.apply(proposal)
        self.assertEqual(result.status_code,200,result.json)
        self.assertEqual(self.board()['rows'][0],before)

    def test_future_plans_and_history_are_not_removed(self):
        saved=self.confirm().json
        field=next(g for g in saved['groups'] if g['mode']=='offline')
        self.cur.execute("INSERT INTO staff_daily_teams(day,assignments,revision,updated_by) SELECT '2026-10-20',assignments,1,1 FROM staff_daily_teams WHERE day='2026-10-19'")
        self.cur.execute("INSERT INTO staff_availability(person_name,day,available,revision,updated_by) SELECT person_name,'2026-10-20',available,1,1 FROM staff_availability WHERE day='2026-10-19' ON CONFLICT DO NOTHING")
        self.admin.commit()
        self.assertEqual(self.assign(field,sid=3,day='2026-10-20').status_code,200)
        before=next(r for r in self.board()['rows'] if r['station_id']==3)
        proposal=self.smart().json
        self.assertTrue(all(g['station_id']!=3 for g in proposal['groups'] if g['mode']=='offline'))
        self.assertEqual(self.apply(proposal).status_code,200)
        self.assertEqual(next(r for r in self.board()['rows'] if r['station_id']==3),before)

    def test_smart_plan_requires_saved_personnel_and_new_get_is_view_only(self):
        self.assertEqual(self.smart().json['groups'],[])
        self.confirm()
        self.permissions.discard('edit_inspection_schedule')
        response=self.client.get('/api/inspection-schedule/today')
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(response.headers['Cache-Control'],'private, no-store')
        self.assertEqual(self.smart().status_code,403)
        self.permissions.discard('view_inspection_schedule')
        self.assertEqual(self.client.get('/api/inspection-schedule/today').status_code,403)

    def test_concurrent_replacements_only_one_old_snapshot_can_commit(self):
        self.confirm()
        proposal=self.smart().json
        body=dict(action='confirm',strategy='replace_today',replace_confirmed=True,day='2026-10-19',offline_count=2,online_count=3,token=proposal['token'])
        with ThreadPoolExecutor(max_workers=2) as pool:
            codes=list(pool.map(lambda _:self.client.application.test_client().post('/api/inspection-schedule/auto',json=body).status_code,range(2)))
        self.assertEqual(sorted(codes),[200,409])

    def test_dispatched_field_members_can_change_until_a_member_registers_at_the_assigned_station(self):
        saved=self.confirm().json
        field=[g for g in saved['groups'] if g['mode']=='offline']
        student=next(p for p in field[0]['members'] if p['position']=='大学生')
        other=next(p for p in field[1]['members'] if p['position']=='大学生')
        self.assign(field[0])
        self.assertEqual(self.post('move',revision=1,student_id=student['id'],leader_id=field[1]['leader_id']).status_code,200)
        self.assertEqual(self.post('move',revision=2,student_id=other['id'],leader_id=field[0]['leader_id']).status_code,200)
        self.admin.commit()
        self.record(station=1,table=1,inspector=field[0]['leader_id'],day='2026-10-19')
        context=self.client.get('/api/staff-availability/today-inspection').json
        locked=next(g for g in context['groups'] if g['leader_id']==field[0]['leader_id'])
        self.assertTrue(locked['dispatch_locked']);self.assertTrue(all(p['dispatch_locked'] for p in locked['members']))
        self.assertEqual(self.post('move',revision=3,student_id=other['id'],leader_id=field[1]['leader_id']).status_code,409)

    def test_video_locks_individual_not_whole_video_pool(self):
        saved=self.confirm().json
        video=next(g for g in saved['groups'] if g['mode']=='online')
        students=[p for p in video['members'] if p['position']=='大学生']
        selected=students[0];other=students[1]
        self.assertEqual(self.assign(dict(video,members=[selected])).status_code,200)
        leader=next(g['leader_id'] for g in saved['groups'] if g['mode']=='offline')
        self.assertEqual(self.post('move',revision=1,student_id=selected['id'],leader_id=leader).status_code,409)
        self.assertEqual(self.post('move',revision=1,student_id=other['id'],leader_id=leader).status_code,200)
