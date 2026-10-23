"""v10.8 proposal adoption, safe leader moves and atomic busy cascades."""
import os
import json
import unittest
from concurrent.futures import ThreadPoolExecutor

from tests import test_staff_daily_teams as teams
from tests import test_schedule_smart as smart
from staff_daily_teams import adjust_members, move_member, propose_teams


class ProposalAlgorithmTests(unittest.TestCase):
    def test_manager_dissolves_field_group_and_can_restore_own_team_never_join_another(self):
        people=[dict(p,available=True) for p in teams.DailyTeamAlgorithmTests().people(6)]
        base=propose_teams(people,[],{'1':'offline','2':'offline','3':'online'},'preview')
        children={p['id'] for p in base if p['leader_id']==1 and p['id']!=1}
        changed=move_member(people,base,1,None)
        self.assertTrue(all(p['mode']=='online' for p in changed if p['id'] in children|{1}))
        self.assertTrue(any(p['leader_id']==1 for p in base), 'input is immutable')
        restored=move_member(people,changed,1,1)
        self.assertEqual([p['id'] for p in restored if p['leader_id']==1],[1])
        with self.assertRaisesRegex(ValueError,'一位管理人员'): move_member(people,base,1,2)
        for bad in (None,{},[{'person_id':True,'leader_id':None}],[{'person_id':1,'leader_id':None,'name':'fake'}]):
            with self.assertRaises(ValueError): adjust_members(people,base,bad)


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST')=='1','isolated database opt-in')
class ProposalDatabaseTests(unittest.TestCase):
    setUp=teams.DailyTeamDatabaseTests.setUp
    setUp_base=teams.DailyTeamDatabaseTests.setUp_base
    connect=teams.DailyTeamDatabaseTests.connect
    tearDown=teams.DailyTeamDatabaseTests.tearDown
    availability=teams.DailyTeamDatabaseTests.availability
    record=teams.DailyTeamDatabaseTests.record
    save=teams.DailyTeamDatabaseTests.save
    post=teams.DailyTeamDatabaseTests.post
    confirm=teams.DailyTeamDatabaseTests.confirm
    board=smart.SmartDatabaseTests.board
    assign=smart.SmartDatabaseTests.assign

    def current(self):
        result=self.client.get('/api/staff-availability/today-inspection')
        self.assertEqual(result.status_code,200,result.json)
        return result.json

    def adopt(self, snapshot, moves=None, **extra):
        return self.client.post('/api/staff-availability/today-inspection',json=dict(
            action='apply',source='current',day=snapshot['day'],revision=snapshot['revision'],
            token=snapshot['current_token'],moves=moves or [],**extra))

    def test_generated_and_current_drafts_only_write_on_explicit_adoption(self):
        generated=self.post().json
        self.cur.execute('SELECT count(*) AS n FROM staff_daily_teams')
        self.assertEqual(self.cur.fetchone()['n'],0)
        result=self.post('apply',source='generated',seed=generated['seed'],token=generated['token'],
                         moves=[dict(person_id=2,leader_id=None)])
        self.assertEqual(result.status_code,200,result.json)
        current=self.current()
        self.assertFalse(any(g['leader_id']==2 for g in current['groups']))
        student=next(p for g in current['groups'] if g['mode']=='online' for p in g['members'] if p['position']=='大学生')
        result=self.adopt(current,[dict(person_id=student['id'],leader_id=3)])
        self.assertEqual(result.status_code,200,result.json)
        latest=self.current()
        self.assertEqual(latest['revision'],2)
        self.assertIn(student['id'],[p['id'] for g in latest['groups'] if g['leader_id']==3 for p in g['members']])
        self.assertEqual(self.adopt(current).status_code,409)
        self.cur.execute('SELECT count(*) AS n FROM staff_daily_team_events')
        self.assertEqual(self.cur.fetchone()['n'],2)

    def test_regeneration_preserves_dispatched_groups_and_unlocked_people_remain_editable(self):
        saved=self.confirm().json
        field=next(g for g in saved['groups'] if g['leader_id']==2)
        self.assertEqual(self.assign(field).status_code,200)
        generated=self.post(revision=1).json
        locked=next(g for g in generated['groups'] if g['leader_id']==2)
        self.assertEqual({p['id'] for p in locked['members']},{p['id'] for p in field['members']})
        self.assertTrue(locked['dispatch_locked'])
        adopted=self.post('apply',revision=1,source='generated',seed=generated['seed'],token=generated['token'])
        self.assertEqual(adopted.status_code,200,adopted.json)
        current=self.current()
        self.assertEqual(self.adopt(current,[dict(person_id=2,leader_id=None)]).status_code,409)
        outsider=next(p for g in current['groups'] if g['mode']=='online' for p in g['members'] if p['position']=='大学生')
        self.assertEqual(self.adopt(current,[dict(person_id=outsider['id'],leader_id=2)]).status_code,409)
        self.assertEqual(self.post(revision=2,manager_modes={'2':'online','3':'offline','6':'online'}).status_code,409)

    def test_busy_leader_dissolves_group_and_retires_parked_cards_without_touching_records(self):
        saved=self.confirm().json
        snapshot=self.current()
        field=next(g for g in saved['groups'] if g['leader_id']==2)
        ids={p['id'] for p in field['members']}
        self.cur.execute("INSERT INTO inspection_schedule_shelf(mode,scheduled_date,inspector_ids,name,source_column_key,source_station_name) VALUES('offline','2026-10-19',%s,'旧组','financial','测试站')",
                         (json.dumps(sorted(ids)),))
        self.admin.commit()
        self.assertEqual(self.availability(available=False,reason='培训').status_code,200)
        current=self.current()
        self.assertFalse(any(g['leader_id']==2 for g in current['groups']))
        video={p['id'] for g in current['groups'] if g['mode']=='online' for p in g['members']}
        self.assertTrue(ids-{2} <= video)
        self.assertNotIn(2,video)
        self.cur.execute("SELECT inspector_ids FROM inspection_schedule_shelf WHERE status='waiting' AND scheduled_date='2026-10-19'")
        waiting=self.cur.fetchall()
        self.assertTrue(all(2 not in r['inspector_ids'] for r in waiting))
        for uid in ids-{2}:
            self.assertTrue(any(r['inspector_ids']==[uid] for r in waiting))
        self.cur.execute('SELECT count(*) AS n FROM inspections');self.assertEqual(self.cur.fetchone()['n'],0)
        self.assertEqual(self.adopt(snapshot).status_code,409)

    def test_busy_student_or_video_manager_is_removed_and_other_teams_unchanged(self):
        self.confirm()
        before=self.current()
        student=next(p for g in before['groups'] if g['mode']=='offline' for p in g['members'] if p['position']=='大学生')
        self.assertEqual(self.availability(name=student['display_name'],available=False).status_code,200)
        self.assertEqual(self.availability(name='芦斌',available=False,reason='请假').status_code,200)
        after=self.current()
        remaining={p['id']:p for g in after['groups'] for p in g['members']}
        self.assertNotIn(student['id'],remaining);self.assertNotIn(6,remaining)
        self.assertTrue(all(remaining[p['id']]['mode']==p['mode'] for g in before['groups'] for p in g['members'] if p['id'] in remaining))

    def test_any_dispatched_field_member_or_video_person_cannot_be_marked_busy(self):
        saved=self.confirm().json
        field=next(g for g in saved['groups'] if g['leader_id']==2)
        self.assertEqual(self.assign(field).status_code,200)
        for p in field['members']:
            self.assertEqual(self.availability(name=p['display_name'],available=False).status_code,409)
        video=next(g for g in saved['groups'] if g['mode']=='online')
        selected=next(p for p in video['members'] if p['position']=='大学生')
        self.assertEqual(self.assign(dict(video,members=[selected]),sid=2).status_code,200)
        self.assertEqual(self.availability(name=selected['display_name'],available=False).status_code,409)
        self.assertEqual(self.availability(name='芦斌',available=False).status_code,200)

    def test_busy_cascade_and_adoption_roll_back_when_any_audit_write_fails(self):
        self.confirm();snapshot=self.current()
        self.cur.execute('SELECT id,status FROM inspection_schedule_shelf ORDER BY id')
        shelf_before=[dict(r) for r in self.cur.fetchall()]
        self.cur.execute('ALTER TABLE staff_availability_events ADD CHECK(false) NOT VALID');self.admin.commit()
        with self.assertLogs(level='ERROR'):
            self.assertEqual(self.availability(available=False).status_code,500)
        current=self.current();self.assertEqual(current['revision'],snapshot['revision'])
        self.assertEqual(current['groups'],snapshot['groups'])
        self.cur.execute('SELECT id,status FROM inspection_schedule_shelf ORDER BY id')
        self.assertEqual([dict(r) for r in self.cur.fetchall()],shelf_before)
        self.cur.execute('ALTER TABLE staff_daily_team_events ADD CHECK(false) NOT VALID');self.admin.commit()
        with self.assertLogs(level='ERROR'):
            self.assertEqual(self.adopt(current,[dict(person_id=2,leader_id=None)]).status_code,500)
        self.assertEqual(self.current()['groups'],snapshot['groups'])

    def test_concurrent_adoptions_only_one_commits_and_permissions_are_unchanged(self):
        self.confirm();snapshot=self.current()
        def once(_):
            return self.adopt(snapshot,[dict(person_id=2,leader_id=None)]).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(once,range(2))),[200,409])
        self.permissions.discard('edit_staff_availability')
        self.assertEqual(self.adopt(self.current()).status_code,403)

    def test_unsafe_driver_changes_are_not_adopted_and_roster_fields_are_server_owned(self):
        self.confirm();snapshot=self.current()
        self.assertEqual(self.adopt(snapshot,[dict(person_id=2,leader_id=3)]).status_code,400)
        self.assertEqual(self.adopt(snapshot,[dict(person_id=99999,leader_id=None)]).status_code,400)
        self.cur.execute('UPDATE users SET has_driving_permit=FALSE');self.admin.commit()
        fresh=self.current()
        self.assertEqual(self.adopt(fresh).status_code,400)
        self.assertEqual(self.current()['revision'],1)

    def test_new_dispatch_invalidates_open_draft_even_when_group_revision_is_unchanged(self):
        saved=self.confirm().json
        snapshot=self.current()
        field=next(g for g in saved['groups'] if g['leader_id']==2)
        self.assertEqual(self.assign(field).status_code,200)
        self.assertEqual(self.current()['revision'],snapshot['revision'])
        response=self.adopt(snapshot,[dict(person_id=2,leader_id=None)])
        self.assertEqual(response.status_code,409,response.json)
        self.assertIn('已变化',response.json['error'])

    def test_busy_change_racing_station_assignment_never_commits_partial_group_or_busy_dispatch(self):
        saved=self.confirm().json
        field=next(g for g in saved['groups'] if g['leader_id']==2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            busy=pool.submit(self.availability,available=False)
            dispatch=pool.submit(self.assign,field)
            self.assertEqual(sorted([busy.result().status_code,dispatch.result().status_code]),[200,409])
        self.cur.execute("SELECT available FROM staff_availability WHERE person_name='步雪琼' AND day='2026-10-19'")
        available=self.cur.fetchone()['available']
        self.cur.execute("SELECT inspector_ids FROM inspection_schedule_cells WHERE scheduled_date='2026-10-19' AND inspector_ids<>'[]'::jsonb")
        cells=self.cur.fetchall()
        self.assertTrue(all(available and set(r['inspector_ids'])=={p['id'] for p in field['members']} for r in cells))
        self.assertEqual(bool(cells),available)
