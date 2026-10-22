"""Real account save transactions in a disposable namespace; no real users or credentials."""
import os
import json
from io import BytesIO
from pathlib import Path
import unittest
import uuid
from unittest.mock import patch
from contextlib import ExitStack

from flask import Flask
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.extensions import parse_dsn


@unittest.skipUnless(os.environ.get('USER_DRIVING_TEST_DSN'), 'isolated database opt-in')
class UserDrivingDatabaseTests(unittest.TestCase):
    def connect(self):
        return psycopg2.connect(self.dsn, options='-c search_path=' + self.schema, cursor_factory=RealDictCursor)

    def setUp(self):
        import app as api
        self.api = api
        self.dsn = os.environ['USER_DRIVING_TEST_DSN']
        if not parse_dsn(self.dsn).get('dbname', '').startswith('test_'):
            raise RuntimeError('Refusing non-test database')
        self.schema = 'user_driving_' + uuid.uuid4().hex
        with psycopg2.connect(self.dsn) as conn, conn.cursor() as cur:
            cur.execute('CREATE SCHEMA ' + self.schema)
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute('''CREATE TABLE users(id serial PRIMARY KEY,username text UNIQUE,password_hash text,role text,
              real_name text,phone text,station_id int,must_change_password boolean,force_change_immediately boolean,
              password_policy_version int,password_risk_flags jsonb,auth_version int,account_status text,
              created_at timestamp,updated_at timestamp);
              CREATE TABLE stations(id int,hos_station_code text,station_name text);
              CREATE TABLE user_permissions(user_id int,permission_key text,is_allowed boolean);
              CREATE TABLE user_birthdays(real_name text,birthday_month int,birthday_day int);
              CREATE TABLE user_password_history(id serial,user_id int,password_hash text,created_at timestamp);
              CREATE TABLE security_audit_logs(id serial,actor_user_id int,actor_username text,actor_role text,
                target_user_id int,target_username text,action_type text,action_result text,failure_reason text,
                request_ip text,user_agent text,affected_count int,details jsonb,created_at timestamp);''')
            cur.execute((Path(__file__).parents[1] / 'db/init/555_user_driving_permits.sql').read_text())
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.actor = dict(id=1, role='root', username='root')
        self.stack.enter_context(patch.object(api, 'get_db_connection', self.connect))
        self.stack.enter_context(patch.object(api, 'require_management_user', return_value=self.actor))
        self.stack.enter_context(patch.object(api, 'fetch_password_policy', return_value={}))
        self.stack.enter_context(patch.object(api, 'generate_strong_initial_password', return_value='fake-test-password'))
        self.stack.enter_context(patch.object(api, 'validate_and_hash_password', return_value=('fake-hash', {})))
        for name in ('ensure_inspection_checklist_management_schema', 'ensure_user_security_schema',
                     'apply_user_permission_updates', 'apply_user_inspection_table_scope_updates',
                     'apply_user_station_region_scope_updates', 'invalidate_auth_caches_for_user'):
            self.stack.enter_context(patch.object(api, name))
        for name in ('get_permission_overrides', 'get_effective_permissions', 'get_user_inspection_table_scope_overrides',
                     'get_user_station_region_scope_overrides', 'get_role_permission_overrides_map',
                     'get_role_inspection_table_scope_overrides_map', 'get_role_station_region_scope_overrides_map'):
            self.stack.enter_context(patch.object(api, name, return_value={}))
        app = Flask(__name__)
        app.add_url_rule('/users', view_func=api.create_management_user, methods=['POST'])
        app.add_url_rule('/users/<int:target_user_id>', view_func=api.update_management_user, methods=['PUT'])
        app.add_url_rule('/export', view_func=api.export_management_users)
        app.add_url_rule('/import', view_func=api.import_management_users, methods=['POST'])
        self.client = app.test_client()

    def tearDown(self):
        with psycopg2.connect(self.dsn) as conn, conn.cursor() as cur:
            cur.execute('DROP SCHEMA ' + self.schema + ' CASCADE')

    def create(self, **extra):
        return self.client.post('/users', json=dict(username='driver', role='supervisor', real_name='测试人员', **extra))

    def stored(self, uid):
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute('SELECT has_driving_permit FROM users WHERE id=%s', (uid,))
            return cur.fetchone()['has_driving_permit']

    def test_default_create_update_preserve_old_client_and_role_change(self):
        response = self.create()
        self.assertEqual(response.status_code, 200, response.json)
        uid = response.json['id']; self.assertFalse(self.stored(uid))
        body = dict(username='driver', role='supervisor_manager', real_name='测试人员', has_driving_permit=True)
        self.assertEqual(self.client.put('/users/'+str(uid), json=body).status_code, 200)
        self.assertTrue(self.stored(uid))
        body.pop('has_driving_permit')
        self.assertEqual(self.client.put('/users/'+str(uid), json=body).status_code, 200)
        self.assertTrue(self.stored(uid))
        self.assertEqual(self.client.put('/users/'+str(uid), json={**body,'role':'quality_safety'}).status_code, 200)
        self.assertFalse(self.stored(uid))
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT details FROM security_audit_logs WHERE action_type='user_driving_permit_update' ORDER BY id")
            self.assertEqual([r['details'] for r in cur.fetchall()], [dict(before=False,after=True),dict(before=True,after=False)])

    def test_permission_denial_invalid_boolean_and_audit_failure_never_save_qualification(self):
        with patch.object(self.api, 'require_management_user', side_effect=PermissionError('无权限')):
            self.assertEqual(self.create(has_driving_permit=True).status_code, 403)
        self.assertEqual(self.create(has_driving_permit='false').status_code, 400)
        response = self.create(); uid = response.json['id']
        with patch.object(self.api, 'record_security_event', side_effect=RuntimeError('test audit failure')):
            response = self.client.put('/users/'+str(uid), json=dict(username='driver',role='supervisor',real_name='测试人员',has_driving_permit=True))
        self.assertEqual(response.status_code, 500)
        self.assertFalse(self.stored(uid))

    def test_user_backup_roundtrip_and_legacy_omission_preserve_qualification(self):
        response = self.create(has_driving_permit=True)
        self.assertEqual(response.status_code, 200, response.json)
        uid = response.json['id']
        exported = self.client.get('/export')
        self.assertEqual(exported.status_code, 200, exported.json)
        self.assertIs(exported.json['users'][0]['has_driving_permit'], True)
        payload = exported.json
        payload['users'][0]['has_driving_permit'] = False
        def restore():
            return self.client.post('/import', data={'file': (BytesIO(json.dumps(payload).encode()), 'users.json')})
        response = restore()
        self.assertEqual(response.status_code, 200, response.json)
        self.assertFalse(self.stored(uid))
        payload['users'][0]['has_driving_permit'] = True
        self.assertEqual(restore().status_code, 200)
        payload['users'][0].pop('has_driving_permit')
        self.assertEqual(restore().status_code, 200)
        self.assertTrue(self.stored(uid))
