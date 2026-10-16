"""Root-only password reset HTTP contract; no live business database is accessed."""
from contextlib import ExitStack
import unittest
from unittest.mock import MagicMock, patch

import app as api
from security_service import DEFAULT_PASSWORD_POLICY


class UserPasswordResetTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.actor = dict(id=1, username='root', role='root')
        self.target = dict(id=2, username='staff', role='supervisor', phone='', real_name='Staff')
        self.conn, self.cur = MagicMock(), MagicMock()
        self.conn.cursor.return_value = self.cur
        self.cur.fetchone.return_value = self.target
        self.get_db = self.stack.enter_context(patch.object(api, 'get_db_connection', return_value=self.conn))
        self.stack.enter_context(patch.object(api, 'verify_auth_token', side_effect=lambda _: (self.actor, {})))
        self.stack.enter_context(patch.object(api, 'get_user_by_id', side_effect=lambda *args: self.actor))
        self.stack.enter_context(patch.object(api, 'can_manage_system', return_value=True))
        for name in ('touch_online_user_presence', 'start_backup_scheduler_once', 'ensure_user_security_schema'):
            self.stack.enter_context(patch.object(api, name))
        self.stack.enter_context(patch.object(api, 'fetch_password_policy', return_value=DEFAULT_PASSWORD_POLICY))
        self.generate = self.stack.enter_context(patch.object(api, 'generate_strong_initial_password', return_value='RandomTestCredential!29'))
        self.update = self.stack.enter_context(patch.object(api, 'update_user_password'))
        self.audit = self.stack.enter_context(patch.object(api, 'record_security_event'))
        self.invalidate = self.stack.enter_context(patch.object(api, 'invalidate_auth_caches_for_user'))
        self.client = api.app.test_client()

    def call(self, authenticated=True, **payload):
        return self.client.post('/api/management/users/2/reset-password', json=payload,
                                headers={'Authorization': 'Bearer test'} if authenticated else {})

    def test_requires_authentication_and_rejects_actor_spoofing(self):
        self.assertEqual(self.call(authenticated=False).status_code, 401)
        self.assertEqual(self.call(user_id='999').status_code, 403)
        self.get_db.assert_not_called(); self.update.assert_not_called()

    def test_non_root_cannot_reset_even_with_management_permission(self):
        self.actor['role'] = 'supervisor'
        response = self.call()
        self.assertEqual(response.status_code, 403)
        self.cur.execute.assert_not_called(); self.generate.assert_not_called()
        self.conn.rollback.assert_called_once()

    def test_missing_user_and_root_target_are_protected(self):
        for target, status in ((None, 404), ({**self.target, 'role': 'root'}, 400)):
            self.cur.fetchone.return_value = target
            self.assertEqual(self.call().status_code, status)
        self.update.assert_not_called(); self.audit.assert_not_called(); self.conn.commit.assert_not_called()

    def test_success_reuses_policy_forced_change_and_audit_then_invalidates_sessions(self):
        events = []
        self.conn.commit.side_effect = lambda: events.append('commit')
        self.invalidate.side_effect = lambda _: events.append('invalidate')
        response = self.call()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(response.json['credentials'], [{'username': 'staff', 'password': 'RandomTestCredential!29'}])
        self.generate.assert_called_once_with(self.target, DEFAULT_PASSWORD_POLICY)
        self.update.assert_called_once_with(self.cur, self.target, 'RandomTestCredential!29', policy=DEFAULT_PASSWORD_POLICY,
                                            must_change_password=True, force_change_immediately=True)
        self.assertIn('FOR UPDATE OF u', self.cur.execute.call_args.args[0])
        self.assertEqual(self.cur.execute.call_args.args[1], (2,))
        self.assertEqual(self.audit.call_args.args[2:4], ('administrator_password_reset', 'success'))
        self.assertNotIn('RandomTestCredential!29', str(self.audit.call_args))
        self.assertEqual(events, ['commit', 'invalidate'])
        self.cur.close.assert_called_once(); self.conn.close.assert_called_once()

    def test_password_policy_error_rolls_back_without_returning_credentials(self):
        self.generate.side_effect = ValueError('当前密码策略无法生成安全的初始密码。')
        response = self.call()
        self.assertEqual(response.status_code, 400)
        self.assertNotIn('credentials', response.json)
        self.update.assert_not_called(); self.invalidate.assert_not_called(); self.conn.rollback.assert_called_once()

    def test_update_audit_or_commit_failure_never_returns_password(self):
        for operation in (self.update, self.audit, self.conn.commit):
            with self.subTest(operation=operation):
                operation.side_effect = RuntimeError('sensitive internal detail')
                response = self.call()
                self.assertEqual((response.status_code, response.json),
                                 (500, {'success': False, 'error': '用户密码重置失败，请稍后重试。'}))
                self.invalidate.assert_not_called()
                operation.side_effect = None
