"""Local backup file contracts. All reads, writes and removals use temporary trees."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch
import zipfile

import app as api


class BackupLocalFilesTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.storage = self.root / 'storage'
        self.default = self.storage / 'backups'
        self.exports = self.storage / 'report_exports'
        self.config = self.storage / 'backup_config.json'
        for name, path in (('STORAGE_ROOT', self.storage), ('DEFAULT_BACKUP_DIR', self.default),
                           ('INSPECTION_REPORT_EXPORTS_STORAGE_DIR', self.exports), ('BACKUP_CONFIG_PATH', self.config)):
            self.stack.enter_context(patch.object(api, name, str(path)))
        self.filename = api.BACKUP_PREFIX + '_latest.zip'
        for name in ('get_db_connection', 'run_backup_subprocess', 'upload_backup_archive_to_cos',
                     'restore_database_from_backup', 'clear_storage_root_for_restore'):
            self.stack.enter_context(patch.object(api, name, side_effect=AssertionError('unsafe operation: ' + name)))

    def file(self, path, content=b'data'):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def pack(self, destination=None):
        path = self.root / 'packed.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            api.add_storage_to_backup(archive, str(destination or self.default))
        with zipfile.ZipFile(path) as archive:
            return {name: archive.read(name) for name in archive.namelist()}

    def test_exclusions_keep_order_deduplicate_and_ignore_external_destinations(self):
        custom = self.storage / 'custom'
        self.assertEqual(api.get_storage_backup_excluded_dirs(str(custom)),
                         list(map(str, (self.exports, custom, self.default))))
        for destination in (self.storage, self.root / 'outside'):
            self.assertEqual(api.get_storage_backup_excluded_dirs(str(destination)),
                             list(map(str, (self.exports, self.default))))
        self.assertEqual(api.get_storage_backup_excluded_dirs(str(self.default / '../backups')),
                         list(map(str, (self.exports, self.default))))
        self.assertFalse(self.storage.exists())

    def test_exclusion_checks_exact_descendant_and_not_sibling_prefix(self):
        paths = [str(self.default)]
        for path in (self.default, self.default / 'nested/file.zip'):
            self.assertTrue(api.should_skip_storage_backup_path(str(path), paths))
        self.assertFalse(api.should_skip_storage_backup_path(str(self.storage / 'backups-other/file.zip'), paths))
        self.assertFalse(api.should_skip_storage_backup_path(str(self.storage / 'file'), []))
        self.assertEqual(paths, [str(self.default)])

    def test_incomparable_path_errors_keep_existing_fallback(self):
        with patch.object(api.os.path, 'commonpath', side_effect=ValueError('different drive')):
            self.assertFalse(api.should_skip_storage_backup_path(str(self.storage / 'file'), [str(self.default)]))
            self.assertEqual(api.get_storage_backup_excluded_dirs(str(self.storage / 'custom')), [str(self.exports)])

    def test_pack_includes_business_files_and_skips_config_backups_and_report_exports(self):
        photo = self.file(self.storage / 'issues/照片.png', b'photo')
        self.file(self.storage / 'inspection_originals/check.pdf', b'original')
        self.file(self.storage / 'issues' / self.filename, b'nested ZIP is not excluded by name')
        self.file(self.storage / 'other.zip', b'unrelated ZIP')
        self.file(self.config, b'private backup config')
        self.file(self.storage / self.filename, b'old root backup')
        self.file(self.default / self.filename, b'old default backup')
        self.file(self.exports / 'huge-report.pptx', b'excluded')
        custom = self.storage / 'custom'
        self.file(custom / 'another.zip', b'excluded')
        result = self.pack(custom)
        self.assertEqual(result, {
            'storage/issues/照片.png': b'photo', 'storage/inspection_originals/check.pdf': b'original',
            'storage/issues/' + self.filename: b'nested ZIP is not excluded by name', 'storage/other.zip': b'unrelated ZIP',
        })
        self.assertEqual(photo.read_bytes(), b'photo')

    def test_walk_prunes_excluded_directories_in_place_before_descent(self):
        visited = []

        def walk(path):
            self.assertEqual(path, str(self.storage))
            dirs = ['report_exports', 'issues']
            yield str(self.storage), dirs, []
            self.assertEqual(dirs, ['issues'])
            visited.extend(dirs)
            yield str(self.storage / 'issues'), [], ['photo.png']

        archive = MagicMock()
        with patch.object(api.os, 'walk', side_effect=walk):
            api.add_storage_to_backup(archive, str(self.default))
        self.assertEqual(visited, ['issues'])
        archive.write.assert_called_once_with(str(self.storage / 'issues/photo.png'), 'storage/issues/photo.png')

    def test_missing_storage_keeps_empty_zip_without_creating_storage(self):
        self.assertEqual(self.pack(), {})
        self.assertFalse(self.storage.exists())

    def test_pack_uses_existing_filename_separator_conversion(self):
        if os.path.sep == '/':
            self.file(self.storage / 'nested\\photo.png', b'photo')
            self.assertEqual(self.pack(), {'storage/nested/photo.png': b'photo'})
        else:
            self.file(self.storage / 'nested/photo.png', b'photo')
            self.assertEqual(self.pack(), {'storage/nested/photo.png': b'photo'})

    def test_file_symlinks_keep_existing_follow_behavior_but_directory_links_are_not_walked(self):
        outside = self.file(self.root / 'outside/temporary.txt', b'outside test file')
        self.storage.mkdir()
        (self.storage / 'linked.txt').symlink_to(outside)
        (self.storage / 'linked-directory').symlink_to(outside.parent, target_is_directory=True)
        self.assertEqual(self.pack(), {'storage/linked.txt': b'outside test file'})
        self.assertEqual(outside.read_bytes(), b'outside test file')

    def test_pack_file_errors_propagate_without_removing_sources(self):
        path = self.file(self.storage / 'issues/photo.png')
        with patch.object(zipfile.ZipFile, 'write', side_effect=OSError('cannot read source')):
            with self.assertRaisesRegex(OSError, 'cannot read source'):
                self.pack()
        self.assertEqual(path.read_bytes(), b'data')

    def test_list_normalizes_default_path_filters_files_sorts_and_limits_twenty(self):
        expected = []
        for index in range(23):
            path = self.file(self.default / (api.BACKUP_PREFIX + f'_{index}.zip'), bytes([index]))
            stamp = 1700000000 + index
            os.utime(path, (stamp, stamp))
            expected.append(dict(filename=path.name, path=str(path), size=1,
                                 updated_at=datetime.fromtimestamp(stamp, api.BEIJING_TZ).isoformat()))
        self.file(self.default / 'not-backup.zip')
        self.file(self.default / (api.BACKUP_PREFIX + '_not-zip.txt'))
        (self.default / (api.BACKUP_PREFIX + '_directory.zip')).mkdir()
        self.assertEqual(api.list_backup_files(''), list(reversed(expected))[:20])

    def test_list_missing_directory_is_empty_and_list_errors_propagate(self):
        self.assertEqual(api.list_backup_files('missing'), [])
        self.default.mkdir(parents=True)
        with patch.object(api.os, 'listdir', side_effect=PermissionError('cannot list')):
            with self.assertRaisesRegex(PermissionError, 'cannot list'):
                api.list_backup_files('')

    def test_cleanup_removes_only_backup_files_and_preserves_normalized_keep_path(self):
        keep = self.file(self.default / self.filename, b'keep')
        stale = self.file(self.default / (api.BACKUP_PREFIX + '_old.zip'), b'delete')
        other = self.file(self.default / 'other.zip', b'other')
        (self.default / (api.BACKUP_PREFIX + '_folder.zip')).mkdir()
        api.cleanup_local_backup_files('', keep_path=str(self.default / 'nested/../' / self.filename))
        self.assertEqual(keep.read_bytes(), b'keep')
        self.assertFalse(stale.exists())
        self.assertEqual(other.read_bytes(), b'other')
        self.assertTrue((self.default / (api.BACKUP_PREFIX + '_folder.zip')).is_dir())

    def test_cleanup_missing_directory_does_not_create_it(self):
        self.assertIsNone(api.cleanup_local_backup_files('missing'))
        self.assertFalse(self.default.exists())

    def test_cleanup_unlinks_backup_symlink_without_deleting_target(self):
        target = self.file(self.root / 'outside.zip', b'outside')
        self.default.mkdir(parents=True)
        link = self.default / self.filename
        link.symlink_to(target)
        api.cleanup_local_backup_files('')
        self.assertFalse(link.is_symlink())
        self.assertEqual(target.read_bytes(), b'outside')

    def test_cleanup_failure_keeps_prior_deletions_and_stops_without_retry(self):
        first = self.file(self.default / (api.BACKUP_PREFIX + '_1.zip'))
        second = self.file(self.default / (api.BACKUP_PREFIX + '_2.zip'))
        third = self.file(self.default / (api.BACKUP_PREFIX + '_3.zip'))
        original_remove = os.remove

        def remove(path):
            if path == str(second):
                raise OSError('second delete failed')
            original_remove(path)

        with patch.object(api.os, 'listdir', return_value=[first.name, second.name, third.name]), \
             patch.object(api.os, 'remove', side_effect=remove) as removal:
            with self.assertRaisesRegex(OSError, 'second delete failed'):
                api.cleanup_local_backup_files('')
        self.assertFalse(first.exists())
        self.assertTrue(second.exists()); self.assertTrue(third.exists())
        self.assertEqual(removal.call_count, 2)

    def test_publish_uses_same_directory_staging_then_replace_and_keeps_source(self):
        source = self.file(self.root / 'source.zip', b'new complete archive')
        final = self.file(self.default / self.filename, b'old archive')
        copy = api.shutil.copy2
        replace = os.replace
        events = []

        def stage(src, dst):
            self.assertEqual(Path(dst).parent, final.parent)
            self.assertRegex(Path(dst).name, r'^\.' + self.filename.replace('.', r'\.') + r'\.[0-9a-f]{32}\.tmp$')
            self.assertEqual(final.read_bytes(), b'old archive')
            events.append('copy')
            return copy(src, dst)

        def publish(src, dst):
            self.assertEqual(Path(src).read_bytes(), b'new complete archive')
            events.append('replace')
            return replace(src, dst)

        with patch.object(api.shutil, 'copy2', side_effect=stage), patch.object(api.os, 'replace', side_effect=publish):
            self.assertIsNone(api.publish_backup_archive(str(source), str(final)))
        self.assertEqual(events, ['copy', 'replace'])
        self.assertEqual(final.read_bytes(), source.read_bytes())
        self.assertEqual(list(final.parent.iterdir()), [final])

    def test_publish_creates_destination_directory(self):
        source = self.file(self.root / 'source.zip', b'archive')
        final = self.default / self.filename
        api.publish_backup_archive(str(source), str(final))
        self.assertEqual(final.read_bytes(), b'archive')

    def test_publish_mkdir_failure_does_not_copy_or_replace(self):
        source = self.file(self.root / 'source.zip')
        with patch.object(api.os, 'makedirs', side_effect=OSError('cannot create destination')), \
             patch.object(api.shutil, 'copy2') as copy, patch.object(api.os, 'replace') as replace:
            with self.assertRaisesRegex(OSError, 'cannot create destination'):
                api.publish_backup_archive(str(source), str(self.default / self.filename))
        copy.assert_not_called(); replace.assert_not_called()

    def test_publish_partial_copy_failure_removes_stage_and_keeps_old_final(self):
        source = self.file(self.root / 'source.zip', b'new')
        final = self.file(self.default / self.filename, b'old')

        def copy(src, dst):
            Path(dst).write_bytes(b'partial')
            raise OSError('copy failed')

        with patch.object(api.shutil, 'copy2', side_effect=copy), patch.object(api.os, 'replace') as replace:
            with self.assertRaisesRegex(OSError, 'copy failed'):
                api.publish_backup_archive(str(source), str(final))
        replace.assert_not_called()
        self.assertEqual(final.read_bytes(), b'old')
        self.assertEqual(list(final.parent.iterdir()), [final])

    def test_publish_replace_failure_removes_stage_and_keeps_old_final(self):
        source = self.file(self.root / 'source.zip', b'new')
        final = self.file(self.default / self.filename, b'old')
        with patch.object(api.os, 'replace', side_effect=OSError('replace failed')):
            with self.assertRaisesRegex(OSError, 'replace failed'):
                api.publish_backup_archive(str(source), str(final))
        self.assertEqual(final.read_bytes(), b'old')
        self.assertEqual(list(final.parent.iterdir()), [final])

    def test_publish_cleanup_error_keeps_existing_exception_precedence(self):
        source = self.file(self.root / 'source.zip', b'new')
        final = self.file(self.default / self.filename, b'old')

        def copy(src, dst):
            Path(dst).write_bytes(b'partial')
            raise OSError('copy failed')

        with patch.object(api.shutil, 'copy2', side_effect=copy), \
             patch.object(api.os, 'remove', side_effect=OSError('stage cleanup failed')):
            with self.assertRaisesRegex(OSError, 'stage cleanup failed'):
                api.publish_backup_archive(str(source), str(final))
        self.assertEqual(final.read_bytes(), b'old')
        self.assertEqual(len(list(final.parent.glob('.*.tmp'))), 1)

    def test_concurrent_publish_uses_distinct_stages_and_leaves_one_complete_archive(self):
        first = self.file(self.root / 'first.zip', b'first complete')
        second = self.file(self.root / 'second.zip', b'second complete')
        final = self.file(self.default / self.filename, b'old')
        original_copy = api.shutil.copy2
        stages = []
        lock = threading.Lock()
        ready, release = threading.Event(), threading.Event()

        def copy(src, dst):
            result = original_copy(src, dst)
            with lock:
                stages.append(dst)
                if len(stages) == 2:
                    ready.set()
            if not release.wait(3):
                raise TimeoutError('test publisher was not released')
            return result

        with patch.object(api.shutil, 'copy2', side_effect=copy), ThreadPoolExecutor(max_workers=2) as executor:
            jobs = [executor.submit(api.publish_backup_archive, str(source), str(final)) for source in (first, second)]
            try:
                self.assertTrue(ready.wait(3))
                self.assertEqual(len(set(stages)), 2)
                self.assertEqual(final.read_bytes(), b'old')
            finally:
                release.set()
            for job in jobs:
                job.result(timeout=3)
        self.assertIn(final.read_bytes(), (b'first complete', b'second complete'))
        self.assertEqual(list(final.parent.iterdir()), [final])
