"""Configuration HTTP contracts use real temporary JSON, never business files or COS."""
from contextlib import ExitStack
from datetime import datetime
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

import app as api


class BackupConfigurationContractTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.path = self.root / 'config.json'
        self.destination = self.root / 'archives'
        self.stack.enter_context(patch.object(api, 'DEFAULT_BACKUP_DIR', str(self.destination)))
        self.stack.enter_context(patch.object(api, 'BACKUP_CONFIG_PATH', str(self.path)))
        self.stack.enter_context(patch.object(api, 'beijing_now', return_value=datetime(2026, 10, 16, 10, tzinfo=api.BEIJING_TZ)))
        self.user = dict(id=17, username='manager', role='supervisor')
        self.conn, self.cur = MagicMock(), MagicMock()
        self.conn.cursor.return_value = self.cur
        self.get_db = self.stack.enter_context(patch.object(api, 'get_db_connection', return_value=self.conn))
        self.get_user = self.stack.enter_context(patch.object(api, 'get_user_by_id', return_value=self.user))
        self.permission = self.stack.enter_context(patch.object(api, 'can_manage_system', return_value=True))
        self.stack.enter_context(patch.object(api, 'verify_auth_token', return_value=(self.user, {})))
        self.stack.enter_context(patch.object(api, 'touch_online_user_presence'))
        self.stack.enter_context(patch.object(api, 'start_backup_scheduler_once'))
        self.cos = self.stack.enter_context(patch.object(api, 'get_cos_backup_overview', return_value=({'configured': False}, [])))
        self.cleanup = self.stack.enter_context(patch.object(api, 'cleanup_local_backup_files'))
        for name in ('create_full_backup_archive', 'restore_full_backup_archive', 'run_backup_subprocess',
                     'upload_backup_archive_to_cos', 'list_cos_backup_objects'):
            self.stack.enter_context(patch.object(api, name, side_effect=AssertionError('unsafe operation: ' + name)))
        self.client = api.app.test_client()

    def call(self, method='GET', authenticated=True, **data):
        return self.client.open('/api/management/backups' + ('/config' if method == 'PUT' else ''),
                                method=method, headers={'Authorization': 'Bearer test'} if authenticated else {},
                                **({'json': data} if method == 'PUT' else {'query_string': data}))

    def test_get_preserves_response_schema_options_and_does_not_save(self):
        response = self.call()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, dict(success=True, config={**api.get_default_backup_config(),
                            'next_run_at': None, 'cos': {'configured': False}},
                            frequency_options=[{'value': value, 'label': label} for value, label in (
                                ('off', '关闭自动备份'), ('hourly', '每小时'), ('daily', '每天'), ('weekly', '每周'), ('monthly', '每月'))],
                            latest_backups=[], latest_cos_backups=[]))
        self.assertFalse(self.path.exists())
        self.conn.commit.assert_not_called(); self.conn.rollback.assert_not_called()
        self.cur.close.assert_called_once(); self.conn.close.assert_called_once()

    def test_authentication_permission_and_actor_mismatch_cannot_read_or_write(self):
        for method in ('GET', 'PUT'):
            with self.subTest(method=method):
                self.assertEqual(self.call(method, authenticated=False).status_code, 401)
                self.permission.return_value = False
                response = self.call(method)
                self.assertEqual((response.status_code, response.json),
                                 (403, {'success': False, 'error': '当前账号无权操作管理系统。'}))
                self.permission.return_value = True
                self.assertEqual(self.call(method, user_id='18').status_code, 403)
        self.cos.assert_not_called(); self.cleanup.assert_not_called()
        self.assertFalse(self.path.exists()); self.assertFalse(self.destination.exists())

    def test_missing_user_and_lookup_errors_keep_404(self):
        self.get_user.return_value = None
        for method in ('GET', 'PUT'):
            response = self.call(method)
            self.assertEqual((response.status_code, response.json), (404, {'success': False, 'error': '用户不存在。'}))
        self.assertFalse(self.path.exists())

    def test_validation_keeps_errors_and_precedes_database_access(self):
        for data, message in (({'frequency': 'bad'}, '自动备份频率不正确。'),
                              ({'scheduled_time': '2:5'}, '自动备份执行时间必须是 HH:MM 格式。'),
                              ({'scheduled_time': '24:00'}, '自动备份执行时间小时必须在 00-23 之间。')):
            response = self.call('PUT', **data)
            self.assertEqual((response.status_code, response.json), (400, {'success': False, 'error': message}))
        self.get_db.assert_not_called(); self.assertFalse(self.destination.exists())

    def test_put_writes_before_old_directory_cleanup_and_preserves_metadata(self):
        api.write_backup_config({'last_status': 'warning', 'last_error': 'old', 'custom': 'keep'})
        new = self.root / 'new'

        def cleaned(previous):
            self.assertEqual(previous, str(self.destination))
            self.assertEqual(json.loads(self.path.read_text())['destination_path'], str(new))
            self.assertFalse((new / '.ywddzx_backup_write_test').exists())
            self.assertFalse(self.conn.close.called)

        self.cleanup.side_effect = cleaned
        response = self.call('PUT', destination_path=str(new), frequency='daily', scheduled_time='1:30')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['message'], '备份设置已保存。')
        config = json.loads(self.path.read_text())
        self.assertEqual(response.json['config'], {**config, 'next_run_at': '2026-10-17T01:30:00+08:00', 'cos': {'configured': False}})
        self.assertEqual((config['last_status'], config['last_error'], config['custom']), ('warning', 'old', 'keep'))
        self.assertEqual(config['updated_at'], '2026-10-16T10:00:00+08:00')
        self.assertEqual(config['next_auto_run_at'], response.json['config']['next_run_at'])
        self.cleanup.assert_called_once_with(str(self.destination))
        self.conn.commit.assert_not_called(); self.conn.rollback.assert_not_called()
        self.conn.close.assert_called_once(); self.cur.close.assert_called_once()

    def test_same_destination_keeps_files_and_off_clears_next_run(self):
        self.destination.mkdir()
        archive = self.destination / (api.BACKUP_PREFIX + 'test.zip')
        archive.write_bytes(b'test')
        response = self.call('PUT', frequency='off')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json['config']['next_run_at'])
        self.assertEqual(response.json['latest_backups'][0]['size'], 4)
        self.assertEqual(response.json['latest_backups'][0]['path'], str(archive))
        self.cleanup.assert_not_called(); self.assertEqual(archive.read_bytes(), b'test')

    def test_config_validation_and_write_failures_never_cleanup_previous_directory(self):
        api.write_backup_config({})
        before = self.path.read_bytes()
        with patch.object(api, 'write_backup_config', side_effect=OSError('disk full')):
            response = self.call('PUT', destination_path=str(self.root / 'new'))
        self.assertEqual((response.status_code, response.json), (400, {'success': False, 'error': '备份目录不可写：disk full'}))
        self.assertEqual(self.path.read_bytes(), before)
        self.cleanup.assert_not_called(); self.cos.assert_not_called()
        self.conn.close.assert_called_once()
        self.path.write_text('{"scheduled_time":"invalid"}')
        self.assertEqual(self.call().status_code, 500)
        self.assertEqual(self.call('PUT').status_code, 400)

    def test_cleanup_failure_remains_after_saved_config_not_rolled_back(self):
        self.cleanup.side_effect = RuntimeError('cleanup failed')
        response = self.call('PUT', destination_path=str(self.root / 'new'))
        self.assertEqual((response.status_code, response.json), (500, {'success': False, 'error': 'cleanup failed'}))
        self.assertEqual(json.loads(self.path.read_text())['destination_path'], str(self.root / 'new'))
        self.cos.assert_not_called(); self.conn.close.assert_called_once()

    def test_config_update_does_not_acquire_existing_job_lock(self):
        # Characterize the existing concurrency boundary, not an endorsement of it.
        lock = threading.Lock()
        with patch.object(api, 'backup_job_lock', lock), lock:
            self.assertEqual(self.call('PUT').status_code, 200)
            self.assertTrue(lock.locked())
