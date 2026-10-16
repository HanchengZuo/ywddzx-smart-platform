"""Exercise real upload/ZIP validation while replacing all destructive restore work."""
from contextlib import ExitStack
from io import BytesIO
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch
import zipfile

from werkzeug.datastructures import FileStorage

import app as api


class BackupRestoreValidationContractTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        original_temporary_directory = tempfile.TemporaryDirectory
        self.stack.enter_context(patch.object(api.tempfile, 'TemporaryDirectory',
                                             side_effect=lambda: original_temporary_directory(dir=self.root)))
        self.stack.enter_context(patch.object(api, 'STORAGE_ROOT', str(self.root / 'storage')))
        self.stack.enter_context(patch.object(api, 'DEFAULT_BACKUP_DIR', str(self.root / 'archives')))
        self.stack.enter_context(patch.object(api, 'BACKUP_CONFIG_PATH', str(self.root / 'config.json')))
        self.events = []
        self.database = self.stack.enter_context(patch.object(api, 'restore_database_from_backup', side_effect=self.database_restored))
        self.original_restore_storage = api.restore_storage_from_backup
        self.storage = self.stack.enter_context(patch.object(api, 'restore_storage_from_backup', side_effect=self.storage_restored))
        self.connect = self.stack.enter_context(patch.object(api, 'get_db_connection', side_effect=AssertionError('unexpected DB access')))
        for name in ('run_backup_subprocess', 'build_pg_environment', 'clear_storage_root_for_restore',
                     'ensure_required_storage_dirs', 'upload_backup_archive_to_cos'):
            self.stack.enter_context(patch.object(api, name, side_effect=AssertionError('unsafe operation: ' + name)))
        self.lock = threading.Lock()
        self.stack.enter_context(patch.object(api, 'backup_job_lock', self.lock))
        self.manifest = dict(backup_type='ywddzx_full_backup', version=2, note='keep')
        self.database_bytes = b'not a real database backup'

    def zip_bytes(self, extras=(), manifest=None, database='database.dump'):
        stream = BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('manifest.json', json.dumps(self.manifest if manifest is None else manifest))
            archive.writestr(database, self.database_bytes)
            for name, content in extras:
                archive.writestr(name, content)
        return stream.getvalue()

    def upload(self, data, filename='backup.zip'):
        return FileStorage(stream=BytesIO(data), filename=filename)

    def database_restored(self, path, member, temp_dir):
        self.assertEqual(Path(path).read_bytes(), self.database_bytes)
        self.assertEqual(Path(path).parent, Path(temp_dir))
        self.assertEqual(Path(temp_dir).parent, self.root)
        self.events.append(('database', member, Path(path)))

    def storage_restored(self, path):
        self.assertEqual(self.events[0][:2], ('database', 'database.dump'))
        self.assertTrue(Path(path).is_file())
        self.events.append(('storage', Path(path)))

    def prepare_http(self):
        user = dict(id=17, username='manager', role='supervisor')
        self.conn, self.cur = MagicMock(), MagicMock()
        self.conn.cursor.return_value = self.cur
        self.connect.side_effect = None
        self.connect.return_value = self.conn
        self.stack.enter_context(patch.object(api, 'get_user_by_id', return_value=user))
        self.permission = self.stack.enter_context(patch.object(api, 'can_manage_system', return_value=True))
        self.stack.enter_context(patch.object(api, 'verify_auth_token', return_value=(user, {})))
        self.stack.enter_context(patch.object(api, 'touch_online_user_presence'))
        self.stack.enter_context(patch.object(api, 'start_backup_scheduler_once'))
        self.http = api.app.test_client()

    def call(self, data, filename='backup.zip', authenticated=True):
        return self.http.post('/api/management/backups/import',
                              headers={'Authorization': 'Bearer test'} if authenticated else {},
                              data={'file': (BytesIO(data), filename)})

    def test_missing_upload_filename_and_wrong_extension_fail_before_restoration(self):
        for upload, message in ((None, '请选择需要导入的完整备份文件。'),
                                (self.upload(b'', ''), '请选择需要导入的完整备份文件。'),
                                (self.upload(b'', 'backup.sql'), '完整备份只支持导入 ZIP 文件。')):
            with self.subTest(message=message), self.assertRaises(ValueError) as error:
                api.restore_full_backup_archive(upload)
            self.assertEqual(str(error.exception), message)
        self.database.assert_not_called(); self.storage.assert_not_called()

    def test_valid_archive_checks_then_restores_database_before_storage_and_removes_temporary_files(self):
        manifest = {**self.manifest, 'database_member': '../../untrusted.sql'}
        result = api.restore_full_backup_archive(self.upload(self.zip_bytes(manifest=manifest), 'BACKUP.ZIP'))
        self.assertEqual(result, {**self.manifest, 'database_member': 'database.dump'})
        self.assertEqual([event[0] for event in self.events], ['database', 'storage'])
        self.assertTrue(all(not event[-1].exists() for event in self.events))
        self.assertFalse((self.root / 'storage').exists())
        self.connect.assert_not_called()

    def test_legacy_sql_upload_selects_sql_without_running_any_database_command(self):
        self.storage.side_effect = None
        result = api.restore_full_backup_archive(self.upload(self.zip_bytes(database='database.sql')))
        self.assertEqual(result['database_member'], 'database.sql')
        self.assertEqual(self.events[0][1], 'database.sql')
        self.storage.assert_called_once()

    def test_traversal_is_rejected_before_database_or_storage_restoration(self):
        with self.assertRaises(ValueError) as error:
            api.restore_full_backup_archive(self.upload(self.zip_bytes(extras=[('storage/../escape', 'bad')])))
        self.assertEqual(str(error.exception), '备份文件中存在非法 storage 路径。')
        self.database.assert_not_called(); self.storage.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_database_failure_does_not_start_storage_restore_or_keep_temporary_files(self):
        self.database.side_effect = RuntimeError('database substitute failed')
        with self.assertRaisesRegex(RuntimeError, 'database substitute failed'):
            api.restore_full_backup_archive(self.upload(self.zip_bytes()))
        self.storage.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_storage_failure_follows_database_and_does_not_retry_or_compensate(self):
        self.storage.side_effect = RuntimeError('storage substitute failed')
        with self.assertRaisesRegex(RuntimeError, 'storage substitute failed'):
            api.restore_full_backup_archive(self.upload(self.zip_bytes()))
        self.database.assert_called_once(); self.storage.assert_called_once()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_storage_restore_validates_before_destructive_clear(self):
        path = self.root / 'bad-storage.zip'
        path.write_bytes(self.zip_bytes(extras=[('storage/../escape', 'bad')]))
        with self.assertRaisesRegex(ValueError, '备份文件中存在非法 storage 路径。'):
            self.original_restore_storage(path)

    def test_http_authentication_and_permission_denial_do_not_validate_or_restore(self):
        self.prepare_http()
        with patch.object(api, 'validate_backup_archive', side_effect=AssertionError('must not validate')):
            self.assertEqual(self.call(self.zip_bytes(), authenticated=False).status_code, 401)
            self.permission.return_value = False
            self.assertEqual(self.call(self.zip_bytes()).status_code, 403)
        self.database.assert_not_called(); self.storage.assert_not_called()
        self.assertFalse(self.lock.locked())

    def test_http_invalid_archives_preserve_error_mapping_config_and_release_lock(self):
        self.prepare_http()
        api.write_backup_config({'last_status': 'previous', 'last_error': 'preserve'})
        before = (self.root / 'config.json').read_bytes()
        for data, status, error in (
            (b'not a ZIP', 400, '备份文件不是有效的 ZIP 文件。'),
            (self.zip_bytes(extras=[('storage/../../escape', '')]), 400, '备份文件中存在非法 storage 路径。'),
            (self.zip_bytes(manifest=[]), 500, "'list' object has no attribute 'get'"),
        ):
            response = self.call(data)
            self.assertEqual((response.status_code, response.json), (status, {'success': False, 'error': error}))
            self.assertEqual((self.root / 'config.json').read_bytes(), before)
            self.assertFalse(self.lock.locked())
        self.database.assert_not_called(); self.storage.assert_not_called()
        response = self.call(self.zip_bytes())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, dict(success=True, message='完整备份已导入，数据库与上传文件目录已恢复。',
                                            manifest={**self.manifest, 'database_member': 'database.dump'}))
        self.assertFalse(self.lock.locked())
        self.assertEqual(api.read_backup_config()['last_status'], 'success')

    def test_http_restore_failures_do_not_update_config_and_always_release_lock(self):
        self.prepare_http()
        api.write_backup_config({'last_status': 'previous'})
        before = (self.root / 'config.json').read_bytes()
        for operation in (self.database, self.storage):
            original_effect = operation.side_effect
            operation.side_effect = RuntimeError('restore substitute failed')
            try:
                response = self.call(self.zip_bytes())
                self.assertEqual((response.status_code, response.json),
                                 (500, {'success': False, 'error': 'restore substitute failed'}))
                self.assertFalse(self.lock.locked())
                self.assertEqual((self.root / 'config.json').read_bytes(), before)
            finally:
                operation.side_effect = original_effect
