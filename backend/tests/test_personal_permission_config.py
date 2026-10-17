"""Personal overrides inherit untouched keys; retired endpoints cannot be reached."""
from contextlib import ExitStack
import unittest
from unittest.mock import MagicMock, patch

import app as api
from security_service import DEFAULT_PASSWORD_POLICY
from user_permission_config import merge_personal_permissions, replace_personal_permissions, clear_personal_permissions


class PersonalPermissionTests(unittest.TestCase):
    def test_role_changes_propagate_except_explicit_personal_choices(self):
        for base, expected in (({'a': False, 'b': False}, {'a': True, 'b': False}),
                               ({'a': False, 'b': True}, {'a': True, 'b': True})):
            result = merge_personal_permissions(base, {'a': True}, [], lambda value, role: value, 'supervisor')
            self.assertEqual(result, expected)
        self.assertFalse(merge_personal_permissions({'a': True}, {'a': False}, [], lambda value, role: value, '')['a'])

    def test_personal_scope_beats_inherited_exclusive_scope_without_bypassing_dependencies(self):
        own, region, all_stations = api.PERMISSION_EXCLUSIVE_GROUPS[0]
        base = {own: False, region: False, all_stations: True, 'edit_inspection_issues': True}
        overrides = {own: True}
        result = merge_personal_permissions(base, overrides, api.PERMISSION_EXCLUSIVE_GROUPS, api.enforce_exclusive_permissions, 'supervisor')
        self.assertTrue(result[own]); self.assertFalse(result[all_stations])
        self.assertFalse(result['edit_inspection_issues'])
        self.assertEqual(overrides, {own: True}); self.assertTrue(base[all_stations])

    def test_replace_rejects_non_root_unknown_keys_non_boolean_and_conflicting_scopes(self):
        cur = MagicMock(); root = {'id': 1, 'role': 'root'}; target = {'id': 2, 'role': 'supervisor'}
        for overrides, actor in (({}, {'role': 'supervisor'}), ({'bad': True}, root),
                                 ({'a': 'false'}, root), ({'a': True, 'b': True}, root)):
            with self.assertRaises((PermissionError, ValueError)):
                replace_personal_permissions(cur, target, overrides, actor, {'a', 'b'}, [('a', 'b')])
        cur.execute.assert_not_called()
        replace_personal_permissions(cur, target, {'b': False}, root, {'a', 'b'}, [])
        self.assertEqual(cur.execute.call_count, 2)
        self.assertEqual(cur.execute.call_args.args[1], (2, 'b', False, 1))

    def test_retired_pages_permissions_routes_and_badge_query_are_removed(self):
        self.assertFalse({'view_peer_reviews', 'manage_peer_review_tasks', 'view_training', 'view_training_materials', 'upload_training_materials'} & api.PERMISSION_KEYS)
        routes = {route.rule for route in api.app.url_map.iter_rules()}
        self.assertFalse(any(route.startswith(('/api/training-materials', '/api/assessment/peer-reviews')) for route in routes))
        self.assertFalse(hasattr(api, 'get_peer_review_pending_count_for_user'))

    def test_clear_requires_root_and_dry_run_preserves_everything(self):
        cur = MagicMock()
        with self.assertRaises(PermissionError):
            clear_personal_permissions(cur, {'role': 'supervisor'}, apply=True)
        cur.execute.assert_not_called()
        cur.fetchall.return_value = [{'id': 2, 'username': 'area', 'role': 'area_account', 'switches': 2, 'tables': 0, 'regions': 4}]
        result = clear_personal_permissions(cur, {'role': 'root', 'id': 1})
        self.assertEqual(result['area_bindings_preserved'], 4)
        self.assertFalse(any('DELETE' in call.args[0] or 'UPDATE users SET' in call.args[0] for call in cur.execute.call_args_list))


class AccountWorkflowHttpTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.actor = {'id': 1, 'username': 'root', 'role': 'root'}
        self.target = {'id': 2, 'username': 'sample', 'role': 'supervisor'}
        self.conn, self.cur = MagicMock(), MagicMock(); self.conn.cursor.return_value = self.cur
        self.cur.fetchone.return_value = self.target
        self.db = self.stack.enter_context(patch.object(api, 'get_db_connection', return_value=self.conn))
        self.stack.enter_context(patch.object(api, 'verify_auth_token', side_effect=lambda _: (self.actor, {})))
        self.stack.enter_context(patch.object(api, 'get_user_by_id', side_effect=lambda *args: self.actor))
        self.stack.enter_context(patch.object(api, 'can_manage_system', side_effect=lambda cur, user, key: user['role'] == 'root'))
        for name in ('touch_online_user_presence', 'start_backup_scheduler_once', 'ensure_user_security_schema', 'ensure_inspection_checklist_management_schema'):
            self.stack.enter_context(patch.object(api, name))
        self.stack.enter_context(patch.object(api, 'fetch_password_policy', return_value=DEFAULT_PASSWORD_POLICY))
        self.generate = self.stack.enter_context(patch.object(api, 'generate_strong_initial_password', return_value='GeneratedTestCredential!29'))
        self.hash = self.stack.enter_context(patch.object(api, 'validate_and_hash_password', return_value=('hash-only', DEFAULT_PASSWORD_POLICY)))
        self.audit = self.stack.enter_context(patch.object(api, 'record_security_event'))
        self.invalidate = self.stack.enter_context(patch.object(api, 'invalidate_auth_caches_for_user'))
        self.client = api.app.test_client()

    def call(self, path='/api/management/users/2/permissions', payload=None, authenticated=True, method='put'):
        return getattr(self.client, method)(path, json=payload or {}, headers={'Authorization': 'Bearer test'} if authenticated else {})

    def test_permission_endpoint_auth_identity_root_and_missing_target(self):
        self.assertEqual(self.call(authenticated=False).status_code, 401)
        self.assertEqual(self.call(payload={'user_id': 99}).status_code, 403)
        self.db.assert_not_called()
        self.actor['role'] = 'supervisor'
        self.assertEqual(self.call().status_code, 403)
        self.actor['role'] = 'root'; self.cur.fetchone.return_value = None
        self.assertEqual(self.call().status_code, 404)
        self.conn.commit.assert_not_called()

    def test_permission_failure_rolls_back_and_never_invalidates(self):
        self.audit.side_effect = RuntimeError('audit unavailable')
        response = self.call(payload={'permission_overrides': {'view_expert_qa': False}})
        self.assertEqual(response.status_code, 500)
        self.conn.rollback.assert_called_once(); self.conn.commit.assert_not_called(); self.invalidate.assert_not_called()

    def test_permission_success_preserves_area_binding_and_commits_before_invalidation(self):
        self.target['role'] = 'area_account'; events = []
        self.conn.commit.side_effect = lambda: events.append('commit')
        self.invalidate.side_effect = lambda _: events.append('invalidate')
        with patch.object(api, 'apply_user_station_region_scope_updates') as regions:
            response = self.call(payload={'permission_overrides': {'view_expert_qa': False}, 'station_region_scope_values': {}})
        self.assertEqual(response.status_code, 200); regions.assert_not_called()
        self.assertEqual(events, ['commit', 'invalidate'])
        self.assertIn('FOR UPDATE', self.cur.execute.call_args_list[0].args[0])

    def test_new_account_generates_password_once_and_inherits_role_without_switch_rows(self):
        with patch.object(api, 'apply_user_permission_updates') as permissions, \
             patch.object(api, 'apply_user_inspection_table_scope_updates'), \
             patch.object(api, 'apply_user_station_region_scope_updates'):
            response = self.call('/api/management/users', {'username': 'sample', 'role': 'supervisor', 'real_name': 'Sample', 'phone': ''}, method='post')
        self.assertEqual(response.status_code, 200)
        self.generate.assert_called_once(); self.hash.assert_called_once()
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(response.json['credentials'][0]['password'], 'GeneratedTestCredential!29')
        self.assertEqual(permissions.call_args.args[2], {})
        self.assertNotIn('GeneratedTestCredential!29', str(self.audit.call_args))

    def test_profile_only_update_does_not_rewrite_personal_permissions_or_scopes(self):
        with patch.object(api, 'apply_user_permission_updates') as permissions, \
             patch.object(api, 'apply_user_inspection_table_scope_updates') as tables, \
             patch.object(api, 'apply_user_station_region_scope_updates') as regions:
            response = self.call('/api/management/users/2', {'username': 'sample', 'role': 'supervisor', 'real_name': 'Changed', 'phone': ''})
        self.assertEqual(response.status_code, 200)
        permissions.assert_not_called(); tables.assert_not_called(); regions.assert_not_called()
