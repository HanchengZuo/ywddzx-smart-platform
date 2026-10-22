import os
import unittest
from pathlib import Path
from unittest.mock import patch

from driving_permits import permit_value, validate_driving_teams
from staff_daily_teams import random_teams, group_assignments, adjust_preview
from tests import test_staff_daily_teams as daily


class DrivingTeamAlgorithmTests(unittest.TestCase):
    def people(self, manager_permits, student_permits):
        return [dict(id=i+1, display_name=f'管理{i}', position='管理人员', available=True, has_driving_permit=flag)
                for i, flag in enumerate(manager_permits)] + [
            dict(id=i+100, display_name=f'学生{i}', position='大学生', available=True, has_driving_permit=flag)
            for i, flag in enumerate(student_permits)]

    def groups(self, people, seed='test'):
        modes = {str(p['id']): 'offline' for p in people if p['position'] == '管理人员'}
        return random_teams(people, modes, seed)

    def test_default_false_strict_boolean_and_only_supervisor_roles(self):
        for role in ('supervisor_manager', 'supervisor'):
            self.assertFalse(permit_value({}, role))
            self.assertTrue(permit_value({}, role, True))
            self.assertTrue(permit_value({'has_driving_permit': True}, role))
            for bad in ('true', 'false', 1, None, []):
                with self.assertRaises(ValueError): permit_value({'has_driving_permit': bad}, role)
        for role in ('root', 'area_account', 'quality_safety', 'station_manager'):
            self.assertFalse(permit_value({'has_driving_permit': True}, role, True))

    def test_two_drivers_per_team_preferred_and_balance_remains_when_feasible(self):
        for seed in range(80):
            people = self.people([True, False, False], [True]*6 + [False]*12)
            assignments = self.groups(people, str(seed))
            self.assertEqual(assignments, self.groups(people, str(seed)))
            groups = group_assignments(assignments)
            field = [g for g in groups if g['mode']=='offline']
            self.assertEqual(len(field), 3)
            self.assertTrue(all(sum(p['has_driving_permit'] for p in g['members']) >= 2 for g in field))
            self.assertEqual({len(g['members']) for g in field}, {4})
            self.assertEqual(len({p['id'] for p in assignments}), len(people))

    def test_minimum_coverage_never_leaves_an_unlicensed_group_and_shortage_fails(self):
        for seed in range(40):
            people = self.people([False, False, True], [True, True] + [False]*10)
            assignments = self.groups(people, str(seed))
            validate_driving_teams(people, assignments)
            self.assertTrue(all(sum(p.get('has_driving_permit', False) for p in g['members']) >= 1
                                for g in group_assignments(assignments) if g['mode']=='offline'))
        with self.assertRaisesRegex(ValueError, '准驾证'):
            self.groups(self.people([False, False], [True, False]))
        with self.assertRaisesRegex(ValueError, '准驾证'):
            self.groups(self.people([False], []))
        self.assertEqual(self.groups(self.people([True], []))[0]['mode'], 'offline')

    def test_pinned_video_driver_cannot_be_used_and_no_leader_keeps_video_only(self):
        people = self.people([False], [True, False])
        people[1]['station_modes'] = ['online']
        with self.assertRaisesRegex(ValueError, '准驾证'): self.groups(people)
        assignments = random_teams(people, {'1': 'online'}, 'video')
        self.assertTrue(all(p['mode']=='online' for p in assignments))

    def test_qualification_beats_half_split_but_never_changes_explicit_manager_modes(self):
        people = self.people([False, False], [True, True])
        assignments = self.groups(people)
        self.assertTrue(all(p['mode']=='offline' for p in assignments))
        self.assertTrue(all(p['leader_id']==p['id'] for p in assignments if p['position']=='管理人员'))

    def test_client_snapshot_cannot_claim_a_permit_and_final_preview_adjustments_revalidate(self):
        people = self.people([False, False], [True, True, False, False])
        assignments = self.groups(people)
        driver = next(p for p in assignments if p['id']==100)
        with self.assertRaisesRegex(ValueError, '准驾证'):
            adjust_preview(people, assignments, {'100': None})
        target = next(p for p in assignments if p['id']==101)['leader_id']
        swapped = adjust_preview(people, assignments, {'100': target, '101': driver['leader_id']})
        validate_driving_teams(people, swapped)
        with self.assertRaisesRegex(ValueError, '准驾证'):
            validate_driving_teams(self.people([False, False], [False]*4), assignments)


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST') == '1', 'isolated database opt-in')
class DrivingTeamDatabaseTests(daily.DailyTeamDatabaseTests):
    def test_revoked_permit_invalidates_preview_and_blocks_station_dispatch(self):
        self.cur.execute('UPDATE users SET has_driving_permit=FALSE'); self.admin.commit()
        response = self.post()
        self.assertEqual(response.status_code, 400, response.json)
        self.cur.execute('UPDATE users SET has_driving_permit=TRUE WHERE id IN (2,3)'); self.admin.commit()
        preview = self.post().json
        self.cur.execute('UPDATE users SET has_driving_permit=FALSE WHERE id=2'); self.admin.commit()
        response = self.post('confirm', seed=preview['seed'], token=preview['token'], has_driving_permit=True)
        self.assertIn(response.status_code, (400,409))
        self.cur.execute('SELECT 1 FROM staff_daily_teams'); self.assertIsNone(self.cur.fetchone())
        self.cur.execute('UPDATE users SET has_driving_permit=TRUE WHERE id=2'); self.admin.commit()
        saved = self.confirm().json
        self.cur.execute('UPDATE users SET has_driving_permit=FALSE'); self.admin.commit()
        members = [p['id'] for p in next(g for g in saved['groups'] if g['mode']=='offline')['members']]
        manual = self.save(scheduled_date='2026-10-19', inspector_ids=members)
        self.assertEqual(manual.status_code, 400, manual.json)
        self.assertIn('准驾证', manual.json['error'])
        response = self.client.post('/api/inspection-schedule/auto', json=dict(action='preview', day='2026-10-19'))
        self.assertEqual(response.status_code, 200, response.json)
        self.assertTrue(all(g['mode']=='online' for g in response.json['groups']))
        self.assertTrue(any('准驾证' in warning for warning in response.json['warnings']))

    def test_saved_drag_cannot_remove_last_driver_and_rejection_has_no_audit_or_revision_change(self):
        self.cur.execute('UPDATE users SET has_driving_permit=FALSE WHERE id=2')
        self.cur.execute('UPDATE users SET has_driving_permit=TRUE WHERE id=10'); self.admin.commit()
        saved = self.confirm().json
        group = next(g for g in saved['groups'] if g['leader_id']==2)
        self.assertIn(10, [p['id'] for p in group['members']])
        response = self.post('move', revision=1, student_id=10, leader_id=None)
        self.assertEqual(response.status_code, 400, response.json)
        self.assertIn('准驾证', response.json['error'])
        self.cur.execute('SELECT revision FROM staff_daily_teams'); self.assertEqual(self.cur.fetchone()['revision'], 1)
        self.cur.execute('SELECT count(*) AS n FROM staff_daily_team_events'); self.assertEqual(self.cur.fetchone()['n'], 1)

    def test_migration_defaults_false_preserves_real_values_and_is_repeatable(self):
        sql = (Path(__file__).resolve().parents[1] / 'db/init/555_user_driving_permits.sql').read_text()
        self.cur.execute(sql); self.cur.execute(sql)
        self.cur.execute("SELECT has_driving_permit FROM users WHERE id=2"); self.assertTrue(self.cur.fetchone()['has_driving_permit'])
        self.cur.execute("INSERT INTO users(id,username,real_name,role) VALUES(99,'new-driver','新账号','supervisor')")
        self.cur.execute('SELECT has_driving_permit FROM users WHERE id=99'); self.assertFalse(self.cur.fetchone()['has_driving_permit'])
