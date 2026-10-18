import copy
import importlib.util
import os
import tempfile
import threading
import time
import unittest
import uuid
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

import app as api
import issue_export_cache as cache
import issue_export_download as grants


class ExportFingerprintTests(unittest.TestCase):
    def test_order_is_stable_but_rows_columns_photos_options_and_redaction_invalidate(self):
        rows = [dict(id=11, description='接地锈蚀', inspector='检查人'), dict(id=12, description='渗漏')]
        options = api.normalize_issue_export_options({'include_fields': {'id': True, 'description': True}})
        fields = {1: [dict(field_label='检查事项')]}
        key = cache.fingerprint(rows, options, fields, lambda _: None)
        self.assertEqual(key, cache.fingerprint(list(reversed(rows)), options, fields, lambda _: None))
        for changed in ([rows[0]], [dict(rows[0], description='已更新'), rows[1]],
                        [dict(rows[0], inspector=''), rows[1]]):
            self.assertNotEqual(key, cache.fingerprint(changed, options, fields, lambda _: None))
        changed = copy.deepcopy(options); changed['photo_mode'] = 'embedded'
        self.assertNotEqual(key, cache.fingerprint(rows, changed, fields, lambda _: None))
        self.assertNotEqual(key, cache.fingerprint(rows, options, {1: []}, lambda _: None))
        with tempfile.TemporaryDirectory() as root:
            photo = Path(root) / 'photo.png'; photo.write_bytes(b'one')
            rows[0]['issue_photo'] = str(photo)
            options['include_photos']['issue_photo'] = True
            key = cache.fingerprint(rows, options, fields, lambda path: path)
            photo.write_bytes(b'two new bytes')
            self.assertNotEqual(key, cache.fingerprint(rows, options, fields, lambda path: path))
            photo.unlink()
            self.assertNotEqual(key, cache.fingerprint(rows, options, fields, lambda path: path))

    def test_grants_bind_task_expiry_identity_and_signature(self):
        identity = dict(uid=17, av=2, role='area_account', username='test', exp=10000, imp_uid=1, imp_av=3)
        token = grants.mint('test-secret', identity, 'one-task', 100)
        payload = grants.unwrap('test-secret', token, 'one-task', 101)
        self.assertEqual(payload['exp'], 1900)
        self.assertEqual(payload['imp_av'], 3)
        self.assertEqual(identity['exp'], 10000)
        for secret, value, task, now in [('wrong', token, 'one-task', 101),
                                        ('test-secret', token+'x', 'one-task', 101),
                                        ('test-secret', token, 'other-task', 101),
                                        ('test-secret', token, 'one-task', 1900)]:
            with self.assertRaises(PermissionError): grants.unwrap(secret, value, task, now)
        with self.assertRaises(PermissionError): grants.mint('test-secret', dict(uid=17, exp=99), 'one-task', 100)


class NativeDownloadTests(unittest.TestCase):
    def test_grant_uses_narrow_cookie_and_native_download_supports_ranges_and_current_auth(self):
        with tempfile.TemporaryDirectory() as root, ExitStack() as stack:
            file = Path(root) / 'test.xlsx'; file.write_bytes(b'0123456789')
            user = dict(id=17, username='test', role='area_account')
            payload = dict(uid=17, av=1, role='area_account', username='test', exp=int(time.time())+3600)
            task = dict(status='completed', created_by=17, file_path=str(file), download_filename='中文导出.xlsx')
            stack.enter_context(patch.object(api, 'start_backup_scheduler_once'))
            verify = stack.enter_context(patch.object(api, 'verify_auth_token', return_value=(user, payload)))
            stack.enter_context(patch.object(api, 'touch_online_user_presence'))
            stack.enter_context(patch.object(api, 'get_db_connection', return_value=MagicMock()))
            stack.enter_context(patch.object(api, 'get_user_by_id', return_value=user))
            stack.enter_context(patch.object(api, 'get_issue_export_task_for_user', return_value=task))
            stack.enter_context(patch.object(api, 'resolve_storage_abs_path', side_effect=lambda path: path))
            client = api.app.test_client()
            url = '/api/issues/export-tasks/task-one/download'
            link = client.post(url+'-link', headers={'Authorization': 'Bearer test'})
            self.assertEqual(link.status_code, 200)
            cookie = link.headers['Set-Cookie']
            self.assertIn('HttpOnly', cookie); self.assertIn('SameSite=Strict', cookie)
            self.assertIn('Path='+url, cookie)
            self.assertNotIn('test?', link.get_json()['download_url'])
            response = client.get(url, headers={'Range': 'bytes=2-5'})
            self.assertEqual(response.status_code, 206)
            self.assertEqual(response.data, b'2345')
            self.assertEqual(response.headers['Content-Length'], '4')
            self.assertEqual(response.headers['Content-Range'], 'bytes 2-5/10')
            self.assertIn('attachment;', response.headers['Content-Disposition'])
            self.assertIn('ETag', response.headers)
            response.close()
            self.assertEqual(client.get(url, headers={'Range': 'bytes=100-200'}).status_code, 416)
            self.assertEqual(client.get(url.rsplit('/', 1)[0]).status_code, 401)
            # A current account/session revocation still wins over an otherwise valid download cookie.
            verify.side_effect = PermissionError('登录已过期')
            self.assertEqual(client.get(url).status_code, 401)

    def test_download_rechecks_visibility_and_hidden_contacts(self):
        task = dict(status='completed', issue_ids=[1, 2], export_options={'include_fields': {'inspector': True}}, file_path='file')
        cursor = MagicMock()
        with patch.object(api, 'build_issue_list_visibility_scope', return_value=(['i.station_id=%s'], [3])):
            cursor.fetchall.return_value = [dict(id=1)]
            with self.assertRaises(PermissionError): api.require_issue_export_download_access(cursor, task, {'id': 17})
            cursor.fetchall.return_value = [dict(id=1), dict(id=2)]
            with patch.object(api, 'should_hide_inspector_contact_info', return_value=True):
                with self.assertRaises(PermissionError): api.require_issue_export_download_access(cursor, task, {'id': 17})


@unittest.skipUnless(os.getenv('ISSUE_EXPORT_DB_TEST') == '1', 'dedicated disposable PostgreSQL database required')
class ExportCacheDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.schema = 'export_cache_'+uuid.uuid4().hex
        self.connect = api.get_db_connection
        conn = self.connect(); cur = conn.cursor()
        cur.execute(f'CREATE SCHEMA {self.schema}; SET search_path TO {self.schema}')
        cur.execute('CREATE TABLE users(id int PRIMARY KEY); INSERT INTO users VALUES(17),(18)')
        api.ensure_issue_export_schema(cur); conn.commit(); cur.close(); conn.close()
        self.root = tempfile.TemporaryDirectory()
        self.directory = Path(self.root.name) / 'issue_exports'; self.directory.mkdir()
        self.rows = [dict(id=11, description='问题甲', inspection_table_id=1, inspection_table_name='测试表'),
                     dict(id=12, description='问题乙', inspection_table_id=1, inspection_table_name='测试表')]
        self.stack = ExitStack()
        self.stack.enter_context(patch.object(api, 'get_db_connection', side_effect=self.connection))
        self.stack.enter_context(patch.object(api, 'get_user_by_id', side_effect=lambda cur, id: dict(id=int(id), role='supervisor', username='test')))
        self.stack.enter_context(patch.object(api, 'fetch_issue_export_rows', side_effect=lambda *args: copy.deepcopy(self.rows)))
        self.stack.enter_context(patch.object(api, 'build_issue_export_table_field_map', return_value={1: []}))
        self.stack.enter_context(patch.object(api, 'should_hide_inspector_contact_info', return_value=False))
        self.stack.enter_context(patch.object(api, 'ISSUE_EXPORTS_STORAGE_DIR', str(self.directory)))
        self.stack.enter_context(patch.object(api, 'resolve_storage_abs_path', side_effect=self.resolve))
        self.stack.enter_context(patch.object(api, 'remove_storage_file', side_effect=self.remove))
        self.start = self.stack.enter_context(patch.object(api, 'start_issue_export_task'))
        self.options = api.normalize_issue_export_options({'include_fields': {'id': True, 'description': True}})

    def tearDown(self):
        self.stack.close()
        conn = self.connect(); cur = conn.cursor()
        cur.execute(f'DROP SCHEMA {self.schema} CASCADE'); conn.commit(); cur.close(); conn.close()
        self.root.cleanup()

    def connection(self):
        conn = self.connect(); cur = conn.cursor()
        cur.execute(f'SET search_path TO {self.schema}'); conn.commit(); cur.close()
        return conn

    def resolve(self, path):
        return str(Path(self.root.name) / path) if path else None

    def remove(self, path):
        Path(self.resolve(path)).unlink(missing_ok=True)

    def create(self, user=17, options=None):
        with api.app.test_request_context('/api/issues/export-tasks', method='POST', json={
                'user_id': user, 'issue_ids': [11, 12], 'export_options': options or self.options}):
            result = api.create_issue_export_task()
            self.assertNotIsInstance(result, tuple, result)
            return result.get_json()['task']

    def task(self, id):
        conn = self.connection(); cur = conn.cursor()
        try:
            return dict(api.get_issue_export_task_for_user(cur, id, dict(id=1, role='root')))
        finally:
            cur.close(); conn.close()

    def test_cross_user_reuse_is_owned_separately_and_content_changes_miss(self):
        first = self.create()
        api.run_issue_export_task(first['task_id'], [11,12], 17, self.options)
        original = self.task(first['task_id'])
        self.assertEqual(original['status'], 'completed')
        second = self.create(18)
        self.assertEqual(second['status'], 'completed')
        self.assertTrue(second['cache_reused'])
        reused = self.task(second['task_id'])
        self.assertEqual(reused['file_path'], original['file_path'])
        self.assertEqual(reused['expires_at'], original['expires_at'])
        self.assertEqual(reused['created_by'], 18)
        self.assertEqual(self.start.call_count, 1)
        conn = self.connection(); cur = conn.cursor()
        with self.assertRaises(PermissionError): api.get_issue_export_task_for_user(cur, first['task_id'], dict(id=18, role='area_account'))
        cur.close(); conn.close()
        self.rows[0]['description'] = '修改后的问题'
        self.assertEqual(self.create(18)['status'], 'pending')
        self.rows[0]['description'] = '问题甲'
        self.assertEqual(self.create(18, dict(self.options, photo_mode='embedded'))['status'], 'pending')
        Path(self.resolve(original['file_path'])).unlink()
        self.assertEqual(self.create()['status'], 'pending')

    def test_simultaneous_workers_render_once_and_cleanup_does_not_delete_live_shared_file(self):
        first, second = self.create(), self.create(18)
        writer = api.write_issue_export_xlsx
        def slow_write(*args):
            time.sleep(.1); return writer(*args)
        with patch.object(api, 'write_issue_export_xlsx', side_effect=slow_write) as render:
            threads = [threading.Thread(target=api.run_issue_export_task, args=(task['task_id'], [11,12], user, self.options))
                       for task, user in ((first,17),(second,18))]
            for thread in threads: thread.start()
            for thread in threads: thread.join(10); self.assertFalse(thread.is_alive())
            self.assertEqual(render.call_count, 1)
        first, second = self.task(first['task_id']), self.task(second['task_id'])
        self.assertEqual([first['status'],second['status']], ['completed','completed'])
        self.assertEqual(first['file_path'],second['file_path'])
        conn = self.connection(); cur = conn.cursor()
        cur.execute("UPDATE issue_export_tasks SET expires_at=CURRENT_TIMESTAMP-INTERVAL '1 day' WHERE task_id=%s", (first['task_id'],))
        api.cleanup_expired_issue_exports(cur); conn.commit()
        self.assertTrue(Path(self.resolve(second['file_path'])).exists())
        cur.execute("UPDATE issue_export_tasks SET expires_at=CURRENT_TIMESTAMP-INTERVAL '1 day'")
        cur.execute("UPDATE issue_export_artifacts SET expires_at=CURRENT_TIMESTAMP-INTERVAL '1 day'")
        api.cleanup_expired_issue_exports(cur); conn.commit()
        self.assertFalse(Path(self.resolve(second['file_path'])).exists())
        cur.close(); conn.close()

    def test_failed_render_rolls_back_artifact_and_partial_file_then_can_retry(self):
        task = self.create()
        def fail(path, *args):
            Path(path).write_bytes(b'partial'); raise RuntimeError('test render failure')
        with patch.object(api, 'write_issue_export_xlsx', side_effect=fail):
            api.run_issue_export_task(task['task_id'], [11,12], 17, self.options)
        self.assertEqual(self.task(task['task_id'])['status'], 'failed')
        self.assertEqual(list(self.directory.iterdir()), [])
        conn = self.connection(); cur = conn.cursor()
        cur.execute('SELECT count(*) AS n FROM issue_export_artifacts'); self.assertEqual(cur.fetchone()['n'], 0)
        cur.close(); conn.close()
        next_task = self.create()
        api.run_issue_export_task(next_task['task_id'], [11,12], 17, self.options)
        self.assertEqual(self.task(next_task['task_id'])['status'], 'completed')

    def test_cleanup_yields_to_a_generation_transaction_and_schema_is_repeatable(self):
        conn = self.connection(); cur = conn.cursor()
        cache.lock_artifact(cur, 'a'*64)
        other = self.connection(); other_cur = other.cursor()
        with patch.object(api, 'remove_storage_file') as remove:
            api.cleanup_expired_issue_exports(other_cur)
            remove.assert_not_called()
        other.rollback(); other_cur.close(); other.close()
        conn.rollback()
        api.ensure_issue_export_schema(cur); api.ensure_issue_export_schema(cur)
        conn.commit(); cur.close(); conn.close()

    def test_migration_is_idempotent_and_preserves_existing_task(self):
        task = self.create()
        path = Path(__file__).parents[1] / 'migrations/versions/20261018_002_issue_export_artifacts.py'
        spec = importlib.util.spec_from_file_location('export_artifact_migration', path)
        migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
        conn = self.connection(); cur = conn.cursor()
        with patch.object(migration.op, 'execute', side_effect=cur.execute):
            migration.upgrade(); migration.upgrade()
        conn.commit(); cur.close(); conn.close()
        self.assertEqual(self.task(task['task_id'])['created_by'], 17)
        self.assertEqual(self.task(task['task_id'])['status'], 'pending')

    def test_expired_artifact_is_not_reused_even_when_live_old_task_keeps_file(self):
        task = self.create()
        api.run_issue_export_task(task['task_id'], [11,12], 17, self.options)
        original = self.task(task['task_id'])
        conn = self.connection(); cur = conn.cursor()
        cur.execute("UPDATE issue_export_artifacts SET expires_at=CURRENT_TIMESTAMP-INTERVAL '1 second'")
        conn.commit(); cur.close(); conn.close()
        self.assertEqual(self.create(18)['status'], 'pending')
        self.assertTrue(Path(self.resolve(original['file_path'])).exists())
