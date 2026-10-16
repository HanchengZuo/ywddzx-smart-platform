"""Characterize the public backup helpers before moving their pure calculations."""
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app as api


class BackupConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.path = self.root / 'config' / 'backup.json'
        self.stack.enter_context(patch.object(api, 'DEFAULT_BACKUP_DIR', str(self.root / 'archives')))
        self.stack.enter_context(patch.object(api, 'BACKUP_CONFIG_PATH', str(self.path)))
        self.now = datetime(2026, 1, 31, 2, 0, 40, 123, tzinfo=api.BEIJING_TZ)
        self.clock = self.stack.enter_context(patch.object(api, 'beijing_now', return_value=self.now))

    def save_raw(self, text):
        self.path.parent.mkdir(exist_ok=True)
        self.path.write_text(text, encoding='utf-8')

    def test_defaults_are_fresh_complete_and_do_not_create_files(self):
        config = api.get_default_backup_config()
        self.assertEqual(config, dict(
            destination_path=str(self.root / 'archives'), frequency='off', scheduled_time='02:00',
            next_auto_run_at=None, last_auto_export_at=None, last_backup_path=None,
            last_backup_size=None, last_cos_status='not_configured', last_cos_key=None,
            last_cos_uploaded_at=None, last_cos_retained_count=0, last_cos_error='',
            last_status='idle', last_error='', updated_at=None))
        config['last_status'] = 'changed'
        self.assertEqual(api.read_backup_config()['last_status'], 'idle')
        self.assertFalse(self.path.parent.exists())
        self.clock.assert_not_called()

    def test_destination_paths_keep_existing_absolute_relative_and_parent_semantics(self):
        for value, expected in ((None, self.root / 'archives'), (' sub/../local ', self.root / 'archives/local'),
                                ('../outside', self.root / 'outside'), (str(self.root / 'other'), self.root / 'other')):
            with self.subTest(value=value):
                self.assertEqual(api.normalize_backup_destination_path(value), str(expected))
        self.assertFalse((self.root / 'archives').exists())

    def test_scheduled_time_normalization_and_exact_validation_errors(self):
        for value, expected in ((None, '02:00'), (' ', '02:00'), (' 2:05 ', '02:05'), ('23:59', '23:59'), (0, '02:00')):
            self.assertEqual(api.normalize_backup_scheduled_time(value), expected)
            self.assertEqual(api.parse_backup_scheduled_time(value), tuple(map(int, expected.split(':'))))
        for value in ('2:5', '12:60', '-1:00', 'abc', '100:00'):
            with self.subTest(value=value), self.assertRaises(ValueError) as error:
                api.normalize_backup_scheduled_time(value)
            self.assertEqual(str(error.exception), '自动备份执行时间必须是 HH:MM 格式。')
        with self.assertRaises(ValueError) as error:
            api.normalize_backup_scheduled_time('24:00')
        self.assertEqual(str(error.exception), '自动备份执行时间小时必须在 00-23 之间。')

    def test_read_bad_json_non_object_and_read_failure_fall_back_without_writing(self):
        for text in ('{broken', '[]', 'null', '123'):
            self.save_raw(text)
            self.assertEqual(api.read_backup_config(), api.get_default_backup_config())
            self.assertEqual(self.path.read_text(encoding='utf-8'), text)
        with patch('builtins.open', side_effect=OSError('unreadable')):
            self.assertEqual(api.read_backup_config(), api.get_default_backup_config())

    def test_read_merges_metadata_normalizes_and_does_not_rewrite(self):
        data = dict(destination_path='relative', frequency='unknown', scheduled_time='1:30',
                    next_auto_run_at='2026-01-01T00:00:00+08:00', extra={'keep': '中文'}, last_status='warning')
        text = json.dumps(data)
        self.save_raw(text)
        config = api.read_backup_config()
        self.assertEqual(config['destination_path'], str(self.root / 'archives/relative'))
        self.assertEqual((config['frequency'], config['scheduled_time'], config['next_auto_run_at']), ('off', '01:30', None))
        self.assertEqual(config['extra'], data['extra'])
        self.assertEqual(config['last_status'], 'warning')
        self.assertEqual(self.path.read_text(), text)
        self.clock.assert_not_called()

    def test_invalid_saved_time_still_raises_even_when_backups_are_off(self):
        self.save_raw('{"frequency": "off", "scheduled_time": "invalid"}')
        with self.assertRaises(ValueError):
            api.read_backup_config()

    def test_write_preserves_input_and_metadata_and_uses_original_json_format(self):
        data = dict(destination_path='relative', frequency='daily', scheduled_time='3:15',
                    next_auto_run_at='saved', extra={'keep': '中文'}, last_backup_path='previous.zip')
        original = deepcopy(data)
        result = api.write_backup_config(data)
        self.assertEqual(data, original)
        self.assertEqual(result['updated_at'], self.now.isoformat())
        self.assertEqual(result['next_auto_run_at'], 'saved')
        self.assertEqual(result['last_backup_path'], 'previous.zip')
        self.assertEqual(self.path.read_text(encoding='utf-8'), json.dumps(result, ensure_ascii=False, indent=2))
        self.assertFalse((self.root / 'archives').exists())
        self.clock.assert_called_once_with()
        self.assertIsNone(api.write_backup_config({'frequency': 'invalid', 'next_auto_run_at': 'saved'})['next_auto_run_at'])

    def test_validation_precedes_clock_mkdir_and_truncation(self):
        self.save_raw('preserve me')
        with patch.object(api.os, 'makedirs') as mkdir:
            with self.assertRaises(ValueError):
                api.write_backup_config({'scheduled_time': '25:00'})
        mkdir.assert_not_called()
        self.clock.assert_not_called()
        self.assertEqual(self.path.read_text(), 'preserve me')

    def test_write_failure_propagates_without_claiming_success(self):
        with patch.object(api.os, 'makedirs', side_effect=OSError('disk unavailable')):
            with self.assertRaisesRegex(OSError, 'disk unavailable'):
                api.write_backup_config({})
        self.clock.assert_called_once_with()
        self.assertFalse(self.path.exists())

    def test_frequency_boundaries_keep_thirty_day_month_and_truncation(self):
        for frequency, expected in (
            ('hourly', '2026-01-31T03:00:00+08:00'), ('daily', '2026-02-01T02:00:00+08:00'),
            ('weekly', '2026-02-07T02:00:00+08:00'), ('monthly', '2026-03-02T02:00:00+08:00')):
            with self.subTest(frequency=frequency):
                self.assertEqual(api.calculate_next_auto_run_at({'frequency': frequency}, self.now), expected)
        self.clock.assert_not_called()
        before = self.now.replace(hour=1)
        for frequency in ('daily', 'weekly', 'monthly'):
            self.assertEqual(api.calculate_next_auto_run_at({'frequency': frequency}, before), '2026-01-31T02:00:00+08:00')
        exact = self.now.replace(second=0, microsecond=0)
        self.assertEqual(api.calculate_next_auto_run_at({'frequency': 'daily'}, exact), '2026-02-01T02:00:00+08:00')

    def test_timezone_conversion_and_hourly_ignores_scheduled_time(self):
        utc = datetime(2026, 1, 30, 20, 5, 59, tzinfo=timezone.utc)
        self.assertEqual(api.calculate_next_auto_run_at({'frequency': 'hourly', 'scheduled_time': 'bad'}, utc),
                         '2026-01-31T05:05:00+08:00')
        self.assertEqual(api.calculate_next_auto_run_at({'frequency': 'daily', 'scheduled_time': '5:00'}, utc),
                         '2026-01-31T05:00:00+08:00')

    def test_disabled_and_saved_next_run_paths_do_not_evaluate_clock(self):
        self.clock.side_effect = AssertionError('clock should remain lazy')
        for frequency in ('off', 'unknown', None):
            self.assertIsNone(api.calculate_next_auto_run_at({'frequency': frequency, 'scheduled_time': 'bad'}))
        self.assertIsNone(api.get_backup_next_run_at({'frequency': 'off', 'next_auto_run_at': '2020-01-01'}))
        self.assertEqual(api.get_backup_next_run_at({'frequency': 'unknown', 'scheduled_time': 'bad',
                                                   'next_auto_run_at': '2020-01-01T00:00:00Z'}),
                         '2020-01-01T08:00:00+08:00')

    def test_invalid_saved_next_run_falls_back_to_calculation(self):
        for value in (None, '', 'bad'):
            self.assertIsNone(api.parse_backup_time(value))
            self.assertEqual(api.get_backup_next_run_at({'frequency': 'hourly', 'next_auto_run_at': value}),
                             '2026-01-31T03:00:00+08:00')
        self.assertEqual(self.clock.call_count, 3)
        self.assertEqual(api.parse_backup_time('2026-01-01'), datetime(2026, 1, 1))
