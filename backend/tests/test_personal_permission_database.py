"""Opt-in transactions on a disposable database, with no production connections."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import psycopg2
from psycopg2.extensions import parse_dsn
from psycopg2.extras import RealDictCursor

import app as api
from account_security import verify_password
from security_service import DEFAULT_PASSWORD_POLICY
from user_permission_config import clear_personal_permissions


@unittest.skipUnless(os.environ.get('USER_PERMISSION_CONFIG_TEST_DSN'), 'disposable account database not configured')
class PersonalPermissionDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = parse_dsn(os.environ['USER_PERMISSION_CONFIG_TEST_DSN'])
        if not cls.config.get('dbname', '').startswith('test_personal_permission_'):
            raise RuntimeError('Refusing non-test database')
        cls.config.setdefault('port', '5432')
        cls.config['cursor_factory'] = RealDictCursor
        with psycopg2.connect(**cls.config) as conn, conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE stations (id integer PRIMARY KEY, hos_station_code text);
                CREATE TABLE users (id serial PRIMARY KEY, username text UNIQUE, role text, real_name text, phone text,
                    station_id integer, password_hash text, must_change_password boolean, force_change_immediately boolean,
                    password_policy_version integer, password_risk_flags jsonb, auth_version integer DEFAULT 1,
                    account_status text, created_at timestamptz DEFAULT CURRENT_TIMESTAMP, updated_at timestamptz DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE user_permissions (user_id integer, permission_key text, is_allowed boolean, updated_by integer,
                    created_at timestamptz DEFAULT CURRENT_TIMESTAMP, updated_at timestamptz DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(user_id,permission_key));
                CREATE TABLE role_permissions (role text, permission_key text, is_allowed boolean, updated_by integer,
                    PRIMARY KEY(role,permission_key));
                CREATE TABLE user_inspection_table_scopes (user_id integer, scope_key text, inspection_table_id integer);
                CREATE TABLE user_station_region_scopes (user_id integer, scope_key text, station_region text);
                CREATE TABLE user_password_history (user_id integer, password_hash text, created_at timestamptz);
                CREATE TABLE security_audit_logs (actor_user_id integer, actor_username text, actor_role text,
                    target_user_id integer, target_username text, action_type text, action_result text, failure_reason text,
                    request_ip text, user_agent text, affected_count integer, details jsonb, created_at timestamptz);
            ''')
        conn.close()

    def setUp(self):
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.actor = {'id': 1, 'username': 'root', 'role': 'root'}
        with psycopg2.connect(**self.config) as conn, conn.cursor() as cur:
            cur.execute('''TRUNCATE users,user_permissions,role_permissions,user_inspection_table_scopes,
                user_station_region_scopes,user_password_history,security_audit_logs RESTART IDENTITY;
                INSERT INTO users(username,role,station_id,auth_version) VALUES
                    ('root','root',NULL,1),('sample','supervisor',NULL,1),('area','area_account',NULL,1),('station','station_manager',7,1);
                INSERT INTO user_permissions VALUES (2,'view_expert_qa',TRUE,1),(3,'view_expert_qa',FALSE,1);
                INSERT INTO role_permissions VALUES ('supervisor','view_expert_qa',FALSE,1);
                INSERT INTO user_inspection_table_scopes VALUES (2,'limit_issue_inspection_table_scope',8);
                INSERT INTO user_station_region_scopes VALUES (3,'limit_issue_station_region_scope','浦东管理片区'),
                    (2,'limit_issue_station_region_scope','松金管理片区');''')
        conn.close()
        self.stack.enter_context(patch.object(api, 'get_db_config', return_value=self.config))
        self.stack.enter_context(patch.object(api, 'get_user_by_id', return_value=self.actor))
        self.stack.enter_context(patch.object(api, 'verify_auth_token', return_value=(self.actor, {})))
        self.stack.enter_context(patch.object(api, 'fetch_password_policy', return_value=DEFAULT_PASSWORD_POLICY))
        for name in ('touch_online_user_presence', 'start_backup_scheduler_once', 'ensure_user_security_schema',
                     'ensure_inspection_checklist_management_schema', 'invalidate_auth_caches_for_user'):
            self.stack.enter_context(patch.object(api, name))

    def query(self, statement):
        with psycopg2.connect(**self.config) as conn, conn.cursor() as cur:
            cur.execute(statement); rows = [dict(row) for row in cur.fetchall()]
        conn.close(); return rows

    def call(self, overrides):
        return api.app.test_client().put('/api/management/users/2/permissions',
            json={'permission_overrides': overrides}, headers={'Authorization': 'Bearer test'})

    def test_replace_is_sparse_and_role_template_changes_affect_only_inherited_keys(self):
        self.assertEqual(self.call({'view_expert_qa': False}).status_code, 200)
        self.assertEqual(self.query('SELECT permission_key,is_allowed FROM user_permissions WHERE user_id=2'),
                         [{'permission_key': 'view_expert_qa', 'is_allowed': False}])
        with psycopg2.connect(**self.config) as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO role_permissions VALUES ('supervisor','view_operations_overview',TRUE,1)")
            actual = api.get_effective_permissions(cur, {'id': 2, 'role': 'supervisor'})
            self.assertTrue(actual['view_operations_overview']); self.assertFalse(actual['view_expert_qa'])
        conn.close()
        self.assertEqual(self.call({}).status_code, 200)
        self.assertEqual(self.query('SELECT * FROM user_permissions WHERE user_id=2'), [])

    def test_failed_permission_audit_rolls_back_switches_and_session_version(self):
        with patch.object(api, 'record_security_event', side_effect=RuntimeError('audit unavailable')):
            self.assertEqual(self.call({}).status_code, 500)
        self.assertTrue(self.query('SELECT is_allowed FROM user_permissions WHERE user_id=2')[0]['is_allowed'])
        self.assertEqual(self.query('SELECT auth_version FROM users WHERE id=2')[0]['auth_version'], 1)
        self.assertEqual(self.query('SELECT * FROM security_audit_logs'), [])

    def test_concurrent_permission_edits_serialize_without_mixing_maps(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            replies = list(pool.map(self.call, [{'view_expert_qa': False}, {'view_operations_overview': False}]))
        self.assertEqual([reply.status_code for reply in replies], [200, 200])
        self.assertEqual(len(self.query('SELECT * FROM user_permissions WHERE user_id=2')), 1)
        self.assertEqual(self.query('SELECT auth_version FROM users WHERE id=2')[0]['auth_version'], 3)
        self.assertEqual(len(self.query('SELECT * FROM security_audit_logs')), 2)

    def test_clear_personal_settings_preserves_roles_area_ownership_and_station_binding(self):
        with psycopg2.connect(**self.config) as conn, conn.cursor() as cur:
            summary = clear_personal_permissions(cur, self.actor, apply=True)
        conn.close()
        self.assertEqual(summary['affected_accounts'], 2)
        self.assertEqual(self.query('SELECT * FROM user_permissions'), [])
        self.assertEqual(self.query('SELECT * FROM user_inspection_table_scopes'), [])
        self.assertEqual(self.query('SELECT user_id,station_region FROM user_station_region_scopes'), [{'user_id': 3, 'station_region': '浦东管理片区'}])
        self.assertEqual(self.query('SELECT station_id FROM users WHERE id=4')[0]['station_id'], 7)
        self.assertFalse(self.query('SELECT is_allowed FROM role_permissions')[0]['is_allowed'])
        self.assertEqual(len(self.query('SELECT * FROM security_audit_logs')), 2)

    def test_clear_audit_failure_rolls_back_the_entire_batch(self):
        with self.assertRaises(RuntimeError):
            with psycopg2.connect(**self.config) as conn, conn.cursor() as cur, \
                 patch('user_permission_config.record_security_event', side_effect=RuntimeError('audit unavailable')):
                clear_personal_permissions(cur, self.actor, apply=True)
        conn.close()
        self.assertEqual(len(self.query('SELECT * FROM user_permissions')), 2)
        self.assertEqual(len(self.query('SELECT * FROM user_station_region_scopes')), 2)
        self.assertEqual(self.query('SELECT auth_version FROM users WHERE id=2')[0]['auth_version'], 1)

    def test_create_generated_credentials_are_hashed_forced_change_and_not_audited_in_plaintext(self):
        response = api.app.test_client().post('/api/management/users',
            json={'username': 'new-user', 'real_name': 'New', 'phone': '', 'role': 'supervisor'},
            headers={'Authorization': 'Bearer test'})
        self.assertEqual(response.status_code, 200)
        secret = response.json['credentials'][0]['password']
        row = self.query("SELECT * FROM users WHERE username='new-user'")[0]
        self.assertTrue(verify_password(row['password_hash'], secret))
        self.assertTrue(row['must_change_password']); self.assertTrue(row['force_change_immediately'])
        self.assertEqual(self.query(f"SELECT * FROM user_permissions WHERE user_id={row['id']}"), [])
        self.assertNotIn(secret, str(self.query('SELECT * FROM security_audit_logs')))

    def test_create_audit_failure_does_not_leave_account_or_password_history(self):
        with patch.object(api, 'record_security_event', side_effect=RuntimeError('audit unavailable')):
            response = api.app.test_client().post('/api/management/users',
                json={'username': 'failed-user', 'real_name': 'New', 'role': 'supervisor'}, headers={'Authorization': 'Bearer test'})
        self.assertEqual(response.status_code, 500); self.assertNotIn('credentials', response.json)
        self.assertEqual(self.query("SELECT * FROM users WHERE username='failed-user'"), [])
        self.assertEqual(self.query('SELECT * FROM user_password_history'), [])

    def test_retirement_migration_removes_only_retired_configuration_and_is_repeatable(self):
        path = Path(__file__).resolve().parents[1] / 'migrations/versions/20261017_002_retire_training_peer_pages.py'
        spec = importlib.util.spec_from_file_location('retire_pages_test', path)
        migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
        with psycopg2.connect(**self.config) as conn, conn.cursor() as cur:
            cur.execute('''CREATE TEMP TABLE system_page_visibility (page_key text);
                INSERT INTO system_page_visibility VALUES ('/training'),('/assessment/peer-review'),('/inspection/issues');
                INSERT INTO user_permissions(user_id,permission_key,is_allowed,updated_by) VALUES (2,'view_training',TRUE,1);
                INSERT INTO role_permissions VALUES ('supervisor','view_training',TRUE,1);''')
            with patch.object(migration.op, 'get_bind', return_value=SimpleNamespace(connection=conn)):
                migration.upgrade(); migration.upgrade()
            cur.execute('SELECT page_key FROM system_page_visibility')
            self.assertEqual(cur.fetchone()['page_key'], '/inspection/issues')
            cur.execute("SELECT count(*) AS n FROM user_permissions WHERE permission_key='view_training'")
            self.assertEqual(cur.fetchone()['n'], 0)
            cur.execute("SELECT is_allowed FROM role_permissions WHERE permission_key='view_expert_qa'")
            self.assertFalse(cur.fetchone()['is_allowed'])
            cur.execute('SELECT count(*) AS n FROM users')
            self.assertEqual(cur.fetchone()['n'], 4)
        conn.close()
