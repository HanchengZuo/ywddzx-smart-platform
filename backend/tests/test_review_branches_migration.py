import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from app import get_db_connection, serialize_issue_flow_history_event, display_issue_status


class ReviewBranchesTests(unittest.TestCase):
    def test_reset_names_and_destroyed_status(self):
        for row, label in [
            ({'action_type': 'inspection_completed', 'to_status': '巡检完成状态：待检查人确认'}, '重置巡检记录'),
            ({'action_type': 'inspection_reset'}, '重置巡检记录'),
            ({'action_type': 'audit_changed', 'result': '待审核'}, '审核重新判定（恢复待审核）'),
            ({'action_type': 'audit_changed', 'result': '待审核', 'note': '巡检记录重置，审核恢复待审核'}, '巡检重置：恢复待审核'),
        ]:
            self.assertEqual(serialize_issue_flow_history_event(row)['action_label'], label)
        self.assertEqual(display_issue_status({'status': '待整改', 'audit_status': 'rejected'}), '已销毁')

    @unittest.skipUnless(os.environ.get('ISSUE_LIFECYCLE_DB_TEST') == '1', 'Local PostgreSQL only; changes rolled back')
    def test_migration_and_reopen(self):
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            for name in ['20260905_001_issue_lifecycle', '20260905_002_review_branches']:
                path = Path(__file__).parents[1] / f'migrations/versions/{name}.py'
                spec = importlib.util.spec_from_file_location(name, path)
                migration = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(migration)
                migration.op = SimpleNamespace(execute=cur.execute)
                migration.upgrade()
            migration.upgrade()
            cur.execute('SELECT id, inspection_id FROM issues ORDER BY id DESC LIMIT 1')
            issue = cur.fetchone()
            if not issue:
                self.skipTest('Needs a local issue')
            cur.execute("UPDATE issues SET audit_status='rejected' WHERE id=%s", (issue['id'],))
            cur.execute('SELECT status FROM issues WHERE id=%s', (issue['id'],))
            self.assertEqual(cur.fetchone()['status'], '已销毁')
            cur.execute("SELECT set_config('app.lifecycle_context','inspection_reset',true)")
            cur.execute("UPDATE issues SET audit_status='pending',audit_source=NULL WHERE id=%s", (issue['id'],))
            cur.execute('SELECT status FROM issues WHERE id=%s', (issue['id'],))
            self.assertEqual(cur.fetchone()['status'], '待整改')
            cur.execute("SELECT note FROM inspection_issue_flow_history WHERE issue_id=%s ORDER BY id DESC LIMIT 1", (issue['id'],))
            self.assertIn('巡检记录重置', cur.fetchone()['note'])
            cur.execute("UPDATE inspections SET inspector_completion_status='已确认完成' WHERE id=%s", (issue['inspection_id'],))
            cur.execute("UPDATE inspections SET inspector_completion_status='待检查人确认' WHERE id=%s", (issue['inspection_id'],))
            cur.execute("SELECT action_type FROM inspection_issue_flow_history WHERE issue_id=%s ORDER BY id DESC LIMIT 1", (issue['id'],))
            self.assertEqual(cur.fetchone()['action_type'], 'inspection_reset')
        finally:
            conn.rollback()
            cur.close()
            conn.close()
