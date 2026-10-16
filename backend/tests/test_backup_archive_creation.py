"""Real temporary ZIP creation/publication with fake pg_dump and no COS or business DB."""
from contextlib import ExitStack
from datetime import datetime
from io import BytesIO
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch
import zipfile

import app as api


class BackupArchiveCreationTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.storage = self.root / 'storage'
        self.default = self.storage / 'backups'
        self.destination = self.storage / 'custom'
        self.exports = self.storage / 'report_exports'
        self.config = self.storage / 'backup_config.json'
        self.work = self.root / 'work'
        self.work.mkdir()
        for name, path in (('STORAGE_ROOT', self.storage), ('DEFAULT_BACKUP_DIR', self.default),
                           ('INSPECTION_REPORT_EXPORTS_STORAGE_DIR', self.exports), ('BACKUP_CONFIG_PATH', self.config)):
            self.stack.enter_context(patch.object(api, name, str(path)))
        original_temporary_directory = tempfile.TemporaryDirectory
        self.stack.enter_context(patch.object(api.tempfile, 'TemporaryDirectory',
                                             side_effect=lambda: original_temporary_directory(dir=self.work)))
        self.now = datetime(2026, 10, 16, 12, 34, 56, tzinfo=api.BEIJING_TZ)
        self.stack.enter_context(patch.object(api, 'beijing_now', return_value=self.now))
        self.db_config = dict(host='never-used', port='5432', user='test-only', dbname='not-a-business-database')
        self.stack.enter_context(patch.object(api, 'build_pg_environment', return_value=(self.db_config, {'PGPASSWORD': 'test-only'})))
        self.connect = self.stack.enter_context(patch.object(api, 'get_db_connection', side_effect=AssertionError('unexpected DB access')))
        for name in ('restore_database_from_backup', 'restore_storage_from_backup', 'clear_storage_root_for_restore', 'get_cos_client'):
            self.stack.enter_context(patch.object(api, name, side_effect=AssertionError('unsafe operation: ' + name)))
        self.filename = api.LOCAL_BACKUP_FILENAME
        self.final = self.file(self.destination / self.filename, b'previous final')
        self.stale = self.file(self.destination / (api.BACKUP_PREFIX + '_stale.zip'), b'previous custom')
        self.default_stale = self.file(self.default / self.filename, b'previous default')
        self.file(self.storage / 'issues/photo.png', b'photo')
        self.file(self.exports / 'preview.pdf', b'do not include')
        api.write_backup_config(dict(destination_path=str(self.destination), last_status='previous'))
        self.previous_config = self.config.read_bytes()
        self.events = []
        self.temp_dirs = []
        self.dump = self.stack.enter_context(patch.object(api, 'run_backup_subprocess', side_effect=self.dump_database))
        self.pack = self.observe('add_storage_to_backup', 'pack')
        self.publish = self.observe('publish_backup_archive', 'publish')
        self.cleanup = self.observe('cleanup_local_backup_files', 'cleanup')
        self.upload = self.stack.enter_context(patch.object(api, 'upload_backup_archive_to_cos', side_effect=self.upload_archive))

    def file(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def observe(self, name, event):
        original = getattr(api, name)

        def operation(*args, **kwargs):
            self.events.append(event)
            return original(*args, **kwargs)

        return self.stack.enter_context(patch.object(api, name, side_effect=operation))

    def dump_database(self, command, env):
        if hasattr(self, 'conn'):
            self.assertTrue(self.conn.close.called)
            self.assertTrue(self.lock.locked())
        self.assertEqual(command[:-1], ['pg_dump', '-h', 'never-used', '-p', '5432', '-U', 'test-only',
                                      '-d', 'not-a-business-database', '-Fc', '--no-owner', '--no-acl', '-f'])
        self.assertEqual(env, {'PGPASSWORD': 'test-only'})
        dump_path = Path(command[-1])
        self.assertEqual(dump_path.parent.parent, self.work)
        self.temp_dirs.append(dump_path.parent)
        dump_path.write_bytes(b'fake database dump')
        self.events.append('dump')

    def upload_archive(self, path, name):
        self.assertEqual(path, str(self.final))
        self.assertEqual(name, api.BACKUP_PREFIX + '_manual_20261016_123456.zip')
        self.assertTrue(self.final.is_file())
        self.assertTrue(all(not directory.exists() for directory in self.temp_dirs))
        if hasattr(self, 'lock'):
            self.assertTrue(self.lock.locked())
        self.events.append('upload')
        return dict(status='not_configured')

    def create(self):
        return api.create_full_backup_archive(str(self.destination))

    def assert_work_clean(self):
        self.assertEqual(list(self.work.iterdir()), [])

    def test_complete_archive_manifest_order_compression_exclusions_and_result(self):
        result = self.create()
        self.assertEqual(self.events, ['dump', 'pack', 'publish', 'cleanup', 'cleanup', 'upload'])
        self.assertEqual(result, dict(path=str(self.final), filename=self.filename,
            download_filename=api.BACKUP_PREFIX + '_manual_20261016_123456.zip', size=self.final.stat().st_size,
            created_at=self.now.isoformat(), cos={'status': 'not_configured'}))
        with zipfile.ZipFile(self.final) as archive:
            self.assertEqual(archive.namelist(), ['manifest.json', 'database.dump', 'storage/issues/photo.png'])
            self.assertEqual(archive.read('database.dump'), b'fake database dump')
            self.assertEqual(archive.read('storage/issues/photo.png'), b'photo')
            self.assertIsNone(archive.testzip())
            self.assertTrue(all(item.compress_type == zipfile.ZIP_DEFLATED for item in archive.infolist()))
            self.assertEqual(json.loads(archive.read('manifest.json')), dict(backup_type='ywddzx_full_backup', version=2,
                created_at=self.now.isoformat(), reason='manual', database=self.db_config['dbname'],
                database_member='database.dump', database_format='custom',
                restore_strategy='drop_user_schemas_then_restore_sql', storage_root=str(self.storage)))
        self.assertFalse(self.stale.exists()); self.assertFalse(self.default_stale.exists())
        self.assertEqual(self.config.read_bytes(), self.previous_config)
        self.assert_work_clean(); self.connect.assert_not_called()

    def test_default_destination_only_cleans_one_directory(self):
        self.destination = self.default
        self.final = self.default_stale
        result = api.create_full_backup_archive()
        self.assertEqual(result['path'], str(self.final))
        self.assertEqual(self.events, ['dump', 'pack', 'publish', 'cleanup', 'upload'])
        self.cleanup.assert_called_once_with(str(self.default), keep_path=str(self.final))
        self.assertTrue(self.stale.exists())

    def test_dump_failure_preserves_old_archives_and_never_packs_or_uploads(self):
        self.dump.side_effect = RuntimeError('dump substitute failed')
        with self.assertRaisesRegex(RuntimeError, 'dump substitute failed'):
            self.create()
        self.pack.assert_not_called(); self.publish.assert_not_called(); self.cleanup.assert_not_called(); self.upload.assert_not_called()
        self.assertEqual(self.final.read_bytes(), b'previous final')
        self.assertTrue(self.stale.exists()); self.assertTrue(self.default_stale.exists())
        self.assert_work_clean()

    def test_pack_failure_preserves_old_archives_and_cleans_temporary_work(self):
        self.pack.side_effect = OSError('pack failed')
        with self.assertRaisesRegex(OSError, 'pack failed'):
            self.create()
        self.publish.assert_not_called(); self.cleanup.assert_not_called(); self.upload.assert_not_called()
        self.assertEqual(self.final.read_bytes(), b'previous final')
        self.assert_work_clean()

    def test_publish_failure_does_not_start_cleanup_or_upload(self):
        self.publish.side_effect = OSError('publish failed')
        with self.assertRaisesRegex(OSError, 'publish failed'):
            self.create()
        self.cleanup.assert_not_called(); self.upload.assert_not_called()
        self.assertEqual(self.final.read_bytes(), b'previous final')
        self.assert_work_clean()

    def test_cleanup_failure_leaves_newly_published_archive_without_compensation(self):
        self.cleanup.side_effect = OSError('cleanup failed')
        with self.assertRaisesRegex(OSError, 'cleanup failed'):
            self.create()
        with zipfile.ZipFile(self.final) as archive:
            self.assertEqual(archive.read('database.dump'), b'fake database dump')
        self.assertTrue(self.stale.exists()); self.assertTrue(self.default_stale.exists())
        self.upload.assert_not_called()
        self.assertEqual(self.config.read_bytes(), self.previous_config)
        self.assert_work_clean()

    def test_cos_error_result_keeps_successful_local_archive(self):
        self.upload.side_effect = None
        self.upload.return_value = dict(status='error', message='COS substitute failed')
        result = self.create()
        self.assertEqual(result['cos'], self.upload.return_value)
        self.assertTrue(self.final.is_file())
        self.assertFalse(self.stale.exists())
        self.assert_work_clean()

    def test_unexpected_cos_exception_does_not_undo_local_publication(self):
        self.upload.side_effect = RuntimeError('COS substitute raised')
        with self.assertRaisesRegex(RuntimeError, 'COS substitute raised'):
            self.create()
        with zipfile.ZipFile(self.final) as archive:
            self.assertEqual(archive.read('database.dump'), b'fake database dump')
        self.assertFalse(self.stale.exists())
        self.assertEqual(self.config.read_bytes(), self.previous_config)
        self.assert_work_clean()

    def prepare_http(self):
        user = dict(id=17, username='manager', role='supervisor')
        self.conn = MagicMock()
        self.connect.side_effect = None
        self.connect.return_value = self.conn
        self.stack.enter_context(patch.object(api, 'get_user_by_id', return_value=user))
        self.permission = self.stack.enter_context(patch.object(api, 'can_manage_system', return_value=True))
        self.stack.enter_context(patch.object(api, 'verify_auth_token', return_value=(user, {})))
        self.stack.enter_context(patch.object(api, 'touch_online_user_presence'))
        self.stack.enter_context(patch.object(api, 'start_backup_scheduler_once'))
        self.lock = threading.Lock()
        self.stack.enter_context(patch.object(api, 'backup_job_lock', self.lock))
        self.http = api.app.test_client()

    def export(self, authenticated=True):
        return self.http.post('/api/management/backups/export', json={},
                              headers={'Authorization': 'Bearer test'} if authenticated else {})

    def test_http_export_builds_real_temporary_zip_and_preserves_download_and_config(self):
        self.prepare_http()
        response = self.export()
        self.addCleanup(response.close)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'application/zip')
        self.assertEqual(response.headers['X-Backup-Path'], str(self.final))
        self.assertEqual(response.headers['X-Backup-Size'], str(len(response.data)))
        self.assertEqual(response.headers['X-COS-Backup-Status'], 'not_configured')
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        with zipfile.ZipFile(BytesIO(response.data)) as archive:
            self.assertEqual(archive.read('storage/issues/photo.png'), b'photo')
        self.assertEqual(api.read_backup_config()['last_status'], 'success')
        self.assertFalse(self.lock.locked())
        self.conn.commit.assert_not_called(); self.conn.rollback.assert_not_called()
        self.assert_work_clean()

    def test_http_denial_never_starts_dump_or_changes_archives(self):
        self.prepare_http()
        self.assertEqual(self.export(authenticated=False).status_code, 401)
        self.permission.return_value = False
        self.assertEqual(self.export().status_code, 403)
        self.dump.assert_not_called(); self.pack.assert_not_called(); self.upload.assert_not_called()
        self.assertEqual(self.final.read_bytes(), b'previous final')
        self.assertEqual(self.config.read_bytes(), self.previous_config)

    def test_http_creation_failure_releases_lock_and_preserves_config(self):
        self.prepare_http()
        self.dump.side_effect = RuntimeError('dump substitute failed')
        response = self.export()
        self.assertEqual((response.status_code, response.json), (500, {'success': False, 'error': 'dump substitute failed'}))
        self.assertFalse(self.lock.locked())
        self.assertEqual(self.final.read_bytes(), b'previous final')
        self.assertEqual(self.config.read_bytes(), self.previous_config)
        self.assert_work_clean()
