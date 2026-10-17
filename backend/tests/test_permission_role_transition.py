"""Independent expert access and role changes on an opt-in disposable database."""
import os
import unittest
from unittest.mock import MagicMock, patch

import psycopg2
from psycopg2.extensions import parse_dsn
from psycopg2.extras import RealDictCursor

import app as api
from account_security import get_role_min_length
from role_permission_transition import promote_supervisor_managers, split_permission_templates
from security_service import DEFAULT_PASSWORD_POLICY


class PermissionRoleCompatibilityTests(unittest.TestCase):
    def test_supervisor_roles_retain_inspection_access_and_password_strength(self):
        for role in ('supervisor', 'supervisor_manager'):
            self.assertIn(role, api.ROLE_OPTIONS)
            self.assertTrue(api.is_supervisor_like({'role': role}))
            self.assertIn(role, api.PRIVILEGED_AUTH_ROLES)
            self.assertEqual(get_role_min_length(DEFAULT_PASSWORD_POLICY, role), 15)
        for permission in api.PERMISSION_CATALOG:
            self.assertEqual(permission['defaults']['supervisor_manager'], permission['defaults'].get('supervisor', False))
        self.assertFalse(api.is_supervisor_like({'role': 'quality_safety'}))

    def test_personal_and_role_overrides_keep_expert_and_cockpit_independent(self):
        with patch.object(api, 'get_role_permission_overrides', return_value={}), \
             patch.object(api, 'get_permission_overrides', return_value={'view_operations_overview': True, 'view_expert_qa': False}):
            user = {'id': 7, 'role': 'supervisor_manager'}
            self.assertTrue(api.has_permission(MagicMock(), user, 'view_operations_overview'))
            self.assertFalse(api.has_permission(MagicMock(), user, 'view_expert_qa'))
        with patch.object(api, 'get_role_permission_overrides', return_value={'view_operations_overview': False, 'view_expert_qa': True}), \
             patch.object(api, 'get_permission_overrides', return_value={}):
            self.assertFalse(api.has_permission(MagicMock(), user, 'view_operations_overview'))
            self.assertTrue(api.has_permission(MagicMock(), user, 'view_expert_qa'))

    def test_retired_reset_endpoint_is_not_registered(self):
        self.assertNotIn('/api/management/users/reset-permissions-to-role-defaults', {r.rule for r in api.app.url_map.iter_rules()})

    def test_promotion_requires_root_before_any_query(self):
        cur = MagicMock()
        with self.assertRaises(PermissionError):
            promote_supervisor_managers(cur, {7: 'test'}, {'role': 'supervisor_manager'}, apply=True)
        cur.execute.assert_not_called()


@unittest.skipUnless(os.environ.get('PERMISSION_ROLE_TEST_DSN'), 'disposable permission-role database not configured')
class PermissionRoleDatabaseTests(unittest.TestCase):
    def setUp(self):
        config = parse_dsn(os.environ['PERMISSION_ROLE_TEST_DSN'])
        if not config.get('dbname', '').startswith('test_permission_role_'):
            raise RuntimeError('Refusing non-test database')
        self.conn = psycopg2.connect(**config, cursor_factory=RealDictCursor)
        self.addCleanup(self.conn.close)
        self.cur = self.conn.cursor()
        self.addCleanup(self.cur.close)
        self.cur.execute('''
            CREATE TEMP TABLE users (id integer PRIMARY KEY, username text, role text, auth_version integer DEFAULT 1, updated_at timestamptz);
            CREATE TEMP TABLE role_permissions (role text, permission_key text, is_allowed boolean, updated_by integer, PRIMARY KEY(role, permission_key));
            CREATE TEMP TABLE user_permissions (user_id integer, permission_key text, is_allowed boolean, updated_by integer, PRIMARY KEY(user_id, permission_key));
            CREATE TEMP TABLE role_inspection_table_scopes (role text, scope_key text, inspection_table_id integer, updated_by integer, PRIMARY KEY(role, scope_key, inspection_table_id));
            CREATE TEMP TABLE role_station_region_scopes (role text, scope_key text, station_region text, updated_by integer, PRIMARY KEY(role, scope_key, station_region));
            CREATE TEMP TABLE security_audit_logs (actor_user_id integer, actor_username text, actor_role text, target_user_id integer,
                target_username text, action_type text, action_result text, failure_reason text, request_ip text, user_agent text,
                affected_count integer, details jsonb, created_at timestamptz);
            INSERT INTO users(id,username,role) VALUES (1,'root','root'),(7,'manager','supervisor'),(8,'member','supervisor');
            INSERT INTO role_permissions VALUES ('supervisor','view_operations_overview',FALSE,1),('supervisor','audit_inspection_issues',TRUE,1);
            INSERT INTO user_permissions VALUES (7,'view_operations_overview',TRUE,1),(8,'view_operations_overview',FALSE,1);
            INSERT INTO role_inspection_table_scopes VALUES ('supervisor','limit_issue_inspection_table_scope',3,1);
            INSERT INTO role_station_region_scopes VALUES ('supervisor','limit_record_station_region_scope','浦东',1);
        ''')
        self.conn.commit()
        self.actor = {'id': 1, 'username': 'root', 'role': 'root'}

    def row(self, query, params=None):
        self.cur.execute(query, params)
        return self.cur.fetchone()

    def test_transition_preserves_denials_personal_overrides_and_scopes(self):
        split_permission_templates(self.cur)
        self.assertEqual(self.row("SELECT is_allowed FROM role_permissions WHERE role='supervisor_manager' AND permission_key='view_expert_qa'")['is_allowed'], False)
        self.assertTrue(self.row("SELECT is_allowed FROM user_permissions WHERE user_id=7 AND permission_key='view_expert_qa'")['is_allowed'])
        self.assertFalse(self.row("SELECT is_allowed FROM user_permissions WHERE user_id=8 AND permission_key='view_expert_qa'")['is_allowed'])
        self.assertEqual(self.row("SELECT inspection_table_id FROM role_inspection_table_scopes WHERE role='supervisor_manager'")['inspection_table_id'], 3)
        self.assertEqual(self.row("SELECT station_region FROM role_station_region_scopes WHERE role='supervisor_manager'")['station_region'], '浦东')
        with patch.object(api, 'ensure_user_security_schema'):
            user = {'id': 7, 'role': 'supervisor_manager'}
            self.assertTrue(api.has_permission(self.cur, user, 'view_expert_qa'))
            self.cur.execute("UPDATE user_permissions SET is_allowed=FALSE WHERE user_id=7 AND permission_key='view_operations_overview'")
            self.assertFalse(api.has_permission(self.cur, user, 'view_operations_overview'))
            self.assertTrue(api.has_permission(self.cur, user, 'view_expert_qa'))

    def test_repeated_migration_does_not_overwrite_new_administrator_choices(self):
        split_permission_templates(self.cur)
        self.cur.execute("UPDATE role_permissions SET is_allowed=TRUE WHERE role='supervisor_manager' AND permission_key='view_expert_qa'")
        self.cur.execute("UPDATE user_permissions SET is_allowed=FALSE WHERE user_id=7 AND permission_key='view_expert_qa'")
        split_permission_templates(self.cur)
        self.assertTrue(self.row("SELECT is_allowed FROM role_permissions WHERE role='supervisor_manager' AND permission_key='view_expert_qa'")['is_allowed'])
        self.assertFalse(self.row("SELECT is_allowed FROM user_permissions WHERE user_id=7 AND permission_key='view_expert_qa'")['is_allowed'])
        self.assertEqual(self.row('SELECT count(*) AS n FROM role_inspection_table_scopes')['n'], 2)

    def test_dry_run_and_identity_mismatch_do_not_change_users(self):
        promote_supervisor_managers(self.cur, {7: 'manager'}, self.actor)
        for targets in ({7: 'wrong'}, {99: 'missing'}, {1: 'root'}, {7: 'manager', 8: 'wrong'}):
            with self.assertRaises(ValueError):
                promote_supervisor_managers(self.cur, targets, self.actor, apply=True)
        self.assertEqual(self.row('SELECT role FROM users WHERE id=7')['role'], 'supervisor')
        self.assertEqual(self.row('SELECT count(*) AS n FROM security_audit_logs')['n'], 0)

    def test_promotion_changes_only_target_session_version_and_records_audit_once(self):
        promote_supervisor_managers(self.cur, {7: 'manager'}, self.actor, apply=True)
        promote_supervisor_managers(self.cur, {7: 'manager'}, self.actor, apply=True)
        self.assertEqual(dict(self.row('SELECT role,auth_version FROM users WHERE id=7')), {'role': 'supervisor_manager', 'auth_version': 2})
        self.assertEqual(self.row('SELECT role FROM users WHERE id=8')['role'], 'supervisor')
        log = self.row('SELECT * FROM security_audit_logs')
        self.assertEqual((log['actor_user_id'], log['target_user_id'], log['action_type']), (1, 7, 'supervisor_role_split'))
        self.assertEqual(self.row('SELECT count(*) AS n FROM security_audit_logs')['n'], 1)
        self.assertEqual(self.row('SELECT count(*) AS n FROM user_permissions')['n'], 2)

    def test_audit_failure_rolls_back_user_and_session_changes(self):
        with patch('role_permission_transition.record_security_event', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                promote_supervisor_managers(self.cur, {7: 'manager'}, self.actor, apply=True)
        self.conn.rollback()
        self.assertEqual(dict(self.row('SELECT role,auth_version FROM users WHERE id=7')), {'role': 'supervisor', 'auth_version': 1})
        self.assertEqual(self.row('SELECT count(*) AS n FROM security_audit_logs')['n'], 0)
