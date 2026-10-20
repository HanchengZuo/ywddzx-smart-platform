"""Daily grouping and manual history tests; PostgreSQL is isolated by schema."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch
from flask import Flask
from staff_daily_teams import adjust_preview, random_teams
from staff_daily_team_http import excluded_reason, register_staff_daily_teams
from tests import test_staff_scheduling as staff_tests
from staff_availability import EDIT, VIEW, STAFF


class DailyTeamAlgorithmTests(unittest.TestCase):
    def people(self, students=18):
        managers = [dict(id=i+1, display_name=name, position='管理人员') for i, name in enumerate(['吕泽昆', '韩叙', '芦斌'])]
        return managers + [dict(id=i+10, display_name=f'学生{i}', position='大学生') for i in range(students)]

    def test_random_split_and_leader_sizes_are_balanced_and_reproducible(self):
        people = self.people()
        assignments = random_teams(people, {'1':'offline', '2':'offline', '3':'online'}, 'same-seed')
        self.assertEqual(assignments, random_teams(people, {'1':'offline', '2':'offline', '3':'online'}, 'same-seed'))
        students = [p for p in assignments if p['position'] == '大学生']
        self.assertEqual(sum(p['mode'] == 'offline' for p in students), 9)
        self.assertEqual(len({p['id'] for p in assignments}), 21)
        counts = [sum(p['leader_id'] == uid for p in students) for uid in (1,2)]
        self.assertEqual(sorted(counts), [4,5])
        self.assertTrue(all(p['group_name'] == '外勤吕泽昆组' for p in assignments if p['leader_id'] == 1))
        variants = {tuple(p['id'] for p in random_teams(people, {'1':'offline', '2':'offline', '3':'online'}, str(seed)) if p['mode']=='offline') for seed in range(10)}
        self.assertGreater(len(variants), 1)

    def test_odd_counts_no_leader_constraints_and_missing_choices(self):
        result = random_teams(self.people(5), {'1':'offline', '2':'offline', '3':'online'}, 'odd')
        self.assertIn(sum(p['mode']=='offline' for p in result if p['position']=='大学生'), (2,3))
        result = random_teams(self.people(), {'1':'online','2':'online','3':'online'}, 'video')
        self.assertTrue(all(p['mode'] == 'online' and p['leader_id'] is None for p in result))
        with self.assertRaises(ValueError): random_teams(self.people(), {}, 'missing')
        with self.assertRaises(ValueError): random_teams(self.people(), {'1':'no','2':'offline','3':'online'}, 'invalid')
        people = self.people(5)
        people[3]['station_modes'] = ['offline']
        with self.assertRaises(ValueError): random_teams(people, {'1':'online','2':'online','3':'online'}, 'leader')
        result = random_teams(people, {'1':'offline','2':'offline','3':'online'}, 'fixed')
        self.assertEqual(next(p for p in result if p['id']==10)['mode'], 'offline')

    def test_no_authentication_never_opens_database(self):
        app=Flask(__name__); connect=MagicMock()
        register_staff_daily_teams(app, connect=connect, has_permission=lambda *_:True)
        self.assertEqual(app.test_client().get('/api/staff-availability/today-inspection').status_code,401)
        self.assertEqual(app.test_client().post('/api/staff-availability/today-inspection').status_code,401)
        connect.assert_not_called()

    def test_excluded_reasons_distinguish_busy_unknown_and_account_binding(self):
        person = dict(id=1, available=False, reason='')
        self.assertEqual(excluded_reason(person), '没空')
        self.assertEqual(excluded_reason({**person,'reason':'培训'}), '没空（培训）')
        self.assertEqual(excluded_reason({**person,'available':None}), '未确认有空或没空')
        self.assertEqual(excluded_reason({**person,'id':None,'available':True}), '账号未唯一匹配')
        self.assertEqual(excluded_reason({**person,'id':None}), '没空；账号未唯一匹配')

    def test_preview_choices_only_move_students_to_existing_field_leaders_or_video(self):
        people = [dict(p,available=True) for p in self.people(4)]
        base = random_teams(people,{'1':'offline','2':'offline','3':'online'},'preview')
        student = next(p for p in base if p['position']=='大学生' and p['mode']=='offline')
        target = 1 if student['leader_id']!=1 else 2
        adjusted = adjust_preview(people,base,{str(student['id']):target})
        self.assertEqual(next(p for p in adjusted if p['id']==student['id'])['leader_id'],target)
        video = adjust_preview(people,adjusted,{str(student['id']):None})
        self.assertEqual(next(p for p in video if p['id']==student['id'])['mode'],'online')
        self.assertEqual({p['id'] for p in adjusted},{p['id'] for p in base})
        self.assertEqual(next(p for p in base if p['id']==student['id'])['leader_id'],student['leader_id'])
        for bad in (None,[],{str(student['id']):True},{'1':2},{str(student['id']):3},{str(student['id']):999},{'0'+str(student['id']):2}):
            with self.assertRaises(ValueError): adjust_preview(people,base,bad)


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST') == '1', 'isolated database opt-in')
class DailyTeamDatabaseTests(unittest.TestCase):
    setUp_base=staff_tests.StaffDatabaseTests.setUp_base
    connect=staff_tests.StaffDatabaseTests.connect
    tearDown=staff_tests.StaffDatabaseTests.tearDown
    availability=staff_tests.StaffDatabaseTests.availability
    record=staff_tests.StaffDatabaseTests.record
    save=staff_tests.StaffDatabaseTests.save

    def setUp(self):
        staff_tests.StaffDatabaseTests.setUp(self)
        self.cur.execute('DELETE FROM staff_daily_teams'); self.admin.commit()
        register_staff_daily_teams(self.client.application, connect=self.connect, has_permission=lambda _, actor,key:key in self.permissions)
        self.cur.execute("INSERT INTO users VALUES(6,'lu','芦斌','supervisor_manager','active')")
        names=['陈中磊','程镇林','葛心玉','侯明敖','姜傲云','吕雪儿','彭思宇','束紫荆']
        for uid,name in enumerate(names,10):
            self.cur.execute("INSERT INTO users VALUES(%s,%s,%s,'supervisor','active')", (uid,f'student{uid}',name))
        self.admin.commit()
        for name in ['步雪琼','孔德辰','芦斌',*names]:
            self.assertEqual(self.availability(name=name).status_code,200)
        for name, _ in STAFF:
            if name not in ['步雪琼','孔德辰','芦斌',*names]:
                self.assertEqual(self.availability(name=name, available=False).status_code,200)
        self.body=dict(day='2026-10-19',revision=0,manager_modes={'2':'offline','3':'offline','6':'online'})

    def post(self, action='preview', **extra):
        return self.client.post('/api/staff-availability/today-inspection',json={**self.body,'action':action,**extra})

    def confirm(self):
        preview=self.post(); self.assertEqual(preview.status_code,200,preview.json)
        result=self.post('confirm',token=preview.json['token'],seed=preview.json['seed'])
        self.assertEqual(result.status_code,200,result.json)
        return result

    def test_shared_save_cancel_audit_idempotence_and_station_auto_keeps_teams_together(self):
        preview=self.post().json
        self.cur.execute('SELECT count(*) AS n FROM staff_daily_teams'); self.assertEqual(self.cur.fetchone()['n'],0)
        result=self.confirm()
        self.assertEqual(len(result.json['groups']),3)
        self.assertEqual(self.post('confirm',token=preview['token'],seed=preview['seed']).status_code,409)
        board=self.client.get('/api/staff-availability?week=2026-10-19').json
        self.assertEqual(board['people'][0]['cells']['2026-10-19']['daily_assignment']['group_name'],'外勤步雪琼组')
        auto=self.client.post('/api/inspection-schedule/auto',json=dict(action='preview',day='2026-10-19')).json
        group=next(g for g in auto['groups'] if g.get('group_name')=='外勤步雪琼组')
        expected=next(g for g in result.json['groups'] if g['name']=='外勤步雪琼组')
        self.assertEqual(set(group['inspector_ids']),{p['id'] for p in expected['members']})
        self.assertEqual(self.availability(available=False).status_code,409)
        response=self.post('cancel',revision=1)
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(self.availability(available=False).status_code,200)
        self.cur.execute('SELECT actor_id,after_value FROM staff_daily_team_events ORDER BY id')
        rows=self.cur.fetchall(); self.assertEqual(len(rows),2); self.assertEqual(rows[-1]['after_value'],[]); self.assertEqual(rows[-1]['actor_id'],2)

    def test_permissions_date_and_context_changes_block_confirmation(self):
        self.permissions.discard(EDIT)
        self.assertEqual(self.post().status_code,403)
        self.assertEqual(self.client.get('/api/staff-availability/today-inspection').status_code,200)
        self.permissions.discard(VIEW)
        self.assertEqual(self.client.get('/api/staff-availability/today-inspection').status_code,403)
        self.permissions.update({VIEW,EDIT})
        self.assertEqual(self.post(day='2026-10-20').status_code,409)
        self.assertEqual(self.post(manager_modes={}).status_code,400)
        preview=self.post().json
        self.availability(name='陈中磊',available=False,reason='出差')
        self.assertEqual(self.post('confirm',token=preview['token'],seed=preview['seed']).status_code,409)
        self.cur.execute('SELECT 1 FROM staff_daily_teams'); self.assertIsNone(self.cur.fetchone())
        with patch('staff_daily_team_http.today',return_value=date(2026,10,20)):
            self.assertEqual(self.post('confirm',token=preview['token'],seed=preview['seed']).status_code,409)

    def test_audit_failure_rolls_back_entire_plan(self):
        preview=self.post().json
        self.cur.execute('ALTER TABLE staff_daily_team_events ADD CHECK(false) NOT VALID'); self.admin.commit()
        with self.assertLogs(level='ERROR'):
            result=self.post('confirm',token=preview['token'],seed=preview['seed'])
        self.assertEqual(result.status_code,500)
        self.cur.execute('SELECT 1 FROM staff_daily_teams'); self.assertIsNone(self.cur.fetchone())

    def test_all_people_must_confirm_and_confirmation_rechecks_unknown(self):
        context = self.client.get('/api/staff-availability/today-inspection').json
        self.assertEqual((context['confirmed_count'], context['total_count']), (25, 25))
        preview = self.post().json
        self.cur.execute("DELETE FROM staff_availability WHERE person_name='韩叙' AND day='2026-10-19'")
        self.admin.commit()
        context = self.client.get('/api/staff-availability/today-inspection').json
        self.assertEqual(context['unconfirmed'], ['韩叙'])
        self.assertEqual(context['confirmed_count'], 24)
        self.assertEqual(self.post().status_code, 409)
        response = self.post('confirm', token=preview['token'], seed=preview['seed'])
        self.assertEqual(response.status_code, 409)
        self.assertIn('韩叙', response.json['error'])
        self.cur.execute('SELECT 1 FROM staff_daily_teams'); self.assertIsNone(self.cur.fetchone())

    def test_preview_adjustments_save_only_on_confirm_and_retain_server_owned_participants(self):
        preview = self.post().json
        student = next(p for group in preview['groups'] if group['mode']=='offline' for p in group['members'] if p['position']=='大学生')
        leader = 2 if student['leader_id']!=2 else 3
        self.cur.execute('SELECT 1 FROM staff_daily_teams'); self.assertIsNone(self.cur.fetchone())
        payload = dict(seed=preview['seed'],token=preview['token'])
        for choices in ({'2':None},{str(student['id']):6},{str(student['id']):True},[],'invalid'):
            self.assertEqual(self.post('confirm',**payload,student_leaders=choices).status_code,400)
        self.cur.execute('SELECT 1 FROM staff_daily_teams'); self.assertIsNone(self.cur.fetchone())
        result = self.post('confirm',**payload,student_leaders={str(student['id']):leader},user_id=1)
        self.assertEqual(result.status_code,200,result.json)
        actual = [p for group in result.json['groups'] for p in group['members']]
        self.assertEqual(next(p for p in actual if p['id']==student['id'])['leader_id'],leader)
        expected_ids = {p['id'] for group in preview['groups'] for p in group['members']}
        self.assertEqual({p['id'] for p in actual},expected_ids)
        self.cur.execute('SELECT actor_id,after_value FROM staff_daily_team_events')
        event = self.cur.fetchone()
        self.assertEqual(event['actor_id'],2)
        self.assertEqual({p['id'] for p in event['after_value']},expected_ids)
        self.assertEqual(self.post('confirm',**payload,student_leaders={str(student['id']):None}).status_code,409)

    def test_adjusted_preview_still_rechecks_availability_and_rolls_back_on_audit_failure(self):
        preview = self.post().json
        student = next(p for group in preview['groups'] for p in group['members'] if p['position']=='大学生')
        payload = dict(seed=preview['seed'],token=preview['token'],student_leaders={str(student['id']):None})
        self.cur.execute('ALTER TABLE staff_daily_team_events ADD CHECK(false) NOT VALID'); self.admin.commit()
        with self.assertLogs(level='ERROR'):
            self.assertEqual(self.post('confirm',**payload).status_code,500)
        self.cur.execute('SELECT 1 FROM staff_daily_teams'); self.assertIsNone(self.cur.fetchone())
        self.availability(name=student['display_name'],available=False)
        self.assertEqual(self.post('confirm',**payload).status_code,409)

    def test_excluded_busy_label_is_returned_without_misleading_unconfirmed_wording(self):
        self.availability(name='步雪琼',available=False)
        self.availability(name='孔德辰',available=False,reason='出差')
        response = self.client.get('/api/staff-availability/today-inspection')
        people = {p['name']:p['reason'] for p in response.json['excluded']}
        self.assertEqual(people['步雪琼'],'没空')
        self.assertEqual(people['孔德辰'],'没空（出差）')

    def test_concurrent_confirmations_only_commit_once(self):
        preview=self.post().json
        body={**self.body,'action':'confirm','token':preview['token'],'seed':preview['seed']}
        def confirm_once():
            return self.client.application.test_client().post('/api/staff-availability/today-inspection',json=body).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses=list(pool.map(lambda _:confirm_once(), range(2)))
        self.assertEqual(sorted(statuses),[200,409])
        self.cur.execute('SELECT count(*) AS n FROM staff_daily_team_events'); self.assertEqual(self.cur.fetchone()['n'],1)

    def test_station_confirmation_dispatches_saved_teams_together(self):
        saved=self.confirm().json
        auto=self.client.post('/api/inspection-schedule/auto',json=dict(action='preview',day='2026-10-19')).json
        result=self.client.post('/api/inspection-schedule/auto',json=dict(action='confirm',day='2026-10-19',token=auto['token']))
        self.assertEqual(result.status_code,200,result.json)
        for group in auto['groups']:
            expected=next(g for g in saved['groups'] if g['name']==group['group_name']) if group['mode']=='offline' else dict(members=[group['person']])
            self.cur.execute('SELECT inspector_ids FROM inspection_schedule_cells WHERE station_id=%s AND mode=%s', (group['station_id'],group['mode']))
            self.assertTrue(all(set(r['inspector_ids'])=={p['id'] for p in expected['members']} for r in self.cur.fetchall()))

    def test_unavailable_team_member_never_causes_partial_or_unled_station_dispatch(self):
        saved=self.confirm().json
        affected=next(g for g in saved['groups'] if any(p['id']==10 for p in g['members']))
        self.cur.execute("UPDATE users SET account_status='disabled' WHERE id=10"); self.admin.commit()
        response=self.client.post('/api/inspection-schedule/auto',json=dict(action='preview',day='2026-10-19'))
        self.assertEqual(response.status_code,200,response.json)
        self.assertNotIn(affected['name'],[g.get('group_name') for g in response.json['groups']])

    def test_history_override_is_versioned_and_never_changes_original_records(self):
        record=self.record(day='2026-10-16',inspector=2)
        response=self.availability(day='2026-10-16',history_status='online')
        self.assertEqual(response.status_code,200,response.json)
        cell=self.client.get('/api/staff-availability?week=2026-10-12').json['people'][0]['cells']['2026-10-16']
        self.assertEqual(cell['history_status'],'online'); self.assertEqual(cell['actual_modes'],[dict(mode='offline',count=1)])
        self.cur.execute('SELECT inspection_table_id FROM inspections WHERE id=%s',(record,)); self.assertEqual(self.cur.fetchone()['inspection_table_id'],1)
        self.assertEqual(self.availability(day='2026-10-16',history_status='busy',reason='培训').status_code,200)
        self.assertEqual(self.availability(day='2026-10-16',history_status='auto').status_code,200)
        self.assertEqual(self.availability(history_status='online').status_code,400)
        self.cur.execute('SELECT after_value FROM staff_availability_events WHERE day=%s ORDER BY id DESC LIMIT 1',('2026-10-16',))
        self.assertIsNone(self.cur.fetchone()['after_value']['history_status'])

    def test_idempotent_migration_preserves_records(self):
        sql=(Path(__file__).resolve().parents[1]/'db/init/525_staff_daily_teams.sql').read_text()
        self.confirm()
        self.cur.execute(sql); self.cur.execute(sql); self.admin.commit()
        self.cur.execute('SELECT revision FROM staff_daily_teams'); self.assertEqual(self.cur.fetchone()['revision'],1)
