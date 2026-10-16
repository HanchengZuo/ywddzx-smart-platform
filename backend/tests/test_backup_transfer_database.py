"""Opt-in transaction tests. Refuse any database not explicitly named for these tests."""
from contextlib import ExitStack
from io import BytesIO
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import psycopg2
from psycopg2.extensions import parse_dsn

import app as api


@unittest.skipUnless(os.environ.get('BACKUP_TRANSFER_TEST_DSN'), 'isolated backup-transfer database not configured')
class BackupTransferDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = parse_dsn(os.environ['BACKUP_TRANSFER_TEST_DSN'])
        if not cls.config.get('dbname', '').startswith('test_backup_transfer_'):
            raise RuntimeError('Refusing non-test database')
        with psycopg2.connect(**cls.config) as conn:
            with conn.cursor() as cur:
                cur.execute('CREATE TABLE IF NOT EXISTS authorization_probe(actor_id text)')
        conn.close()

    def probe_count(self):
        conn = psycopg2.connect(**self.config)
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT COUNT(*) FROM authorization_probe')
                return cur.fetchone()[0]
        finally:
            conn.close()

    def exercise(self, kind, denied=False, archive_failure=False):
        user = dict(id=17, role='supervisor', username='test-manager')
        opened = []
        original_connect = api.get_db_connection

        def connect():
            conn = original_connect()
            opened.append(conn)
            return conn

        def authorize(cur, user_id, permission):
            self.assertEqual(permission, 'manage_backups')
            cur.execute("SELECT current_setting('app.actor_id') AS actor_id")
            self.assertEqual(cur.fetchone()['actor_id'], '17')
            # Simulate uncommitted work during authorization: close, not a new commit, must undo it.
            cur.execute("INSERT INTO authorization_probe VALUES ('17')")
            if denied:
                raise PermissionError('denied')

        def archive(*args, **kwargs):
            self.assertTrue(opened and all(conn.closed for conn in opened))
            self.assertEqual(self.probe_count(), 0)
            if archive_failure:
                raise RuntimeError('archive failed')
            return dict(path=str(path), size=path.stat().st_size, download_filename='test.zip') if kind == 'export' else {'version': 2}

        with ExitStack() as stack:
            directory = stack.enter_context(tempfile.TemporaryDirectory())
            path = Path(directory) / 'test.zip'
            path.write_bytes(b'temporary test archive')
            stack.enter_context(patch.object(api, 'get_db_config', return_value=self.config))
            stack.enter_context(patch.object(api, 'get_db_connection', side_effect=connect))
            stack.enter_context(patch.object(api, 'verify_auth_token', return_value=(user, {})))
            stack.enter_context(patch.object(api, 'touch_online_user_presence'))
            stack.enter_context(patch.object(api, 'start_backup_scheduler_once'))
            stack.enter_context(patch.object(api, 'backup_job_lock', threading.Lock()))
            stack.enter_context(patch.object(api, 'require_management_user', side_effect=authorize))
            stack.enter_context(patch.object(api, 'read_backup_config', return_value={}))
            stack.enter_context(patch.object(api, 'write_backup_config'))
            operation = stack.enter_context(patch.object(api, 'create_full_backup_archive' if kind == 'export' else 'restore_full_backup_archive', side_effect=archive))
            for name in ('run_backup_subprocess', 'upload_backup_archive_to_cos', 'restore_storage_from_backup'):
                stack.enter_context(patch.object(api, name, side_effect=AssertionError('unsafe test operation')))
            try:
                with api.app.test_client() as client:
                    params = {'data': {'file': (BytesIO(b'test'), 'test.zip')}} if kind == 'import' else {'json': {}}
                    response = client.post('/api/management/backups/' + kind,
                                           headers={'Authorization': 'Bearer test'}, **params)
                    try:
                        self.assertEqual(response.status_code, 403 if denied else 500 if archive_failure else 200)
                    finally:
                        response.close()
                self.assertTrue(opened and all(conn.closed for conn in opened))
                self.assertEqual(self.probe_count(), 0)
                self.assertEqual(operation.call_count, 0 if denied else 1)
            finally:
                for conn in opened:
                    conn.close()

    def test_authorization_transaction_closes_and_rolls_back_before_success_or_failure(self):
        for kind in ('export', 'import'):
            for failure in (False, True):
                with self.subTest(kind=kind, failure=failure):
                    self.exercise(kind, archive_failure=failure)

    def test_permission_denial_closes_and_rolls_back_without_starting_transfer(self):
        for kind in ('export', 'import'):
            with self.subTest(kind=kind):
                self.exercise(kind, denied=True)

    def test_configuration_authorization_transactions_close_and_roll_back(self):
        user = dict(id=17, role='supervisor', username='test-manager')
        original_connect = api.get_db_connection
        for method in ('GET', 'PUT'):
            for outcome in ('success', 'denied', 'overview_failure'):
                with self.subTest(method=method, outcome=outcome), ExitStack() as stack:
                    root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
                    opened = []

                    def connect():
                        conn = original_connect()
                        opened.append(conn)
                        return conn

                    def authorize(cur, user_id, permission):
                        self.assertEqual(permission, 'manage_backups')
                        cur.execute("SELECT current_setting('app.actor_id') AS actor_id")
                        self.assertEqual(cur.fetchone()['actor_id'], '17')
                        cur.execute("INSERT INTO authorization_probe VALUES ('17')")
                        if outcome == 'denied':
                            raise PermissionError('denied')

                    def overview(config):
                        self.assertTrue(opened and all(not conn.closed for conn in opened))
                        self.assertEqual(self.probe_count(), 0)
                        if outcome == 'overview_failure':
                            raise RuntimeError('overview failed')
                        return {}, []

                    stack.enter_context(patch.object(api, 'get_db_config', return_value=self.config))
                    stack.enter_context(patch.object(api, 'get_db_connection', side_effect=connect))
                    stack.enter_context(patch.object(api, 'verify_auth_token', return_value=(user, {})))
                    stack.enter_context(patch.object(api, 'touch_online_user_presence'))
                    stack.enter_context(patch.object(api, 'start_backup_scheduler_once'))
                    stack.enter_context(patch.object(api, 'require_management_user', side_effect=authorize))
                    stack.enter_context(patch.object(api, 'DEFAULT_BACKUP_DIR', str(root / 'archives')))
                    stack.enter_context(patch.object(api, 'BACKUP_CONFIG_PATH', str(root / 'config.json')))
                    stack.enter_context(patch.object(api, 'get_cos_backup_overview', side_effect=overview))
                    for name in ('run_backup_subprocess', 'upload_backup_archive_to_cos',
                                 'cleanup_local_backup_files', 'create_full_backup_archive', 'restore_full_backup_archive'):
                        stack.enter_context(patch.object(api, name, side_effect=AssertionError('unsafe operation')))
                    try:
                        params = {'json': {}} if method == 'PUT' else {}
                        response = api.app.test_client().open(
                            '/api/management/backups' + ('/config' if method == 'PUT' else ''),
                            method=method, headers={'Authorization': 'Bearer test'}, **params)
                        self.addCleanup(response.close)
                        self.assertEqual(response.status_code, {'success': 200, 'denied': 403, 'overview_failure': 500}[outcome])
                        self.assertTrue(opened and all(conn.closed for conn in opened))
                        self.assertEqual(self.probe_count(), 0)
                        # A later response failure has never undone an already saved JSON file.
                        self.assertEqual((root / 'config.json').exists(), method == 'PUT' and outcome != 'denied')
                    finally:
                        for conn in opened:
                            conn.close()
