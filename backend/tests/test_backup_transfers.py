from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import MagicMock

from backups.transfers import BackupTaskBusy, BackupTransfers


class BackupTransfersTests(unittest.TestCase):
    def service(self, lock=None, **overrides):
        dependencies = dict(
            job_lock=lock if lock is not None else threading.Lock(),
            read_config=MagicMock(return_value={'destination_path': '/test/backups'}),
            write_config=MagicMock(),
            create_archive=MagicMock(return_value={'path': '/test/archive.zip', 'size': 10}),
            restore_archive=MagicMock(return_value={'version': 2}),
        )
        dependencies.update(overrides)
        return BackupTransfers(**dependencies)

    def test_instances_share_one_lock_and_competing_import_never_reads_upload(self):
        lock = threading.Lock()
        entered, finish = threading.Event(), threading.Event()

        def create(*args, **kwargs):
            entered.set()
            if not finish.wait(3):
                raise TimeoutError('test did not release its fake backup')
            return {'path': '/test/archive.zip', 'size': 10}

        exporter = self.service(lock, create_archive=create)
        importer = self.service(lock)
        upload = MagicMock()
        with ThreadPoolExecutor(max_workers=1) as executor:
            job = executor.submit(exporter.export)
            try:
                self.assertTrue(entered.wait(3))
                with self.assertRaisesRegex(BackupTaskBusy, '已有备份或恢复任务'):
                    importer.restore(upload)
                # Scheduled backup uses this same process-local lock, not a service-local one.
                self.assertFalse(lock.acquire(blocking=False))
                upload.assert_not_called()
                importer.read_config.assert_not_called()
                importer.restore_archive.assert_not_called()
            finally:
                finish.set()
            self.assertEqual(job.result(timeout=3)['size'], 10)
        self.assertFalse(lock.locked())
        importer.restore(upload)
        upload.assert_called_once()

    def test_config_read_or_archive_failure_releases_lock_and_allows_next_job(self):
        for dependency in ('read_config', 'create_archive'):
            with self.subTest(dependency=dependency):
                service = self.service(**{dependency: MagicMock(side_effect=RuntimeError('failed'))})
                with self.assertRaisesRegex(RuntimeError, 'failed'):
                    service.export()
                service.write_config.assert_not_called()
                self.assertFalse(service.job_lock.locked())
                self.service(service.job_lock).export()

    def test_upload_parser_failure_does_not_restore_or_change_config(self):
        service = self.service()
        with self.assertRaisesRegex(ValueError, 'invalid multipart'):
            service.restore(MagicMock(side_effect=ValueError('invalid multipart')))
        service.restore_archive.assert_not_called()
        service.read_config.assert_not_called()
        self.assertFalse(service.job_lock.locked())

    def test_temporary_config_file_preserves_existing_keys_and_warning_details(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            original = dict(frequency='weekly', scheduled_time='03:15', destination_path=directory,
                            next_auto_run_at='2026-10-23T03:15:00+08:00', custom_field='keep')
            path.write_text(json.dumps(original), encoding='utf-8')

            def read():
                return json.loads(path.read_text(encoding='utf-8'))

            def write(value):
                path.write_text(json.dumps(value), encoding='utf-8')

            service = self.service(read_config=read, write_config=write,
                create_archive=lambda *a, **kw: dict(path='/test/archive.zip', size=8,
                    cos=dict(status='error', message='COS upload failed')))
            service.export()
            saved = read()
            self.assertEqual({key: saved[key] for key in original}, original)
            self.assertEqual(saved['last_status'], 'warning')
            self.assertEqual(saved['last_error'], 'COS upload failed')
            self.assertEqual(saved['last_cos_error'], 'COS upload failed')
            self.assertEqual(saved['last_cos_retained_count'], 0)
            before_restore = deepcopy(saved)
            service.restore(lambda: object())
            self.assertEqual(read(), {**before_restore, 'last_status': 'success', 'last_error': ''})
