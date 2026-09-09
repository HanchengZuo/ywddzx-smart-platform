import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from tests import test_issue_appeals as appeal_tests
from quality_deadlines import run_deadline_scan, scan_interval_seconds


class ScanIntervalTests(unittest.TestCase):
    def test_default_and_safe_bounds(self):
        for value, expected in [(None,10800),('bad',10800),('1',1800),('99999',86400),('240',14400)]:
            with patch.dict(os.environ, {}, clear=True):
                if value is not None:
                    os.environ['QUALITY_DEADLINE_SCAN_MINUTES'] = value
                self.assertEqual(scan_interval_seconds(), expected)


@unittest.skipUnless(os.environ.get('ISSUE_LIFECYCLE_DB_TEST') == '1', 'Local PostgreSQL only; rolled back')
class QualityDeadlineTests(unittest.TestCase):
    setUp = appeal_tests.AppealDatabaseTests.setUp
    cleanup_database = appeal_tests.AppealDatabaseTests.cleanup_database
    post = appeal_tests.AppealDatabaseTests.post
    start = appeal_tests.AppealDatabaseTests.start
    state = appeal_tests.AppealDatabaseTests.state
    decide = appeal_tests.AppealDatabaseTests.decide

    def scan(self):
        run_deadline_scan(self.cur, SimpleNamespace(**self.namespace))

    def test_work_calendar_weekends_holidays_makeup_and_unknown_year(self):
        cases = [
            ('2026-09-11 12:00+08', 24, '2026-09-14 12:00'),
            ('2025-05-30 12:00+08', 24, '2025-06-03 12:00'),
            ('2025-09-30 12:00+08', 24, '2025-10-09 12:00'),
            ('2025-09-28 00:00+08', 12, '2025-09-28 12:00'),
            ('2026-09-11 23:30+08', 1, '2026-09-14 00:30'),
            ('2027-01-01 00:00+08', 1, None),
            ('2026-12-31 12:00+08', 72, None),
        ]
        for start, hours, expected in cases:
            with self.subTest(start=start):
                self.cur.execute("SELECT to_char(quality_add_work_hours(%s,%s) AT TIME ZONE 'Asia/Shanghai','YYYY-MM-DD HH24:MI') AS deadline", (start,hours))
                self.assertEqual(self.cur.fetchone()['deadline'], expected)

    def test_both_review_timeouts_preserve_each_stage_evidence(self):
        self.cur.execute("UPDATE quality_deadline_policy SET area_review_timeout_action='approve',quality_review_timeout_action='reject' WHERE id=1")
        aid = self.start(); self.expire_review(aid); self.scan()
        self.assertEqual(self.state(),'申诉中')
        self.cur.execute('SELECT review_phase,review_deadline_at>CURRENT_TIMESTAMP AS fresh FROM inspection_issue_appeals WHERE id=%s',(aid,))
        row = self.cur.fetchone()
        self.assertEqual(row['review_phase'],'quality_review')
        self.assertTrue(row['fresh'])
        self.expire_review(aid); self.scan(); self.scan()
        self.assertEqual(self.state(),'待整改')
        self.cur.execute("SELECT stage FROM quality_deadline_events WHERE appeal_id=%s AND kind='review_timeout' ORDER BY id",(aid,))
        self.assertEqual([r['stage'] for r in self.cur.fetchall()],['area_pending','quality_pending'])
        self.cur.execute('SELECT area_timeout_at,quality_timeout_at,area_by,quality_by FROM inspection_issue_appeals WHERE id=%s',(aid,))
        row = self.cur.fetchone()
        self.assertTrue(row['area_timeout_at']); self.assertTrue(row['quality_timeout_at'])
        self.assertIsNone(row['area_by']); self.assertIsNone(row['quality_by'])

    def test_missing_calendar_does_not_reject_application_or_approve_review(self):
        self.cur.execute('DELETE FROM quality_work_calendar')
        self.cur.execute('UPDATE issues SET quality_appeal_deadline_at=NULL WHERE id=%s',(self.issue['id'],))
        self.cur.execute("UPDATE quality_deadline_policy SET area_review_timeout_action='approve' WHERE id=1")
        aid = self.start(); self.scan()
        self.assertEqual(self.state(),'申诉中')
        self.cur.execute('SELECT review_deadline_at FROM inspection_issue_appeals WHERE id=%s',(aid,))
        self.assertIsNone(self.cur.fetchone()['review_deadline_at'])
        self.assertEqual(self.decide(aid,'area','area_pending','reject').status_code,200)

    def test_migration_rerun_keeps_custom_hour_settings_and_grace(self):
        import importlib.util
        from pathlib import Path
        self.cur.execute('UPDATE quality_deadline_policy SET area_review_hours=37,quality_review_hours=81 WHERE id=1 RETURNING *')
        before = dict(self.cur.fetchone())
        spec = importlib.util.spec_from_file_location('working_hours',Path(__file__).parents[1]/'migrations/versions/20260909_002_working_hour_deadlines.py')
        migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
        migration.op = SimpleNamespace(execute=self.cur.execute)
        migration.upgrade(); migration.upgrade()
        self.cur.execute('SELECT * FROM quality_deadline_policy WHERE id=1')
        self.assertEqual(dict(self.cur.fetchone()),before)

    def test_quality_timeout_approval_destroys_only_after_handoff(self):
        self.cur.execute("UPDATE quality_deadline_policy SET quality_review_timeout_action='approve' WHERE id=1")
        aid = self.start()
        self.decide(aid,'area','area_pending')
        self.expire_review(aid); self.scan()
        self.assertEqual(self.state(),'已销毁')

    def prepare_unsigned(self):
        # Keep this rollback-only fixture independent of unrelated local backlog/batch limits.
        self.cur.execute("UPDATE inspections SET quality_accept_started_at=CURRENT_TIMESTAMP+interval '1 year',quality_accept_deadline_at=CURRENT_TIMESTAMP+interval '1 year' WHERE id<>%s", (self.issue['inspection_id'],))
        self.cur.execute("UPDATE quality_deadline_policy SET activated_at=CURRENT_TIMESTAMP-interval '30 days',acceptance_enabled_at=CURRENT_TIMESTAMP-interval '30 days' WHERE id=1")
        self.cur.execute("""UPDATE inspections SET sign_status='待签名确认',station_manager_signed_at=NULL,
          inspector_completion_status='已确认完成',inspector_completed_at=CURRENT_TIMESTAMP-interval '15 days',
          inspection_table_id=(SELECT inspection_table_id FROM issues WHERE id=%s),
          quality_accept_started_at=NULL,quality_accept_deadline_at=NULL WHERE id=%s""", (self.issue['id'],self.issue['inspection_id']))
        self.cur.execute("UPDATE issues SET audit_status='approved',audited_at=CURRENT_TIMESTAMP-interval '15 days' WHERE inspection_id=%s", (self.issue['inspection_id'],))

    def row(self):
        self.cur.execute('SELECT * FROM inspections WHERE id=%s', (self.issue['inspection_id'],))
        return self.cur.fetchone()

    def test_auto_acceptance_is_idempotent_and_records_evidence(self):
        self.prepare_unsigned()
        self.scan()
        row = self.row()
        self.assertEqual(row['quality_accept_source'], 'automatic')
        self.assertEqual(row['sign_status'], '已签名确认')
        self.assertIsNone(row['station_manager_signature_path'])
        self.scan()
        self.cur.execute("SELECT * FROM quality_deadline_events WHERE inspection_id=%s AND kind='acceptance_timeout'", (row['id'],))
        events = self.cur.fetchall()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['policy']['acceptance_hours'], 72)
        self.cur.execute("SELECT count(*) AS n FROM inspection_issue_flow_history WHERE issue_id=%s AND action_type='inspection_auto_accepted'", (self.issue['id'],))
        self.assertEqual(self.cur.fetchone()['n'], 1)

    def test_pending_audit_never_auto_accepts(self):
        self.prepare_unsigned()
        self.cur.execute("UPDATE issues SET audit_status='pending' WHERE id=%s", (self.issue['id'],))
        self.scan()
        self.assertNotEqual(self.row()['sign_status'], '已签名确认')
        self.assertIsNone(self.row()['quality_accept_deadline_at'])

    def test_deadline_starts_on_last_audit_not_inspection_date(self):
        self.prepare_unsigned()
        self.cur.execute('UPDATE issues SET audited_at=CURRENT_TIMESTAMP WHERE id=%s', (self.issue['id'],))
        self.scan()
        row = self.row()
        self.assertNotEqual(row['sign_status'], '已签名确认')
        self.assertGreaterEqual((row['quality_accept_deadline_at'] - row['quality_accept_started_at']).days, 3)
        self.cur.execute('UPDATE quality_deadline_policy SET acceptance_hours=24,version=version+1 WHERE id=1')
        self.cur.execute('SELECT refresh_quality_acceptance(%s)', (row['id'],))
        self.assertEqual(self.row()['quality_accept_deadline_at'], row['quality_accept_deadline_at'])

    def test_non_quality_tables_are_excluded(self):
        self.prepare_unsigned()
        self.cur.execute('SELECT id FROM inspection_tables WHERE NOT is_quality_deadline_table(id) LIMIT 1')
        other = self.cur.fetchone()['id']
        self.cur.execute('UPDATE inspections SET inspection_table_id=%s WHERE id=%s', (other,self.issue['inspection_id']))
        self.cur.execute('UPDATE issues SET inspection_table_id=%s WHERE inspection_id=%s', (other,self.issue['inspection_id']))
        self.scan()
        self.assertNotEqual(self.row()['sign_status'], '已签名确认')

    def test_expired_application_is_rejected_by_server(self):
        self.cur.execute("UPDATE issues SET quality_appeal_deadline_at=CURRENT_TIMESTAMP WHERE id=%s", (self.issue['id'],))
        response = self.post(f"/api/issues/{self.issue['id']}/appeals", reason='超过申请期')
        self.assertEqual(response.status_code, 409)
        self.assertIn('期限', response.json['error'])

    def test_manual_acceptance_wins_before_background_processing(self):
        self.prepare_unsigned()
        self.cur.execute("UPDATE inspections SET sign_status='已签名确认',quality_accept_source='manual',station_manager_signed_at=CURRENT_TIMESTAMP WHERE id=%s", (self.issue['inspection_id'],))
        self.scan()
        self.assertEqual(self.row()['quality_accept_source'],'manual')
        self.cur.execute("SELECT count(*) AS n FROM quality_deadline_events WHERE inspection_id=%s AND kind='acceptance_timeout'",(self.issue['inspection_id'],))
        self.assertEqual(self.cur.fetchone()['n'],0)

    def test_only_one_database_scan_can_hold_the_lock(self):
        self.cur.execute('SELECT pg_advisory_xact_lock(66092026)')
        import app as core
        other = core.get_db_connection()
        try:
            with other.cursor() as cursor:
                run_deadline_scan(cursor, SimpleNamespace(**self.namespace))
                cursor.execute('SELECT pg_try_advisory_xact_lock(66092026) AS acquired')
                self.assertFalse(cursor.fetchone()['acquired'])
        finally:
            other.rollback(); other.close()

    def test_handoff_starts_independent_quality_deadline(self):
        self.cur.execute('UPDATE quality_deadline_policy SET area_review_hours=12,quality_review_hours=96 WHERE id=1')
        aid = self.start()
        self.cur.execute('SELECT review_deadline_at FROM inspection_issue_appeals WHERE id=%s', (aid,))
        deadline = self.cur.fetchone()['review_deadline_at']
        self.assertEqual(self.decide(aid,'area','area_pending').status_code, 200)
        self.cur.execute('SELECT review_deadline_at,phase_responsible FROM inspection_issue_appeals WHERE id=%s', (aid,))
        row = self.cur.fetchone()
        self.assertGreater(row['review_deadline_at'],deadline)
        self.assertIn('quality_pending',row['phase_responsible'])

    def expire_review(self, aid):
        self.cur.execute("UPDATE inspection_issue_appeals SET review_deadline_at=CURRENT_TIMESTAMP-interval '1 second' WHERE id=%s", (aid,))

    def test_timeout_rejects_at_current_stage_and_leaves_one_event(self):
        self.cur.execute("UPDATE quality_deadline_policy SET quality_review_timeout_action='reject' WHERE id=1")
        aid = self.start()
        self.decide(aid,'area','area_pending')
        self.expire_review(aid)
        self.assertEqual(self.decide(aid,'quality','quality_pending').status_code,409)
        self.scan(); self.scan()
        self.assertEqual(self.state(),'待整改')
        self.cur.execute("SELECT timeout_stage,quality_by FROM inspection_issue_appeals WHERE id=%s", (aid,))
        row = self.cur.fetchone()
        self.assertEqual(row['timeout_stage'],'quality_pending')
        self.assertIsNone(row['quality_by'])
        self.cur.execute("SELECT * FROM quality_deadline_events WHERE appeal_id=%s AND kind='review_timeout'", (aid,))
        events = self.cur.fetchall()
        self.assertEqual(len(events),1)
        self.assertIn('phase_start',events[0]['responsible'])

    def test_area_timeout_approval_hands_off_without_faking_quality_reviewer(self):
        self.cur.execute("UPDATE quality_deadline_policy SET area_review_timeout_action='approve' WHERE id=1")
        aid = self.start(); self.expire_review(aid); self.scan()
        self.assertEqual(self.state(),'申诉中')
        self.cur.execute('SELECT status,timeout_stage,quality_at,area_by FROM inspection_issue_appeals WHERE id=%s', (aid,))
        row = self.cur.fetchone()
        self.assertEqual(row['status'],'quality_pending')
        self.assertEqual(row['timeout_stage'],'area_pending')
        self.assertIsNone(row['area_by']); self.assertIsNone(row['quality_at'])

    def test_manual_policy_and_completed_appeals_are_not_automatically_changed(self):
        aid = self.start(); self.expire_review(aid); self.scan()
        self.assertEqual(self.state(),'申诉中')
        self.assertEqual(self.decide(aid,'area','area_pending','reject').status_code,200)
        self.scan()
        self.cur.execute('SELECT timeout_at FROM inspection_issue_appeals WHERE id=%s',(aid,))
        self.assertIsNone(self.cur.fetchone()['timeout_at'])

    def test_management_requires_server_root_and_audits_updates(self):
        path = '/api/management/quality-deadlines'
        self.assertEqual(self.client.get(path).status_code,401)
        for identity in ('station','area','quality'):
            self.assertEqual(self.client.get(path,headers={'X-Test-Identity':identity}).status_code,403)
        self.users['root'] = dict(self.users['station'], role='root', username='root')
        headers = {'X-Test-Identity':'root'}
        policy = self.client.get(path,headers=headers).json['policy']
        data = dict(stage='acceptance',enabled=False,hours=96,version=policy['version'])
        self.assertEqual(self.client.put(path,json=dict(data,hours=0),headers=headers).status_code,400)
        self.assertEqual(self.client.put(path,json=dict(data,enabled='false'),headers=headers).status_code,400)
        self.assertEqual(self.client.put(path,json=data,headers=headers).status_code,200)
        self.assertEqual(self.client.put(path,json=data,headers=headers).status_code,409)
        updated = self.client.get(path,headers=headers).json['policy']
        self.assertFalse(updated['acceptance_enabled'])
        for field in ('appeal_enabled','appeal_hours','area_review_enabled','area_review_hours','quality_review_timeout_action'):
            self.assertEqual(updated[field],policy[field])
        events = self.client.get(path+'/events',headers=headers).json['items']
        self.assertEqual(events[0]['kind'],'policy_updated')
        self.assertEqual(events[0]['actor']['username'],'root')

    def set_switch(self, stage, enabled):
        self.users['root'] = dict(self.users['station'], role='root', username='root')
        headers = {'X-Test-Identity':'root'}
        path = '/api/management/quality-deadlines'
        policy = self.client.get(path,headers=headers).json['policy']
        response = self.client.put(path,headers=headers,json=dict(stage=stage,enabled=enabled,
            hours=policy[f'{stage}_hours'],timeout_action=policy.get(f'{stage}_timeout_action'),version=policy['version']))
        self.assertEqual(response.status_code,200,response.json)

    def test_disabled_acceptance_does_not_process_existing_overdue_record(self):
        self.prepare_unsigned()
        self.cur.execute('SELECT refresh_quality_acceptance(%s)', (self.issue['inspection_id'],))
        self.set_switch('acceptance',False)
        self.scan()
        self.assertNotEqual(self.row()['sign_status'],'已签名确认')
        self.cur.execute("SELECT quality_effective_deadline('acceptance',quality_accept_deadline_at,quality_accept_started_at) AS deadline FROM inspections WHERE id=%s", (self.issue['inspection_id'],))
        self.assertIsNone(self.cur.fetchone()['deadline'])
        self.set_switch('acceptance',True)
        self.scan()
        self.assertNotEqual(self.row()['sign_status'],'已签名确认')
        self.cur.execute('SELECT quality_accept_deadline_at>CURRENT_TIMESTAMP AS fresh FROM inspections WHERE id=%s', (self.issue['inspection_id'],))
        self.assertTrue(self.cur.fetchone()['fresh'])

    def test_disabled_application_window_allows_expired_issue_but_not_second_appeal(self):
        self.cur.execute("UPDATE issues SET quality_appeal_deadline_at=CURRENT_TIMESTAMP-interval '1 day' WHERE id=%s", (self.issue['id'],))
        self.set_switch('appeal',False)
        aid = self.start()
        self.assertEqual(self.decide(aid,'area','area_pending','reject').status_code,200)
        response = self.post(f"/api/issues/{self.issue['id']}/appeals",reason='再次申诉')
        self.assertEqual(response.status_code,409)

    def test_disabled_review_preserves_manual_handoff_and_decision(self):
        self.cur.execute("UPDATE quality_deadline_policy SET area_review_timeout_action='approve' WHERE id=1")
        aid = self.start(); self.expire_review(aid)
        self.set_switch('area_review',False)
        self.scan()
        self.assertEqual(self.state(),'申诉中')
        self.assertEqual(self.decide(aid,'area','area_pending').status_code,200)
        self.assertEqual(self.decide(aid,'quality','quality_pending','reject').status_code,200)
        self.assertEqual(self.state(),'待整改')

    def test_reenabled_review_and_application_receive_full_grace(self):
        self.cur.execute("UPDATE quality_deadline_policy SET area_review_timeout_action='approve' WHERE id=1")
        aid = self.start()
        self.cur.execute("UPDATE inspection_issue_appeals SET review_started_at=CURRENT_TIMESTAMP-interval '5 days',review_deadline_at=CURRENT_TIMESTAMP-interval '1 day' WHERE id=%s", (aid,))
        self.set_switch('area_review',False); self.set_switch('area_review',True)
        self.scan()
        self.assertEqual(self.state(),'申诉中')
        self.cur.execute('SELECT review_deadline_at>CURRENT_TIMESTAMP AS fresh FROM inspection_issue_appeals WHERE id=%s',(aid,))
        self.assertTrue(self.cur.fetchone()['fresh'])
        self.cur.execute("UPDATE issues SET quality_appeal_started_at=CURRENT_TIMESTAMP-interval '5 days',quality_appeal_deadline_at=CURRENT_TIMESTAMP-interval '1 day' WHERE id=%s", (self.issue['id'],))
        self.set_switch('appeal',False); self.set_switch('appeal',True)
        self.cur.execute("SELECT quality_effective_deadline('appeal',quality_appeal_deadline_at,quality_appeal_started_at)>CURRENT_TIMESTAMP AS fresh FROM issues WHERE id=%s", (self.issue['id'],))
        self.assertTrue(self.cur.fetchone()['fresh'])

    def test_new_appeal_with_review_off_can_be_manually_completed(self):
        self.set_switch('area_review',False)
        aid = self.start()
        self.cur.execute('SELECT review_deadline_at FROM inspection_issue_appeals WHERE id=%s',(aid,))
        self.assertIsNone(self.cur.fetchone()['review_deadline_at'])
        self.assertEqual(self.decide(aid,'area','area_pending').status_code,200)
        self.assertEqual(self.decide(aid,'quality','quality_pending').status_code,200)

    def test_sequential_workers_and_restart_share_the_same_scan_schedule(self):
        self.prepare_unsigned()
        self.cur.execute('UPDATE quality_deadline_worker_state SET next_scan_at=NULL WHERE id=1')
        run_deadline_scan(self.cur,SimpleNamespace(**self.namespace),scheduled=True)
        self.assertEqual(self.row()['quality_accept_source'],'automatic')
        self.prepare_unsigned()
        run_deadline_scan(self.cur,SimpleNamespace(**self.namespace),scheduled=True)
        self.assertNotEqual(self.row()['sign_status'],'已签名确认')
        self.cur.execute('SELECT next_scan_at>last_success_at AS delayed FROM quality_deadline_worker_state WHERE id=1')
        self.assertTrue(self.cur.fetchone()['delayed'])

    def test_all_switches_off_do_not_initialize_or_process_tasks(self):
        self.prepare_unsigned()
        for stage in ('acceptance','appeal','area_review','quality_review'):
            self.set_switch(stage,False)
        self.scan()
        self.assertIsNone(self.row()['quality_accept_deadline_at'])
        self.assertNotEqual(self.row()['sign_status'],'已签名确认')

    def test_reenable_grace_snapshot_is_not_changed_before_lazy_scan(self):
        aid = self.start()
        self.cur.execute("UPDATE inspection_issue_appeals SET created_at=CURRENT_TIMESTAMP-interval '5 days',review_started_at=CURRENT_TIMESTAMP-interval '5 days' WHERE id=%s",(aid,))
        self.set_switch('area_review',False); self.set_switch('area_review',True)
        # New-task defaults change before the low-frequency worker has materialized old tasks.
        self.cur.execute("UPDATE quality_deadline_policy SET area_review_hours=216,area_review_timeout_action='approve' WHERE id=1")
        self.scan()
        self.cur.execute('SELECT review_policy,review_deadline_at-review_started_at AS duration FROM inspection_issue_appeals WHERE id=%s',(aid,))
        row = self.cur.fetchone()
        self.assertEqual(row['review_policy']['area_review_hours'],72)
        self.assertEqual(row['review_policy']['timeout_action'],'manual')

    def test_all_independent_switch_combinations_mask_only_their_own_deadline(self):
        from itertools import product
        for flags in product((False,True),repeat=4):
            self.cur.execute('UPDATE quality_deadline_policy SET acceptance_enabled=%s,appeal_enabled=%s,area_review_enabled=%s,quality_review_enabled=%s WHERE id=1',flags)
            for stage, enabled in zip(('acceptance','appeal','area_review','quality_review'),flags):
                self.cur.execute("SELECT quality_effective_deadline(%s,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP) IS NOT NULL AS enabled",(stage,))
                self.assertEqual(self.cur.fetchone()['enabled'],enabled)
