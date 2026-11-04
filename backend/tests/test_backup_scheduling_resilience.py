"""Isolated process-level regression tests; no production database or COS writes."""
from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

import app as api
from backups.cos_worker import run_bounded_upload
from backups.job_lock import BackupJobLock


class BackupResilienceTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.now = datetime(2026, 11, 4, 0, 5, tzinfo=api.BEIJING_TZ)
        for name, value in (('STORAGE_ROOT', str(self.root)),
                            ('BACKUP_CONFIG_PATH', str(self.root / 'backup_config.json')),
                            ('DEFAULT_BACKUP_DIR', str(self.root / 'backups')),
                            ('beijing_now', lambda: self.now)):
            p = patch.object(api, name, value)
            p.start()
            self.addCleanup(p.stop)
        api.write_backup_config(dict(frequency='daily', scheduled_time='00:00',
                                     next_auto_run_at='2026-11-04T00:00:00+08:00'))

    def test_concurrent_processes_claim_one_run_even_when_upload_fails(self):
        worker = r"""
import sys, time
from pathlib import Path
from datetime import datetime
from unittest.mock import patch
import app as api
root = Path(sys.argv[1])
api.STORAGE_ROOT = str(root)
api.BACKUP_CONFIG_PATH = str(root / 'backup_config.json')
api.DEFAULT_BACKUP_DIR = str(root / 'backups')
api.beijing_now = lambda: datetime(2026, 11, 4, 0, 5, tzinfo=api.BEIJING_TZ)
def fail(*args, **kwargs):
    with (root / 'claims').open('a') as f:
        f.write('claim\n')
    time.sleep(.2)
    raise RuntimeError('simulated upload failure')
with patch.object(api, 'create_full_backup_archive', side_effect=fail):
    api.maybe_run_scheduled_backup()
"""
        workers = [subprocess.Popen([sys.executable, '-c', worker, str(self.root)],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                   for _ in range(4)]
        try:
            for process in workers:
                _, errors = process.communicate(timeout=20)
                self.assertEqual(process.returncode, 0, errors)
        finally:
            for process in workers:
                if process.poll() is None:
                    process.kill()
                process.communicate()
        self.assertEqual((self.root / 'claims').read_text().splitlines(), ['claim'])
        saved = api.read_backup_config()
        self.assertEqual(saved['next_auto_run_at'], '2026-11-05T00:00:00+08:00')
        self.assertEqual(saved['last_status'], 'error')

    def test_crash_after_claim_does_not_run_the_same_slot_again(self):
        with patch.object(api, 'create_full_backup_archive', side_effect=SystemExit) as create:
            with self.assertRaises(SystemExit):
                api.maybe_run_scheduled_backup()
            self.assertEqual(api.read_backup_config()['last_status'], 'running')
            api.maybe_run_scheduled_backup()
            create.assert_called_once()
        self.assertEqual(api.read_backup_config()['last_status'], 'error')
        self.assertEqual(api.read_backup_config()['next_auto_run_at'], '2026-11-05T00:00:00+08:00')

    def test_restore_cannot_remove_the_lock_or_overwrite_schedule(self):
        with tempfile.TemporaryDirectory() as work:
            archive = Path(work) / 'restore.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('storage/backup_config.json', '{"frequency":"off"}')
                z.writestr('storage/issues/a.txt', 'restored')
            lock = BackupJobLock(lambda: str(self.root))
            self.assertTrue(lock.acquire(blocking=False))
            try:
                with patch.object(api, 'get_required_storage_dirs', return_value=()):
                    api.restore_storage_from_backup(archive)
                self.assertFalse(BackupJobLock(lambda: str(self.root)).acquire(blocking=False))
                self.assertEqual(api.read_backup_config()['frequency'], 'daily')
                self.assertEqual((self.root / 'issues/a.txt').read_text(), 'restored')
            finally:
                lock.release()

    def test_stalled_sdk_is_killed_by_the_child_deadline(self):
        (self.root / 'qcloud_cos.py').write_text(
            'import time\nclass CosConfig:\n def __init__(self, **kw): pass\n'
            'class CosS3Client:\n def __init__(self, config): pass\n'
            ' def upload_file(self, **kw): time.sleep(60)\n'
        )
        archive = self.root / 'backup.zip'
        archive.write_bytes(b'local archive')
        start = time.monotonic()
        with patch.dict(os.environ, dict(PYTHONPATH=str(self.root), COS_SECRET_ID='fake',
                COS_SECRET_KEY='fake', COS_REGION='fake', COS_BUCKET='fake')):
            result = run_bounded_upload(str(archive), 'backup.zip', prefix='test',
                                        backup_prefix='backup', retention=1, timeout=1)
        self.assertLess(time.monotonic() - start, 5)
        self.assertEqual(result['status'], 'error')
        self.assertIn('已停止', result['message'])
        self.assertEqual(archive.read_bytes(), b'local archive')

    def test_upload_child_keeps_the_lock_if_the_owner_exits(self):
        lock = BackupJobLock(lambda: str(self.root))
        self.assertTrue(lock.acquire(blocking=False))
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'],
                                 pass_fds=lock.inherited_fds())
        lock.release()
        try:
            self.assertFalse(lock.acquire(blocking=False))
        finally:
            child.kill()
            child.wait(timeout=5)
        self.assertTrue(lock.acquire(blocking=False))
        lock.release()
