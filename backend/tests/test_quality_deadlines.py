import os
import unittest
from types import SimpleNamespace
from tests import test_issue_appeals as appeal_tests
from quality_deadlines import run_deadline_scan


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

    def prepare_unsigned(self):
        # Keep this rollback-only fixture independent of unrelated local backlog/batch limits.
        self.cur.execute("UPDATE inspections SET quality_accept_started_at=CURRENT_TIMESTAMP+interval '1 year',quality_accept_deadline_at=CURRENT_TIMESTAMP+interval '1 year' WHERE id<>%s", (self.issue['inspection_id'],))
        self.cur.execute("UPDATE quality_deadline_policy SET activated_at=CURRENT_TIMESTAMP-interval '30 days' WHERE id=1")
        self.cur.execute("""UPDATE inspections SET sign_status='待签名确认',station_manager_signed_at=NULL,
          inspector_completion_status='已确认完成',inspector_completed_at=CURRENT_TIMESTAMP-interval '5 days',
          inspection_table_id=(SELECT inspection_table_id FROM issues WHERE id=%s),
          quality_accept_started_at=NULL,quality_accept_deadline_at=NULL WHERE id=%s""", (self.issue['id'],self.issue['inspection_id']))
        self.cur.execute("UPDATE issues SET audit_status='approved',audited_at=CURRENT_TIMESTAMP-interval '5 days' WHERE inspection_id=%s", (self.issue['inspection_id'],))

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
        self.assertEqual(events[0]['policy']['acceptance_days'], 3)
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
        self.assertEqual((row['quality_accept_deadline_at'] - row['quality_accept_started_at']).days, 3)
        self.cur.execute('UPDATE quality_deadline_policy SET acceptance_days=1,version=version+1 WHERE id=1')
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

    def test_handoff_preserves_shared_deadline(self):
        aid = self.start()
        self.cur.execute('SELECT review_deadline_at FROM inspection_issue_appeals WHERE id=%s', (aid,))
        deadline = self.cur.fetchone()['review_deadline_at']
        self.assertEqual(self.decide(aid,'area','area_pending').status_code, 200)
        self.cur.execute('SELECT review_deadline_at,phase_responsible FROM inspection_issue_appeals WHERE id=%s', (aid,))
        row = self.cur.fetchone()
        self.assertEqual(row['review_deadline_at'],deadline)
        self.assertIn('quality_pending',row['phase_responsible'])

    def expire_review(self, aid):
        self.cur.execute("UPDATE inspection_issue_appeals SET review_deadline_at=CURRENT_TIMESTAMP-interval '1 second' WHERE id=%s", (aid,))

    def test_timeout_rejects_at_current_stage_and_leaves_one_event(self):
        self.cur.execute("UPDATE quality_deadline_policy SET timeout_action='reject' WHERE id=1")
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

    def test_timeout_approval_ends_appeal_without_faking_quality_reviewer(self):
        self.cur.execute("UPDATE quality_deadline_policy SET timeout_action='approve' WHERE id=1")
        aid = self.start(); self.expire_review(aid); self.scan()
        self.assertEqual(self.state(),'已销毁')
        self.cur.execute('SELECT status,timeout_stage,quality_at,area_by FROM inspection_issue_appeals WHERE id=%s', (aid,))
        row = self.cur.fetchone()
        self.assertEqual(row['status'],'approved')
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
        data = self.client.get(path,headers=headers).json['policy']
        data.update(acceptance_days=4,appeal_days=5,review_days=6,timeout_action='reject')
        self.assertEqual(self.client.put(path,json=dict(data,acceptance_days=0),headers=headers).status_code,400)
        self.assertEqual(self.client.put(path,json=data,headers=headers).status_code,200)
        self.assertEqual(self.client.put(path,json=data,headers=headers).status_code,409)
        events = self.client.get(path+'/events',headers=headers).json['items']
        self.assertEqual(events[0]['kind'],'policy_updated')
        self.assertEqual(events[0]['actor']['username'],'root')
