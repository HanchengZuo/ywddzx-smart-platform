"""Characterization of existing manual backup endpoints, with no real transfer operations."""
from contextlib import ExitStack
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

from flask import g, request

import app as api


class BackupTransferContractTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.temp = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.archive = self.temp / 'archive.zip'
        self.archive.write_bytes(b'test archive bytes')
        self.user = dict(id=17, username='manager', role='supervisor')
        self.events = []
        self.lock = threading.Lock()
        self.conn, self.cur = MagicMock(), MagicMock()
        self.conn.cursor.return_value = self.cur
        self.cur.close.side_effect = lambda: self.events.append('cursor.close')
        self.conn.close.side_effect = lambda: self.events.append('connection.close')
        self.config = dict(destination_path=str(self.temp), frequency='off', last_error='previous')
        self.result = dict(path=str(self.archive), download_filename='备份.zip', size=self.archive.stat().st_size,
                           cos=dict(status='success', key='cloud/archive.zip', uploaded_at='2026-10-16T10:00:00+08:00', retained_count=1))
        self.manifest = dict(backup_type='ywddzx_full_backup', version=2)
        self.get_db = self.stack.enter_context(patch.object(api, 'get_db_connection', return_value=self.conn))
        self.get_user = self.stack.enter_context(patch.object(api, 'get_user_by_id', return_value=self.user))
        self.permission = self.stack.enter_context(patch.object(api, 'can_manage_system', return_value=True))
        self.stack.enter_context(patch.object(api, 'verify_auth_token', side_effect=lambda _: (self.user, {})))
        self.stack.enter_context(patch.object(api, 'touch_online_user_presence'))
        self.stack.enter_context(patch.object(api, 'start_backup_scheduler_once'))
        self.stack.enter_context(patch.object(api, 'backup_job_lock', self.lock))
        self.read = self.stack.enter_context(patch.object(api, 'read_backup_config', side_effect=self.read_config))
        self.write = self.stack.enter_context(patch.object(api, 'write_backup_config', side_effect=self.write_config))
        self.create = self.stack.enter_context(patch.object(api, 'create_full_backup_archive', side_effect=self.create_archive))
        self.restore = self.stack.enter_context(patch.object(api, 'restore_full_backup_archive', side_effect=self.restore_archive))
        # Defense in depth: a regression must not run commands, touch COS or restore real files.
        for name in ('run_backup_subprocess', 'upload_backup_archive_to_cos', 'restore_database_from_backup',
                     'restore_storage_from_backup', 'cleanup_local_backup_files'):
            self.stack.enter_context(patch.object(api, name, side_effect=AssertionError('unsafe test operation: ' + name)))
        self.client = api.app.test_client()

    def read_config(self):
        self.events.append(('read', self.lock.locked()))
        return deepcopy(self.config)

    def write_config(self, config):
        self.events.append(('write', self.lock.locked()))
        self.config = deepcopy(config)
        return config

    def create_archive(self, destination, reason):
        self.events.append(('create', self.lock.locked()))
        self.assertEqual(self.events[:2], ['cursor.close', 'connection.close'])
        self.assertEqual((destination, reason), (str(self.temp), 'manual'))
        return deepcopy(self.result)

    def restore_archive(self, file):
        self.events.append(('restore', self.lock.locked()))
        self.assertEqual(self.events[:2], ['cursor.close', 'connection.close'])
        self.assertEqual(file.filename, 'upload.zip')
        self.assertEqual(file.read(), b'upload')
        return self.manifest

    def call(self, kind, authenticated=True, **kwargs):
        headers = {'Authorization': 'Bearer test-token'} if authenticated else {}
        if kind == 'import':
            return self.client.post('/api/management/backups/import', headers=headers,
                                    data={'file': (BytesIO(b'upload'), 'upload.zip')}, **kwargs)
        return self.client.post('/api/management/backups/export', headers=headers, json=kwargs.pop('json', {}), **kwargs)

    def test_authentication_permission_and_actor_identity_remain_mandatory(self):
        for kind in ('export', 'import'):
            with self.subTest(kind=kind):
                self.assertEqual(self.call(kind, authenticated=False).status_code, 401)
                self.get_db.assert_not_called()
                self.permission.return_value = False
                response = self.call(kind)
                self.assertEqual((response.status_code, response.json),
                                 (403, {'success': False, 'error': '当前账号无权操作管理系统。'}))
                self.create.assert_not_called(); self.restore.assert_not_called()
                self.read.assert_not_called(); self.write.assert_not_called()
                self.permission.return_value = True
                self.get_db.reset_mock()
        response = self.call('export', json={'user_id': '18'})
        self.assertEqual(response.status_code, 403)
        self.get_db.assert_not_called()

    def test_missing_management_user_is_404_and_does_not_start_work(self):
        self.get_user.return_value = None
        for kind in ('export', 'import'):
            response = self.call(kind)
            self.assertEqual((response.status_code, response.json), (404, {'success': False, 'error': '用户不存在。'}))
        self.create.assert_not_called(); self.restore.assert_not_called()

    def test_export_closes_authorization_transaction_before_lock_and_preserves_download(self):
        response = self.call('export')
        self.addCleanup(response.close)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.archive.read_bytes())
        self.assertEqual(response.mimetype, 'application/zip')
        self.assertIn("filename*=UTF-8''", response.headers['Content-Disposition'])
        self.assertEqual({key: response.headers[key] for key in ('X-Backup-Path', 'X-Backup-Size', 'X-COS-Backup-Status', 'X-COS-Backup-Key', 'Cache-Control')},
                         {'X-Backup-Path': str(self.archive), 'X-Backup-Size': str(self.result['size']),
                          'X-COS-Backup-Status': 'success', 'X-COS-Backup-Key': 'cloud/archive.zip', 'Cache-Control': 'no-store'})
        self.assertEqual(self.events, ['cursor.close', 'connection.close', ('read', True), ('create', True), ('write', True)])
        self.assertFalse(self.lock.locked())
        self.assertEqual(self.config['last_status'], 'success')
        self.assertEqual(self.config['last_cos_retained_count'], 1)
        self.conn.commit.assert_not_called(); self.conn.rollback.assert_not_called()

    def test_cos_warning_and_unconfigured_status_are_not_http_failures(self):
        self.result['cos'] = dict(status='error', message='COS 上传失败：test failure')
        response = self.call('export'); self.addCleanup(response.close)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['X-COS-Backup-Status'], 'error')
        self.assertEqual(self.config['last_status'], 'warning')
        self.assertEqual(self.config['last_error'], 'COS 上传失败：test failure')
        self.result['cos'] = {}
        response = self.call('export'); self.addCleanup(response.close)
        self.assertEqual(response.headers['X-COS-Backup-Status'], 'not_configured')
        self.assertEqual(response.headers['X-COS-Backup-Key'], '')

    def test_import_releases_lock_before_config_update_and_preserves_response(self):
        response = self.call('import')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, dict(success=True, message='完整备份已导入，数据库与上传文件目录已恢复。', manifest=self.manifest))
        self.assertEqual(self.events, ['cursor.close', 'connection.close', ('restore', True), ('read', False), ('write', False)])
        self.assertFalse(self.lock.locked())
        self.assertEqual(self.config['last_error'], '')

    def test_busy_lock_returns_409_without_reading_configuration_or_starting_work(self):
        self.lock.acquire()
        try:
            for kind in ('export', 'import'):
                response = self.call(kind)
                self.assertEqual((response.status_code, response.json),
                                 (409, {'success': False, 'error': '已有备份或恢复任务正在执行，请稍后再试。'}))
                self.assertTrue(self.lock.locked())
            self.read.assert_not_called(); self.write.assert_not_called()
            self.create.assert_not_called(); self.restore.assert_not_called()
        finally:
            self.lock.release()

    def test_import_busy_does_not_parse_upload_in_the_endpoint(self):
        self.lock.acquire()
        try:
            with api.app.test_request_context('/api/management/backups/import', method='POST',
                    data={'file': (BytesIO(b'upload'), 'upload.zip')}):
                g.current_user = self.user
                response, status = api.import_management_full_backup()
                self.assertEqual(status, 409)
                self.assertNotIn('files', request.__dict__)
                self.assertNotIn('form', request.__dict__)
                self.assertFalse(response.json['success'])
        finally:
            self.lock.release()

    def test_missing_export_file_is_500_after_config_saved_and_lock_released(self):
        self.result['path'] = str(self.temp / 'missing.zip')
        response = self.call('export')
        self.assertEqual(response.status_code, 500)
        self.write.assert_called_once()
        self.assertFalse(self.lock.locked())

    def test_scheduled_backup_observes_the_same_busy_lock_as_manual_transfers(self):
        self.config.update(frequency='hourly', next_auto_run_at='2000-01-01T00:00:00+08:00')
        self.lock.acquire()
        try:
            api.maybe_run_scheduled_backup()
            self.create.assert_not_called()
            self.write.assert_not_called()
        finally:
            self.lock.release()

    def test_export_exception_categories_release_lock_and_preserve_errors(self):
        for failure, status in [(PermissionError('permission'), 403), (LookupError('missing'), 404),
                                (ValueError('invalid'), 500), (RuntimeError('failed'), 500), (OSError('disk'), 500)]:
            with self.subTest(failure=failure):
                self.create.side_effect = failure
                response = self.call('export')
                self.assertEqual((response.status_code, response.json), (status, {'success': False, 'error': str(failure)}))
                self.assertFalse(self.lock.locked())
        self.write.assert_not_called()

    def test_import_exception_categories_release_lock_and_do_not_update_config(self):
        for failure, status in [(ValueError('invalid ZIP'), 400), (RuntimeError('restore failed'), 500),
                                (PermissionError('permission'), 403), (LookupError('missing'), 404), (OSError('disk'), 500)]:
            with self.subTest(failure=failure):
                self.restore.side_effect = failure
                response = self.call('import')
                self.assertEqual((response.status_code, response.json), (status, {'success': False, 'error': str(failure)}))
                self.assertFalse(self.lock.locked())
        self.read.assert_not_called(); self.write.assert_not_called()

    def test_config_write_failure_keeps_completed_operation_order_and_releases_lock(self):
        self.write.side_effect = OSError('config failed')
        response = self.call('export')
        self.assertEqual((response.status_code, response.json), (500, {'success': False, 'error': 'config failed'}))
        self.assertFalse(self.lock.locked())
        self.assertTrue(self.archive.exists())
        self.events.clear()
        response = self.call('import')
        self.assertEqual(response.status_code, 500)
        self.assertIn(('restore', True), self.events)
        self.assertIn(('read', False), self.events)
        self.assertFalse(self.lock.locked())


if __name__ == '__main__':
    unittest.main()
