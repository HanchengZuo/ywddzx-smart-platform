"""Archive validation contracts using small temporary ZIPs, without restoring anything."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

import app as api


class BackupArchiveValidationTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.path = self.root / 'archive.zip'
        self.storage = self.root / 'storage'
        self.stack.enter_context(patch.object(api, 'STORAGE_ROOT', str(self.storage)))
        for name in ('get_db_connection', 'run_backup_subprocess', 'upload_backup_archive_to_cos',
                     'clear_storage_root_for_restore', 'restore_database_from_backup'):
            self.stack.enter_context(patch.object(api, name, side_effect=AssertionError('unsafe operation: ' + name)))

    def archive(self, entries):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(self.path, 'w') as archive:
                for name, content in entries:
                    archive.writestr(name, content)
        return self.path

    def manifest(self, **extra):
        return json.dumps(dict(backup_type='ywddzx_full_backup', **extra), ensure_ascii=False)

    def assert_error(self, entries, message, error_type=ValueError):
        with self.assertRaises(error_type) as error:
            api.validate_backup_archive(self.archive(entries))
        self.assertEqual(str(error.exception), message)

    def test_database_member_selection_prefers_dump_and_accepts_legacy_sql(self):
        self.assertEqual(api.get_database_backup_member_name({'database.sql', 'database.dump'}), 'database.dump')
        self.assertEqual(api.get_database_backup_member_name(['database.sql']), 'database.sql')
        for names in (set(), {'nested/database.dump'}, {'DATABASE.DUMP'}, {'database.dump/'}):
            with self.subTest(names=names), self.assertRaises(ValueError) as error:
                api.get_database_backup_member_name(names)
            self.assertEqual(str(error.exception), '备份文件缺少 database.dump 或 database.sql。')

    def test_valid_manifest_preserves_metadata_and_uses_actual_database_member(self):
        text = self.manifest(version=2, database_member='../../untrusted.sql', note='原有元数据', extension={'keep': True})
        path = self.archive([('manifest.json', text), ('database.dump', b'fake dump'), ('database.sql', 'legacy')])
        before = path.read_bytes()
        self.assertEqual(api.validate_backup_archive(path), {**json.loads(text), 'database_member': 'database.dump'})
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(self.storage.exists())

    def test_legacy_sql_and_unchecked_manifest_versions_remain_accepted(self):
        for version in (None, 1, 999):
            text = self.manifest(version=version)
            result = api.validate_backup_archive(self.archive([('manifest.json', text), ('database.sql', 'fake SQL')]))
            self.assertEqual(result, {**json.loads(text), 'database_member': 'database.sql'})

    def test_missing_manifest_precedes_database_and_json_errors(self):
        self.assert_error([], '备份文件缺少 manifest.json。')
        self.assert_error([('nested/manifest.json', 'invalid')], '备份文件缺少 manifest.json。')

    def test_missing_database_member_precedes_manifest_decoding(self):
        self.assert_error([('manifest.json', b'\xff')], '备份文件缺少 database.dump 或 database.sql。')

    def test_invalid_json_keeps_specific_error(self):
        self.assert_error([('manifest.json', '{broken'), ('database.dump', '')], '备份文件清单格式不正确。')

    def test_wrong_backup_type_keeps_specific_error(self):
        for text in ('{}', '{"backup_type":"other"}'):
            self.assert_error([('manifest.json', text), ('database.dump', '')], '备份文件类型不正确。')

    def test_non_object_json_and_utf8_errors_are_not_silently_normalized(self):
        for text in ('null', '[]', '123', '"text"'):
            with self.subTest(text=text), self.assertRaises(AttributeError):
                api.validate_backup_archive(self.archive([('manifest.json', text), ('database.dump', '')]))
        with self.assertRaises(UnicodeDecodeError):
            api.validate_backup_archive(self.archive([('manifest.json', b'\xff'), ('database.dump', '')]))

    def test_invalid_zip_and_missing_file_remain_distinct_errors(self):
        self.path.write_bytes(b'not a ZIP')
        with self.assertRaises(ValueError) as error:
            api.validate_backup_archive(self.path)
        self.assertEqual(str(error.exception), '备份文件不是有效的 ZIP 文件。')
        self.assertIsInstance(error.exception.__cause__, zipfile.BadZipFile)
        self.path.unlink()
        with self.assertRaises(FileNotFoundError):
            api.validate_backup_archive(self.path)

    def test_crc_errors_are_mapped_as_invalid_zip(self):
        self.archive([('manifest.json', self.manifest()), ('database.dump', '')])
        with patch.object(zipfile.ZipFile, 'read', side_effect=zipfile.BadZipFile('CRC mismatch')):
            with self.assertRaises(ValueError) as error:
                api.validate_backup_archive(self.path)
        self.assertEqual(str(error.exception), '备份文件不是有效的 ZIP 文件。')

    def test_zip_handle_closes_on_success_and_validation_failure(self):
        original = zipfile.ZipFile
        for text in (self.manifest(), '{broken'):
            self.archive([('manifest.json', text), ('database.dump', '')])
            opened = []

            def open_zip(*args, **kwargs):
                handle = original(*args, **kwargs)
                opened.append(handle)
                return handle

            with patch.object(api.zipfile, 'ZipFile', side_effect=open_zip):
                try:
                    api.validate_backup_archive(self.path)
                except ValueError:
                    self.assertEqual(text, '{broken')
            self.assertEqual(len(opened), 1)
            self.assertIsNone(opened[0].fp)

    def test_duplicate_manifest_uses_last_entry_like_zipfile(self):
        self.archive([('manifest.json', self.manifest(note='first')),
                      ('manifest.json', self.manifest(note='last')), ('database.dump', '')])
        self.assertEqual(api.validate_backup_archive(self.path)['note'], 'last')

    def test_archive_manifest_validation_does_not_also_validate_storage_paths(self):
        self.archive([('manifest.json', self.manifest()), ('database.dump', ''), ('storage/../escape.txt', 'bad')])
        self.assertEqual(api.validate_backup_archive(self.path)['database_member'], 'database.dump')
        with zipfile.ZipFile(self.path) as archive:
            with self.assertRaisesRegex(ValueError, '备份文件中存在非法 storage 路径。'):
                api.validate_storage_backup_members(archive)

    def test_normal_storage_members_are_checked_without_extraction_or_directory_creation(self):
        self.archive([('storage/', ''), ('storage/photos/', ''), ('storage/photos/图.png', b'photo'),
                      ('storage/a/../valid.txt', 'valid'), ('ignored/file.txt', 'ignore')])
        with zipfile.ZipFile(self.path) as archive:
            self.assertIsNone(api.validate_storage_backup_members(archive))
        self.assertFalse(self.storage.exists())

    def test_traversal_absolute_and_sibling_prefix_members_are_rejected(self):
        for name in ('storage/../escape.txt', 'storage/a/../../escape.txt', 'storage/../../escape.txt',
                     'storage/../storage-lookalike/file.txt', 'storage/' + str(self.root / 'escape.txt')):
            with self.subTest(name=name):
                self.archive([(name, 'bad')])
                with zipfile.ZipFile(self.path) as archive, self.assertRaises(ValueError) as error:
                    api.validate_storage_backup_members(archive)
                self.assertEqual(str(error.exception), '备份文件中存在非法 storage 路径。')
                self.assertFalse((self.root / 'escape.txt').exists())

    def test_directory_and_non_storage_members_keep_existing_skip_rules(self):
        self.archive([('storage/../../directory/', ''), ('../outside.txt', 'ignore'), ('storage-other/../file.txt', '')])
        with zipfile.ZipFile(self.path) as archive:
            self.assertIsNone(api.validate_storage_backup_members(archive))

    def test_root_member_and_duplicate_storage_names_keep_existing_acceptance(self):
        self.archive([('storage/.', ''), ('storage/file.txt', 'first'), ('storage/file.txt', 'second')])
        with zipfile.ZipFile(self.path) as archive:
            self.assertIsNone(api.validate_storage_backup_members(archive))
        self.assertFalse(self.storage.exists())

    def test_backslash_members_follow_host_path_semantics_not_a_new_zip_policy(self):
        name = 'storage/..\\outside.txt'
        self.archive([(name, 'data')])
        with zipfile.ZipFile(self.path) as archive:
            if os.path.sep == '/':
                self.assertIsNone(api.validate_storage_backup_members(archive))
            else:
                with self.assertRaises(ValueError):
                    api.validate_storage_backup_members(archive)

    def test_storage_root_is_read_at_call_time(self):
        self.archive([('storage/' + str(self.root / 'another-root/file.txt'), 'data')])
        with zipfile.ZipFile(self.path) as archive, self.assertRaises(ValueError):
            api.validate_storage_backup_members(archive)
        with patch.object(api, 'STORAGE_ROOT', str(self.root / 'another-root')), zipfile.ZipFile(self.path) as archive:
            self.assertIsNone(api.validate_storage_backup_members(archive))
        self.assertFalse((self.root / 'another-root').exists())
