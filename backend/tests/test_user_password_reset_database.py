"""Opt-in real transactions on a disposable database, never the application database."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import json
import os
import unittest
from unittest.mock import patch

import psycopg2
from psycopg2.extensions import parse_dsn

import app as api
from account_security import hash_password, verify_password
from security_service import DEFAULT_PASSWORD_POLICY


@unittest.skipUnless(os.environ.get('USER_PASSWORD_RESET_TEST_DSN'), 'isolated password-reset database not configured')
class UserPasswordResetDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = parse_dsn(os.environ['USER_PASSWORD_RESET_TEST_DSN'])
        if not cls.config.get('dbname', '').startswith('test_user_password_reset_'):
            raise RuntimeError('Refusing non-test database')
        with psycopg2.connect(**cls.config) as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    CREATE TABLE stations (id integer PRIMARY KEY, hos_station_code text);
                    CREATE TABLE users (
                        id integer PRIMARY KEY, username text, role text, real_name text, phone text,
                        password_hash text, station_id integer, account_status text, auth_version integer,
                        must_change_password boolean DEFAULT false, force_change_immediately boolean DEFAULT false,
                        password_changed_at timestamptz, password_policy_version integer,
                        password_risk_flags jsonb DEFAULT '[]', updated_at timestamptz
                    );
                    CREATE TABLE user_password_history (id serial PRIMARY KEY, user_id integer, password_hash text, created_at timestamptz);
                    CREATE TABLE security_audit_logs (
                        id serial PRIMARY KEY, actor_user_id integer, actor_username text, actor_role text,
                        target_user_id integer, target_username text, action_type text, action_result text,
                        failure_reason text, request_ip text, user_agent text, affected_count integer,
                        details jsonb, created_at timestamptz
                    );
                ''')
        conn.close()
        cls.old_hash = hash_password('PreviousCompliantPassword!27')

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        with psycopg2.connect(**self.config) as conn:
            with conn.cursor() as cur:
                cur.execute('TRUNCATE users, user_password_history, security_audit_logs RESTART IDENTITY')
                cur.execute("INSERT INTO users (id,username,role,phone,password_hash,account_status,auth_version) VALUES (2,'staff','supervisor','',%s,'active',7)", (self.old_hash,))
        conn.close()
        actor = dict(id=1, username='root', role='root')
        self.stack.enter_context(patch.object(api, 'get_db_config', return_value=self.config))
        self.stack.enter_context(patch.object(api, 'get_user_by_id', return_value=actor))
        self.stack.enter_context(patch.object(api, 'verify_auth_token', return_value=(actor, {})))
        self.stack.enter_context(patch.object(api, 'fetch_password_policy', return_value=DEFAULT_PASSWORD_POLICY))
        for name in ('touch_online_user_presence', 'start_backup_scheduler_once', 'ensure_user_security_schema', 'invalidate_auth_caches_for_user'):
            self.stack.enter_context(patch.object(api, name))

    def call(self):
        return api.app.test_client().post('/api/management/users/2/reset-password', json={}, headers={'Authorization': 'Bearer test'})

    def stored(self):
        with psycopg2.connect(**self.config) as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT password_hash, auth_version, must_change_password, force_change_immediately, account_status FROM users WHERE id=2')
                user = cur.fetchone()
                cur.execute('SELECT actor_user_id,target_user_id,action_type,details FROM security_audit_logs ORDER BY id')
                logs = cur.fetchall()
                cur.execute('SELECT count(*) FROM user_password_history')
                history = cur.fetchone()[0]
        conn.close()
        return user, logs, history

    def test_success_hashes_random_password_forces_change_and_audits_without_plaintext(self):
        response = self.call()
        self.assertEqual(response.status_code, 200)
        password = response.json['credentials'][0]['password']
        user, logs, history = self.stored()
        self.assertNotEqual(user[0], password)
        self.assertTrue(verify_password(user[0], password))
        self.assertFalse(verify_password(user[0], 'PreviousCompliantPassword!27'))
        self.assertEqual(user[1:], (8, True, True, 'active'))
        self.assertEqual(history, 1)
        self.assertEqual(logs[0][:3], (1, 2, 'administrator_password_reset'))
        self.assertNotIn(password, json.dumps(logs))
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_audit_failure_rolls_back_hash_session_version_and_history(self):
        with patch.object(api, 'record_security_event', side_effect=RuntimeError('audit failed')):
            self.assertEqual(self.call().status_code, 500)
        user, logs, history = self.stored()
        self.assertEqual(user[:2], (self.old_hash, 7))
        self.assertEqual(user[2:4], (False, False))
        self.assertEqual((logs, history), ([], 0))

    def test_concurrent_resets_serialize_and_preserve_both_audits(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(lambda _: self.call(), range(2)))
        self.assertEqual([response.status_code for response in responses], [200, 200])
        passwords = [response.json['credentials'][0]['password'] for response in responses]
        self.assertNotEqual(*passwords)
        user, logs, history = self.stored()
        self.assertEqual(user[1], 9)
        self.assertEqual((len(logs), history), (2, 2))
        self.assertEqual(sum(verify_password(user[0], password) for password in passwords), 1)
