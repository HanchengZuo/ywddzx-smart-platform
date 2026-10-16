"""Characterize the COS boundary with SDK doubles and disposable local files only."""
from contextlib import ExitStack
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, call, patch

import app as api


class CosBackupAdapterTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.archive = self.root / 'test.zip'
        self.archive.write_bytes(b'temporary archive')
        self.size = self.archive.stat().st_size
        self.filename = api.BACKUP_PREFIX + '_new.zip'
        self.key = 'test-backups/' + self.filename
        self.old_key = 'test-backups/' + api.BACKUP_PREFIX + '_old.zip'
        self.stack.enter_context(patch.dict(api.os.environ, {
            'COS_SECRET_ID': ' test-secret-id ', 'COS_SECRET_KEY': ' test-secret-key ',
            'COS_REGION': ' test-region ', 'COS_BUCKET': ' test-bucket ', 'COS_USE_INTERNAL': 'false',
        }))
        self.stack.enter_context(patch.object(api, 'COS_BACKUP_PREFIX', 'test-backups'))
        self.stack.enter_context(patch.object(api, 'COS_BACKUP_RETENTION_COUNT', 1))
        self.client = MagicMock()
        self.config_factory = self.stack.enter_context(patch.object(api, 'CosConfig', return_value=object()))
        self.client_factory = self.stack.enter_context(patch.object(api, 'CosS3Client', return_value=self.client))
        self.now = datetime(2026, 10, 16, 12, tzinfo=api.BEIJING_TZ)
        self.clock = self.stack.enter_context(patch.object(api, 'beijing_now', return_value=self.now))
        self.new_object = dict(Key=self.key, Size=str(self.size), LastModified='2026-10-16T04:00:00Z', ETag='"new-etag"')
        self.old_object = dict(Key=self.old_key, Size='5', LastModified='2026-10-15T04:00:00Z', ETag='"old-etag"')
        self.client.list_objects.return_value = dict(Contents=[self.old_object, self.new_object], IsTruncated=False)
        self.client.head_object.return_value = {'Content-Length': str(self.size)}

    def upload(self):
        return api.upload_backup_archive_to_cos(str(self.archive), self.filename)

    def test_environment_values_are_trimmed_and_read_on_each_call(self):
        config = api.get_cos_env_config()
        self.assertEqual(config, dict(secret_id='test-secret-id', secret_key='test-secret-key',
            region='test-region', bucket='test-bucket', prefix='test-backups/', configured=True,
            sdk_available=True, retention_count=1, use_internal=False))
        api.os.environ['COS_BUCKET'] = 'changed'
        self.assertEqual(api.get_cos_env_config()['bucket'], 'changed')
        with patch.object(api, 'COS_BACKUP_PREFIX', ''):
            self.assertEqual(api.get_cos_env_config()['prefix'], '')
        self.config_factory.assert_not_called(); self.client_factory.assert_not_called()

    def test_internal_domain_flag_keeps_existing_case_and_whitespace_semantics(self):
        for value, enabled in (('TRUE', True), ('1', True), ('yes', True), (' true ', False), ('0', False)):
            api.os.environ['COS_USE_INTERNAL'] = value
            client, config = api.get_cos_client()
            self.assertIs(client, self.client)
            self.assertEqual(config['use_internal'], enabled)
            self.config_factory.assert_called_with(Region='test-region', SecretId='test-secret-id',
                SecretKey='test-secret-key', Scheme='https', EnableOldDomain=not enabled, EnableInternalDomain=enabled)
            self.client_factory.assert_called_with(self.config_factory.return_value)

    def test_public_status_preserves_metadata_without_exposing_credentials(self):
        metadata = dict(last_cos_status='error', last_cos_key='old-key', last_cos_uploaded_at='saved',
                        last_cos_error='previous failure', last_cos_retained_count=1)
        before = deepcopy(metadata)
        result = api.get_cos_public_status(metadata)
        self.assertEqual(result, dict(status='ready', message='COS 环境变量已配置，备份会自动上传对象存储。',
            configured=True, sdk_available=True, bucket='test-bucket', region='test-region',
            prefix='test-backups/', retention_count=1, **metadata))
        self.assertEqual(metadata, before)
        self.assertNotIn('test-secret', json.dumps(result))
        self.assertEqual(api.get_cos_public_status(error='list failed')['message'], 'list failed')

    def test_missing_environment_or_sdk_keeps_error_precedence_and_does_not_construct_client(self):
        with patch.object(api, 'CosConfig', None):
            self.assertEqual(api.get_cos_public_status(error='ignored')['message'], '后端缺少腾讯云 COS Python SDK，请重新安装依赖。')
            with self.assertRaises(RuntimeError) as error:
                api.get_cos_client()
            self.assertEqual(str(error.exception), '后端缺少腾讯云 COS Python SDK，请重新安装依赖。')
            self.assertEqual(self.upload(), dict(status='error', message='后端缺少腾讯云 COS Python SDK，请重新安装依赖。'))
            api.os.environ['COS_BUCKET'] = ' '
            self.assertEqual(api.get_cos_public_status(error='ignored')['status'], 'not_configured')
            self.assertEqual(api.get_cos_public_status()['bucket'], '')
            self.assertEqual(api.get_cos_public_status()['region'], '')
            with self.assertRaises(RuntimeError) as error:
                api.get_cos_client()
            self.assertEqual(str(error.exception), '未配置 COS_SECRET_ID、COS_SECRET_KEY、COS_REGION 或 COS_BUCKET。')
            self.assertEqual(self.upload(), dict(status='not_configured', message='未配置 COS 环境变量，已跳过云端上传。'))
        self.client_factory.assert_not_called(); self.client.upload_file.assert_not_called()

    def test_missing_client_class_is_also_sdk_unavailable(self):
        with patch.object(api, 'CosS3Client', None):
            self.assertFalse(api.get_cos_env_config()['sdk_available'])
        self.config_factory.assert_not_called()

    def test_client_constructor_errors_propagate_for_direct_calls_and_are_wrapped_for_upload(self):
        self.config_factory.side_effect = RuntimeError('bad SDK config')
        with self.assertRaisesRegex(RuntimeError, 'bad SDK config'):
            api.get_cos_client()
        self.assertEqual(self.upload(), dict(status='error', message='COS 上传失败：bad SDK config'))
        self.client.upload_file.assert_not_called()

    def test_timestamp_parsing_preserves_timezone_and_invalid_fallback(self):
        for value in ('2026-10-16T04:00:00Z', '2026-10-16T12:00:00+08:00'):
            self.assertEqual(api.parse_cos_last_modified(value), self.now)
        self.assertEqual(api.parse_cos_last_modified('2026-10-16T04:00:00.123Z').microsecond, 123000)
        for value in (None, '', 'invalid'):
            self.assertEqual(api.parse_cos_last_modified(value), datetime.min.replace(tzinfo=api.BEIJING_TZ))

    def test_list_paginates_filters_normalizes_and_sorts(self):
        self.client.list_objects.side_effect = [
            dict(Contents=[self.old_object, dict(Key='test-backups/not-a-backup.zip')], IsTruncated='TRUE', NextMarker='next'),
            dict(Contents=self.new_object, IsTruncated='1', Marker='fallback'),
            dict(Contents=[dict(Key=self.key + '.tmp'), dict(Key='folder/')], IsTruncated=False),
        ]
        self.assertEqual(api.list_cos_backup_objects(), [
            dict(key=self.key, filename=self.filename, size=self.size, updated_at=self.now.isoformat(), etag='new-etag'),
            dict(key=self.old_key, filename=self.old_key.split('/')[-1], size=5,
                 updated_at='2026-10-15T12:00:00+08:00', etag='old-etag'),
        ])
        self.assertEqual(self.client.list_objects.call_args_list, [
            call(Bucket='test-bucket', Prefix='test-backups/', Marker=marker, MaxKeys=1000)
            for marker in ('', 'next', 'fallback')])
        self.client_factory.assert_called_once()

    def test_list_stops_when_truncated_page_has_no_marker(self):
        self.client.list_objects.return_value = dict(Contents=None, IsTruncated=True)
        self.assertEqual(api.list_cos_backup_objects(), [])
        self.client.list_objects.assert_called_once()

    def test_list_missing_fields_and_equal_timestamps_keep_stable_input_order(self):
        first = dict(Key=self.old_key)
        second = dict(Key=self.key, Size='0', LastModified='invalid')
        self.client.list_objects.return_value = dict(Contents=[first, second, {}])
        rows = api.list_cos_backup_objects()
        self.assertEqual([row['key'] for row in rows], [self.old_key, self.key])
        self.assertEqual((rows[0]['size'], rows[0]['etag']), (0, ''))

    def test_list_failures_propagate_without_deletion(self):
        self.client.list_objects.return_value = dict(Contents=[dict(Key=self.key, Size='bad')])
        with self.assertRaises(ValueError):
            api.list_cos_backup_objects()
        self.client.list_objects.side_effect = RuntimeError('listing failed')
        with self.assertRaisesRegex(RuntimeError, 'listing failed'):
            api.list_cos_backup_objects()
        self.client.delete_object.assert_not_called()

    def test_prune_supplied_rows_preserves_order_and_does_not_relist(self):
        rows = [dict(key=self.key), dict(key=self.old_key), dict(key='third')]
        before = deepcopy(rows)
        self.assertEqual(api.prune_cos_backup_objects(rows), (rows[:1], rows[1:]))
        self.assertEqual(rows, before)
        self.assertEqual(self.client.delete_object.call_args_list, [
            call(Bucket='test-bucket', Key=self.old_key), call(Bucket='test-bucket', Key='third')])
        self.client.list_objects.assert_not_called()
        self.client_factory.assert_called_once()

    def test_prune_empty_rows_still_constructs_client_but_does_not_list(self):
        self.assertEqual(api.prune_cos_backup_objects([]), ([], []))
        self.client_factory.assert_called_once(); self.client.list_objects.assert_not_called()

    def test_prune_without_supplied_rows_uses_new_listing_client(self):
        kept, removed = api.prune_cos_backup_objects()
        self.assertEqual([row['key'] for row in kept], [self.key])
        self.assertEqual([row['key'] for row in removed], [self.old_key])
        self.assertEqual(self.client_factory.call_count, 2)

    def test_prune_failure_is_not_hidden_or_retried(self):
        self.client.delete_object.side_effect = RuntimeError('cannot delete')
        with self.assertRaisesRegex(RuntimeError, 'cannot delete'):
            api.prune_cos_backup_objects([dict(key=self.key), dict(key=self.old_key), dict(key='third')])
        self.client.delete_object.assert_called_once_with(Bucket='test-bucket', Key=self.old_key)

    def test_upload_result_and_sdk_sequence_remain_exact(self):
        result = self.upload()
        self.assertEqual(result, dict(status='success', message='COS 上传成功，云端已保留最近 1 个备份。',
            key=self.key, bucket='test-bucket', region='test-region', uploaded_at=self.now.isoformat(),
            retained_count=1, removed_count=1))
        self.assertEqual(self.client.mock_calls, [
            call.upload_file(Bucket='test-bucket', Key=self.key, LocalFilePath=str(self.archive),
                             PartSize=16, MAXThread=2, EnableMD5=True),
            call.head_object(Bucket='test-bucket', Key=self.key),
            call.list_objects(Bucket='test-bucket', Prefix='test-backups/', Marker='', MaxKeys=1000),
            call.delete_object(Bucket='test-bucket', Key=self.old_key),
        ])
        self.assertEqual(self.client_factory.call_count, 3)
        self.clock.assert_called_once_with()

    def test_upload_checks_size_then_listing_before_any_deletion(self):
        for metadata in ({}, {'Content-Length': '1'}, {'Content-Length': 'invalid'}):
            with self.subTest(metadata=metadata):
                self.client.head_object.return_value = metadata
                result = self.upload()
                self.assertEqual(result['status'], 'error')
                self.assertTrue(result['message'].startswith('COS 上传失败：'))
                self.client.list_objects.assert_not_called(); self.client.delete_object.assert_not_called()
        self.client.head_object.return_value = {'Content-Length': str(self.size)}
        for item in (self.old_object, {**self.new_object, 'Size': '1'}):
            self.client.list_objects.return_value = dict(Contents=[item])
            self.assertEqual(self.upload(), dict(status='error', message='COS 上传失败：云端列表尚未确认新备份，旧备份未清理。'))
        self.client.delete_object.assert_not_called(); self.clock.assert_not_called()

    def test_local_file_failure_never_uploads_or_deletes(self):
        self.archive.unlink()
        result = self.upload()
        self.assertEqual(result['status'], 'error')
        self.assertIn('COS 上传失败：', result['message'])
        self.client.upload_file.assert_not_called(); self.client.delete_object.assert_not_called()

    def test_upload_and_head_and_listing_failures_never_delete(self):
        for operation in ('upload_file', 'head_object', 'list_objects'):
            with self.subTest(operation=operation), patch.object(self.client, operation, side_effect=RuntimeError(operation + ' failed')):
                self.assertEqual(self.upload(), dict(status='error', message='COS 上传失败：' + operation + ' failed'))
                self.client.delete_object.assert_not_called()

    def test_delete_failure_returns_error_after_upload_without_success_timestamp(self):
        self.client.delete_object.side_effect = RuntimeError('cannot delete')
        self.assertEqual(self.upload(), dict(status='error', message='COS 上传失败：cannot delete'))
        self.client.upload_file.assert_called_once(); self.clock.assert_not_called()

    def test_partial_prune_failure_keeps_completed_deletions_without_retry_or_compensation(self):
        older = {**self.old_object, 'Key': 'test-backups/' + api.BACKUP_PREFIX + '_older.zip',
                 'LastModified': '2026-10-14T04:00:00Z'}
        self.client.list_objects.return_value = dict(Contents=[older, self.old_object, self.new_object])
        self.client.delete_object.side_effect = [None, RuntimeError('second delete failed')]
        self.assertEqual(self.upload(), dict(status='error', message='COS 上传失败：second delete failed'))
        self.assertEqual(self.client.delete_object.call_args_list, [
            call(Bucket='test-bucket', Key=self.old_key), call(Bucket='test-bucket', Key=older['Key'])])
        self.client.upload_file.assert_called_once(); self.clock.assert_not_called()

    def test_overview_limits_results_and_turns_list_error_into_public_status(self):
        metadata = dict(last_cos_key='saved-key', last_cos_error='saved error')
        status, rows = api.get_cos_backup_overview(metadata)
        self.assertEqual(status['status'], 'ready')
        self.assertEqual([row['key'] for row in rows], [self.key])
        self.client.delete_object.assert_not_called()
        self.client.list_objects.side_effect = RuntimeError('listing failed')
        status, rows = api.get_cos_backup_overview(metadata)
        self.assertEqual(rows, [])
        self.assertEqual((status['status'], status['message']), ('error', 'COS 备份列表读取失败：listing failed'))
        self.assertEqual(status['last_cos_key'], 'saved-key')
        self.assertEqual(status['last_cos_error'], 'saved error')
        self.assertNotIn('test-secret', json.dumps(status))

    def test_overview_without_environment_or_sdk_does_not_construct_client(self):
        for name in ('COS_SECRET_ID', 'COS_SECRET_KEY', 'COS_REGION', 'COS_BUCKET'):
            with patch.dict(api.os.environ, {name: ''}):
                self.assertEqual(api.get_cos_backup_overview()[1], [])
        with patch.object(api, 'CosS3Client', None):
            self.assertEqual(api.get_cos_backup_overview()[0]['status'], 'error')
        self.client_factory.assert_not_called()

    def prepare_http(self):
        user = dict(id=17, username='manager', role='supervisor')
        self.conn = MagicMock()
        self.stack.enter_context(patch.object(api, 'get_db_connection', return_value=self.conn))
        self.stack.enter_context(patch.object(api, 'get_user_by_id', return_value=user))
        self.permission = self.stack.enter_context(patch.object(api, 'can_manage_system', return_value=True))
        self.stack.enter_context(patch.object(api, 'verify_auth_token', return_value=(user, {})))
        self.stack.enter_context(patch.object(api, 'touch_online_user_presence'))
        self.stack.enter_context(patch.object(api, 'start_backup_scheduler_once'))
        self.stack.enter_context(patch.object(api, 'DEFAULT_BACKUP_DIR', str(self.root / 'backups')))
        self.stack.enter_context(patch.object(api, 'BACKUP_CONFIG_PATH', str(self.root / 'config.json')))
        self.lock = threading.Lock()
        self.stack.enter_context(patch.object(api, 'backup_job_lock', self.lock))
        for name in ('run_backup_subprocess', 'restore_full_backup_archive', 'cleanup_local_backup_files'):
            self.stack.enter_context(patch.object(api, name, side_effect=AssertionError('unsafe operation')))
        self.http = api.app.test_client()

    def test_http_overview_rejects_denied_users_before_any_sdk_access(self):
        self.prepare_http()
        self.permission.return_value = False
        response = self.http.get('/api/management/backups', headers={'Authorization': 'Bearer test'})
        self.assertEqual(response.status_code, 403)
        self.client_factory.assert_not_called(); self.conn.close.assert_called_once()

    def test_http_overview_failure_remains_success_with_cos_error_and_metadata(self):
        self.prepare_http()
        api.write_backup_config({'last_cos_key': 'saved-key'})
        self.client.list_objects.side_effect = RuntimeError('listing failed')
        response = self.http.get('/api/management/backups', headers={'Authorization': 'Bearer test'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['latest_cos_backups'], [])
        self.assertEqual(response.json['config']['cos']['message'], 'COS 备份列表读取失败：listing failed')
        self.assertEqual(response.json['config']['cos']['last_cos_key'], 'saved-key')
        self.assertNotIn('test-secret', json.dumps(response.json))

    def test_http_export_upload_failure_keeps_download_and_saves_warning_under_lock(self):
        self.prepare_http()
        self.client.upload_file.side_effect = RuntimeError('network failed')

        def archive(destination, reason):
            self.assertTrue(self.conn.close.called)
            self.assertTrue(self.lock.locked())
            return dict(path=str(self.archive), size=self.size, download_filename=self.filename,
                        cos=api.upload_backup_archive_to_cos(str(self.archive), self.filename))

        with patch.object(api, 'create_full_backup_archive', side_effect=archive):
            response = self.http.post('/api/management/backups/export', json={}, headers={'Authorization': 'Bearer test'})
        self.addCleanup(response.close)
        self.assertEqual((response.status_code, response.data), (200, self.archive.read_bytes()))
        self.assertEqual(response.headers['X-COS-Backup-Status'], 'error')
        saved = api.read_backup_config()
        self.assertEqual((saved['last_status'], saved['last_cos_status']), ('warning', 'error'))
        self.assertEqual(saved['last_error'], 'COS 上传失败：network failed')
        self.assertFalse(self.lock.locked()); self.client.delete_object.assert_not_called()

    def test_slow_upload_keeps_transfer_lock_and_competing_restore_is_rejected(self):
        self.prepare_http()
        entered, finish = threading.Event(), threading.Event()

        def upload(**kwargs):
            self.assertTrue(self.lock.locked())
            entered.set()
            if not finish.wait(3):
                raise TimeoutError('test upload was not released')

        def archive(destination, reason):
            return dict(path=str(self.archive), size=self.size, download_filename=self.filename,
                        cos=api.upload_backup_archive_to_cos(str(self.archive), self.filename))

        def request_export():
            response = api.app.test_client().post('/api/management/backups/export', json={},
                                                 headers={'Authorization': 'Bearer test'})
            try:
                self.assertEqual(response.status_code, 200)
                return response.data
            finally:
                response.close()

        self.client.upload_file.side_effect = upload
        with patch.object(api, 'create_full_backup_archive', side_effect=archive), ThreadPoolExecutor(max_workers=1) as executor:
            job = executor.submit(request_export)
            try:
                self.assertTrue(entered.wait(3))
                response = self.http.post('/api/management/backups/import', headers={'Authorization': 'Bearer test'})
                self.assertEqual(response.status_code, 409)
                self.assertTrue(self.lock.locked())
                self.client.delete_object.assert_not_called()
            finally:
                finish.set()
            self.assertEqual(job.result(timeout=3), self.archive.read_bytes())
        self.assertFalse(self.lock.locked())
        self.assertEqual(api.read_backup_config()['last_cos_status'], 'success')
