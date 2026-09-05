import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import unittest

from app import get_db_connection, serialize_issue_flow_history_event


class IssueLifecycleTests(unittest.TestCase):
    def test_audit_and_completion_are_not_mislabeled_as_review(self):
        for kind in ('audit_changed', 'inspection_signed', 'inspection_completed', 'issue_updated', 'status_changed'):
            event = serialize_issue_flow_history_event({'action_type': kind, 'round_no': 1})
            self.assertNotEqual(event['action_label'], '督导组提交复核')
            self.assertIsNone(event['round_no'])

    def test_automatic_audit_is_identifiable(self):
        event = serialize_issue_flow_history_event({'action_type': 'audit_changed', 'note': '自动审核：规则', 'result': '审核通过'})
        self.assertEqual(event['actor_display_name'], '系统自动审核')
        self.assertEqual(event['action_label'], '自动审核')

    @unittest.skipUnless(os.environ.get('ISSUE_LIFECYCLE_DB_TEST') == '1', 'Requires local PostgreSQL, all changes rolled back')
    def test_migration_and_lifecycle_in_rollback_transaction(self):
        path = Path(__file__).parents[1] / 'migrations/versions/20260905_001_issue_lifecycle.py'
        spec = importlib.util.spec_from_file_location('lifecycle_migration', path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            migration.op = SimpleNamespace(execute=cur.execute)
            migration.upgrade()
            cur.execute('SELECT COUNT(*) AS n FROM inspection_issue_flow_history')
            count = cur.fetchone()['n']
            migration.upgrade()
            cur.execute('SELECT COUNT(*) AS n FROM inspection_issue_flow_history')
            self.assertEqual(cur.fetchone()['n'], count)
            cur.execute('SELECT id, inspection_id FROM issues ORDER BY id DESC LIMIT 1')
            issue = cur.fetchone()
            if not issue:
                self.skipTest('Needs a local issue fixture')
            for decision in ('pending', 'approved', 'rejected', 'pending'):
                cur.execute('UPDATE issues SET audit_status=%s WHERE id=%s', (decision, issue['id']))
            cur.execute("SELECT result FROM inspection_issue_flow_history WHERE issue_id=%s AND action_type='audit_changed' ORDER BY id DESC LIMIT 3", (issue['id'],))
            self.assertEqual([r['result'] for r in cur.fetchall()], ['待审核', '审核否决', '审核通过'])
            cur.execute("UPDATE issues SET status='站经无法整改' WHERE id=%s", (issue['id'],))
            migration.upgrade()
            cur.execute('SELECT status FROM issues WHERE id=%s', (issue['id'],))
            self.assertEqual(cur.fetchone()['status'], '待整改')
            cur.execute("UPDATE inspections SET station_manager_signed_at=CURRENT_TIMESTAMP, sign_status='已签名确认' WHERE id=%s", (issue['inspection_id'],))
            cur.execute("SELECT action_type FROM inspection_issue_flow_history WHERE issue_id=%s ORDER BY id DESC LIMIT 1", (issue['id'],))
            self.assertEqual(cur.fetchone()['action_type'], 'inspection_signed')
        finally:
            conn.rollback()
            cur.close()
            conn.close()
