"""v11.2 execution-bound field teams and free-person re-entry, isolated DB only."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from time import sleep
from zoneinfo import ZoneInfo
from unittest.mock import patch
from tests import test_staff_team_proposals as proposals


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST') == '1', 'isolated database opt-in')
class TeamExecutionTests(unittest.TestCase):
    setUp_base = proposals.ProposalDatabaseTests.setUp_base
    connect = proposals.ProposalDatabaseTests.connect
    tearDown = proposals.ProposalDatabaseTests.tearDown
    availability = proposals.ProposalDatabaseTests.availability
    save = proposals.ProposalDatabaseTests.save
    post = proposals.ProposalDatabaseTests.post
    confirm = proposals.ProposalDatabaseTests.confirm
    board = proposals.ProposalDatabaseTests.board
    assign = proposals.ProposalDatabaseTests.assign
    current = proposals.ProposalDatabaseTests.current
    adopt = proposals.ProposalDatabaseTests.adopt

    def setUp(self):
        proposals.ProposalDatabaseTests.setUp(self)
        clock = patch('schedule_common.shanghai_now', return_value=datetime(2026,10,19,9,tzinfo=ZoneInfo('Asia/Shanghai')))
        clock.start(); self.addCleanup(clock.stop)

    def dispatched(self):
        saved = self.confirm().json
        group = next(g for g in saved['groups'] if g['leader_id'] == 2)
        outsider = next(p for g in saved['groups'] if g['mode'] == 'online'
                        for p in g['members'] if p['position'] == '大学生')
        response = self.assign(group)
        self.assertEqual(response.status_code, 200, response.json)
        return group, outsider

    def move_in(self, person):
        snapshot = self.current()
        return self.adopt(snapshot, [dict(person_id=person['id'], leader_id=2)])

    def record(self, **kwargs):
        # Do not backdate CURRENT_TIMESTAMP to a test-admin read before dispatch.
        self.admin.commit()
        return proposals.ProposalDatabaseTests.record(self, **kwargs)

    def test_unstarted_field_group_accepts_video_member_and_atomically_syncs_cells_tasks_and_shelf(self):
        group, outsider = self.dispatched()
        old = {p['id'] for p in group['members']}
        response = self.move_in(outsider)
        self.assertEqual(response.status_code, 200, response.json)
        current = self.current()
        changed = next(g for g in current['groups'] if g['leader_id'] == 2)
        self.assertFalse(changed['dispatch_locked'])
        self.assertEqual({p['id'] for p in changed['members']}, old | {outsider['id']})
        self.cur.execute("SELECT inspector_ids,plan_team FROM inspection_schedule_cells WHERE station_id=1 AND mode='offline'")
        cells = self.cur.fetchall()
        self.assertEqual(len(cells), 6)
        self.assertTrue(all(set(c['inspector_ids']) == old | {outsider['id']} for c in cells))
        self.assertTrue(all({p['id'] for p in c['plan_team']['members']} == set(c['inspector_ids']) for c in cells))
        self.cur.execute("SELECT COUNT(*) n FROM inspection_schedule_tasks WHERE user_id=%s AND status='pending'", (outsider['id'],))
        self.assertEqual(self.cur.fetchone()['n'], 6)
        self.cur.execute("SELECT team_ids FROM inspection_schedule_tasks WHERE station_id=1 AND status='pending'")
        self.assertTrue(all(set(r['team_ids']) == old | {outsider['id']} for r in self.cur.fetchall()))
        self.cur.execute("SELECT inspector_ids,plan_team FROM inspection_schedule_shelf WHERE status='waiting' AND mode='offline'")
        waiting=self.cur.fetchall()
        self.assertTrue(any(set(r['inspector_ids']) == old | {outsider['id']} for r in waiting))
        self.assertTrue(all('dispatch_locked' not in p and 'field_dispatched' not in p for row in waiting for p in row['plan_team']['members']))
        self.cur.execute('SELECT COUNT(*) n FROM inspections'); self.assertEqual(self.cur.fetchone()['n'], 0)
        self.cur.execute('SELECT assignments FROM staff_daily_teams')
        self.assertTrue(all('field_dispatched' not in p and 'dispatch_locked' not in p for p in self.cur.fetchone()['assignments']))

    def test_only_member_post_dispatch_evidence_at_matching_station_and_table_locks_before_1700(self):
        group, outsider = self.dispatched()
        self.record(station=2, table=1, inspector=2, day='2026-10-19')
        self.record(station=1, table=7, inspector=2, day='2026-10-19')
        self.record(station=1, table=1, inspector=3, day='2026-10-19')
        self.assertFalse(next(g for g in self.current()['groups'] if g['leader_id']==2)['dispatch_locked'])
        child = next(p for p in group['members'] if p['position']=='大学生')
        self.record(station=1, table=1, inspector=child['id'], day='2026-10-19')
        snapshot = self.current()
        self.assertTrue(all(not p['actual_modes'] for p in snapshot['people']), 'staff actuals are still deferred before 17:00')
        locked = next(g for g in snapshot['groups'] if g['leader_id']==2)
        self.assertTrue(locked['dispatch_locked'])
        self.assertTrue(all(p['dispatch_locked'] for p in locked['members']))
        response = self.adopt(snapshot, [dict(person_id=outsider['id'],leader_id=2)])
        self.assertEqual(response.status_code,409,response.json)
        self.assertIn('派工后',response.json['error'])

    def test_member_refresh_does_not_reset_the_original_dispatch_execution_cutoff(self):
        _, outsider = self.dispatched()
        self.record(station=1,table=1,inspector=outsider['id'],day='2026-10-19')
        before = self.current()
        self.assertFalse(next(g for g in before['groups'] if g['leader_id']==2)['dispatch_locked'])
        response = self.adopt(before,[dict(person_id=outsider['id'],leader_id=2)])
        self.assertEqual(response.status_code,200,response.json)
        self.assertTrue(next(g for g in response.json['groups'] if g['leader_id']==2)['dispatch_locked'])
        self.assertTrue(next(g for g in self.current()['groups'] if g['leader_id']==2)['dispatch_locked'])

    def test_old_records_do_not_freeze_members_but_a_new_issue_on_a_reused_record_does(self):
        _, outsider = self.dispatched()
        rid = self.record(station=1, table=1, inspector=1, day='2026-10-01')
        self.cur.execute("UPDATE inspections SET created_at=(SELECT MIN(updated_at)-INTERVAL '1 hour' FROM inspection_schedule_cells) WHERE id=%s", (rid,))
        self.admin.commit()
        self.assertFalse(next(g for g in self.current()['groups'] if g['leader_id']==2)['dispatch_locked'])
        response = self.move_in(outsider)
        self.assertEqual(response.status_code,200,response.json)
        self.cur.execute('SELECT inspector_id,created_at FROM inspections WHERE id=%s',(rid,))
        record = dict(self.cur.fetchone()); self.admin.commit()
        self.cur.execute('INSERT INTO issues(inspection_id,inspector_id) VALUES(%s,%s)',(rid,outsider['id']))
        self.admin.commit()
        self.assertTrue(next(g for g in self.current()['groups'] if g['leader_id']==2)['dispatch_locked'])
        self.cur.execute('SELECT inspector_id,created_at FROM inspections WHERE id=%s',(rid,))
        self.assertEqual(dict(self.cur.fetchone()),record)

    def assign_annual(self, group):
        self.cur.execute("UPDATE stations SET monitoring_status='未运行' WHERE id=1"); self.admin.commit()
        board=self.board('annual')
        row=next(r for r in board['rows'] if r['station_id']==1)
        response=self.client.put('/api/inspection-schedule',json=dict(mode='annual',year=2026,
            scheduled_date='2026-10-19',inspector_ids=[p['id'] for p in group['members']],
            cells=[dict(station_id=1,column_key=k,revision=c['revision']) for k,c in row['cells'].items() if c['status']=='unassigned']))
        self.assertEqual(response.status_code,200,response.json)
        return board

    def test_metering_annual_video_record_also_locks_the_linked_field_team(self):
        saved=self.confirm().json
        group=next(g for g in saved['groups'] if g['leader_id']==2)
        board=self.assign_annual(group)
        tid=next(c['table_id'] for c in board['columns'] if c['key']=='metering_video')
        self.record(station=1,table=tid,inspector=2,day='2026-10-19')
        self.assertTrue(next(g for g in self.current()['groups'] if g['leader_id']==2)['dispatch_locked'])

    def test_member_change_updates_both_annual_and_quarterly_linked_plans(self):
        saved=self.confirm().json
        group=next(g for g in saved['groups'] if g['leader_id']==2)
        self.assign_annual(group)
        free=next(p for g in saved['groups'] if g['mode']=='online' for p in g['members'] if p['position']=='大学生')
        response=self.move_in(free)
        self.assertEqual(response.status_code,200,response.json)
        expected={p['id'] for p in group['members']}|{free['id']}
        self.cur.execute("SELECT mode,inspector_ids FROM inspection_schedule_cells WHERE station_id=1")
        cells=self.cur.fetchall()
        self.assertEqual({c['mode'] for c in cells},{'offline','annual'})
        self.assertEqual(len(cells),8)
        self.assertTrue(all(set(c['inspector_ids'])==expected for c in cells))
        self.cur.execute("SELECT COUNT(*) n FROM inspection_schedule_tasks WHERE user_id=%s AND status='pending'",(free['id'],))
        self.assertEqual(self.cur.fetchone()['n'],8)

    def test_busy_to_free_returns_to_pool_and_can_join_field_or_video_without_regeneration(self):
        _, outsider=self.dispatched()
        self.assertEqual(self.availability(name=outsider['display_name'],available=False,reason='培训').status_code,200)
        self.assertEqual(self.availability(name=outsider['display_name'],available=True).status_code,200)
        current=self.current()
        self.assertIn(outsider['id'],{p['id'] for p in current['unassigned_people']})
        self.assertNotIn(outsider['id'],{p['id'] for g in current['groups'] for p in g['members']})
        adopted=self.adopt(current,[dict(person_id=outsider['id'],leader_id=2)])
        self.assertEqual(adopted.status_code,200,adopted.json)
        self.assertNotIn(outsider['id'],{p['id'] for p in adopted.json['unassigned_people']})
        self.cur.execute("SELECT COUNT(*) n FROM inspection_schedule_tasks WHERE user_id=%s AND status='pending'",(outsider['id'],))
        self.assertEqual(self.cur.fetchone()['n'],6)
        free=next(p for g in self.current()['groups'] if g['mode']=='online' for p in g['members'] if p['position']=='大学生')
        self.assertEqual(self.availability(name=free['display_name'],available=False).status_code,200)
        self.assertEqual(self.availability(name=free['display_name'],available=True).status_code,200)
        response=self.adopt(self.current(),[dict(person_id=free['id'],leader_id=None)])
        self.assertEqual(response.status_code,200,response.json)
        self.assertIn(free['id'],{p['id'] for g in response.json['groups'] if g['mode']=='online' for p in g['members']})

    def test_pool_is_server_owned_and_does_not_include_busy_or_already_dispatched_people(self):
        saved=self.confirm().json
        video=next(g for g in saved['groups'] if g['mode']=='online')
        p=next(p for p in video['members'] if p['position']=='大学生')
        self.assertEqual(self.assign(dict(video,members=[p]),sid=2).status_code,200)
        self.assertNotIn(p['id'],{p['id'] for p in self.current()['unassigned_people']})
        snapshot=self.current()
        self.assertEqual(self.adopt(snapshot,[dict(person_id=99999,leader_id=2)]).status_code,400)
        self.assertEqual(self.adopt(snapshot,[dict(person_id=p['id'],leader_id=2)]).status_code,409)
        self.assertEqual(self.current()['revision'],1)

    def test_generation_consumes_pool_without_duplicating_saved_or_preview_participants(self):
        _, outsider=self.dispatched()
        self.assertEqual(self.availability(name=outsider['display_name'],available=False).status_code,200)
        self.assertEqual(self.availability(name=outsider['display_name'],available=True).status_code,200)
        current=self.current()
        self.assertIn(outsider['id'],{p['id'] for p in current['unassigned_people']})
        generated=self.post(revision=current['revision'])
        self.assertEqual(generated.status_code,200,generated.json)
        assigned=[p['id'] for g in generated.json['groups'] for p in g['members']]
        self.assertEqual(len(assigned),len(set(assigned)))
        self.assertIn(outsider['id'],assigned)
        self.assertEqual(generated.json['unassigned_people'],[])
        # Generating does not consume the live pool until the plan is adopted.
        self.assertIn(outsider['id'],{p['id'] for p in self.current()['unassigned_people']})

    def test_free_pool_can_create_first_video_assignment_without_any_saved_group(self):
        before=self.current()
        self.assertEqual(before['groups'],[])
        free=next(p for p in before['unassigned_people'] if p['position']=='大学生')
        result=self.adopt(before,[dict(person_id=free['id'],leader_id=None)])
        self.assertEqual(result.status_code,200,result.json)
        self.assertEqual(result.json['groups'][0]['members'][0]['id'],free['id'])
        self.assertNotIn(free['id'],{p['id'] for p in result.json['unassigned_people']})
        self.assertEqual(result.json['revision'],1)

    def test_unstarted_field_member_can_leave_and_old_tasks_are_retired_not_deleted(self):
        group,_=self.dispatched()
        child=next(p for p in group['members'] if p['position']=='大学生')
        result=self.adopt(self.current(),[dict(person_id=child['id'],leader_id=None)])
        self.assertEqual(result.status_code,200,result.json)
        self.cur.execute("SELECT inspector_ids FROM inspection_schedule_cells WHERE station_id=1 AND mode='offline'")
        self.assertTrue(all(child['id'] not in r['inspector_ids'] for r in self.cur.fetchall()))
        self.cur.execute('SELECT status,plan_team FROM inspection_schedule_tasks WHERE user_id=%s',(child['id'],))
        old_tasks=self.cur.fetchall()
        self.assertEqual(len(old_tasks),6)
        self.assertTrue(all(t['status']=='cancelled' and child['id'] in {p['id'] for p in t['plan_team']['members']} for t in old_tasks))
        self.assertIn(child['id'],{p['id'] for g in result.json['groups'] if g['mode']=='online' for p in g['members']})

    def test_last_driver_cannot_leave_dispatched_field_group(self):
        group,_=self.dispatched()
        child=next(p for p in group['members'] if p['position']=='大学生')
        self.cur.execute('UPDATE users SET has_driving_permit=false WHERE id=ANY(%s)',([p['id'] for p in group['members']],))
        self.cur.execute('UPDATE users SET has_driving_permit=true WHERE id=%s',(child['id'],));self.admin.commit()
        before=self.current()
        result=self.adopt(before,[dict(person_id=child['id'],leader_id=None)])
        self.assertEqual(result.status_code,400,result.json)
        self.assertEqual(self.current()['revision'],before['revision'])
        self.cur.execute("SELECT inspector_ids FROM inspection_schedule_cells WHERE station_id=1 AND mode='offline'")
        self.assertTrue(all(child['id'] in r['inspector_ids'] for r in self.cur.fetchall()))

    def test_sync_failure_rolls_back_groups_cells_tasks_and_audit(self):
        _, outsider=self.dispatched()
        before=self.current()
        self.cur.execute('SELECT * FROM inspection_schedule_cells ORDER BY station_id,column_key'); cells=[dict(r) for r in self.cur.fetchall()]
        self.cur.execute('SELECT * FROM inspection_schedule_tasks ORDER BY id'); tasks=[dict(r) for r in self.cur.fetchall()]
        self.cur.execute('ALTER TABLE inspection_schedule_tasks ADD CHECK(false) NOT VALID'); self.admin.commit()
        with self.assertLogs(level='ERROR'):
            response=self.adopt(before,[dict(person_id=outsider['id'],leader_id=2)])
        self.assertEqual(response.status_code,500,response.json)
        self.assertEqual(self.current()['groups'],before['groups'])
        self.assertEqual(self.current()['revision'],before['revision'])
        self.cur.execute('SELECT * FROM inspection_schedule_cells ORDER BY station_id,column_key'); self.assertEqual([dict(r) for r in self.cur.fetchall()],cells)
        self.cur.execute('SELECT * FROM inspection_schedule_tasks ORDER BY id'); self.assertEqual([dict(r) for r in self.cur.fetchall()],tasks)
        self.cur.execute('SELECT COUNT(*) n FROM staff_daily_team_events'); self.assertEqual(self.cur.fetchone()['n'],1)

    def test_new_execution_waits_for_validation_boundary_and_invalidates_open_draft(self):
        _, outsider=self.dispatched()
        before=self.current()
        writer=self.connect()
        try:
            with writer.cursor() as cur:
                cur.execute("INSERT INTO inspections(station_id,inspection_table_id,inspector_id,inspection_date) VALUES(1,1,2,'2026-10-19')")
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(self.adopt,before,[dict(person_id=outsider['id'],leader_id=2)])
                sleep(.15)
                self.assertFalse(future.done(), 'adoption waits for the active record writer')
                writer.commit()
                self.assertEqual(future.result(timeout=5).status_code,409)
        finally:
            writer.close()
        self.assertEqual(self.current()['revision'],1)
