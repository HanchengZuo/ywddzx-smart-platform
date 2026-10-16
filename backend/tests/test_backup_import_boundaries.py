"""Fresh-process checks so import safety is not hidden by the parent's module cache."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class BackupImportBoundaryTests(unittest.TestCase):
    def test_local_files_import_needs_no_app_or_io(self):
        source = '''
import sys
from unittest.mock import patch
def forbidden(*args, **kwargs):
    raise AssertionError('unexpected local backup module import side effect')
with patch('builtins.open', side_effect=forbidden), \\
     patch('os.makedirs', side_effect=forbidden), \\
     patch('socket.socket.connect', side_effect=forbidden), \\
     patch('threading.Thread.start', side_effect=forbidden), \\
     patch('subprocess.Popen', side_effect=forbidden):
    import backups.local_files
    assert not {'app', 'flask', 'psycopg2', 'qcloud_cos'}.intersection(sys.modules)
'''
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, '-c', source], cwd=root,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_archive_validation_import_needs_no_app_or_io(self):
        source = '''
import sys
from unittest.mock import patch
def forbidden(*args, **kwargs):
    raise AssertionError('unexpected archive validation import side effect')
with patch('builtins.open', side_effect=forbidden), \\
     patch('os.makedirs', side_effect=forbidden), \\
     patch('socket.socket.connect', side_effect=forbidden), \\
     patch('threading.Thread.start', side_effect=forbidden), \\
     patch('subprocess.Popen', side_effect=forbidden):
    import backups.archive_validation
    import backups.local_files
    assert not {'app', 'flask', 'psycopg2', 'qcloud_cos'}.intersection(sys.modules)
'''
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, '-c', source], cwd=root,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cos_module_import_needs_no_sdk_flask_or_io(self):
        source = '''
import sys
from unittest.mock import patch
def forbidden(*args, **kwargs):
    raise AssertionError('unexpected COS module import side effect')
with patch('builtins.open', side_effect=forbidden), \\
     patch('os.makedirs', side_effect=forbidden), \\
     patch('socket.socket.connect', side_effect=forbidden), \\
     patch('threading.Thread.start', side_effect=forbidden), \\
     patch('subprocess.Popen', side_effect=forbidden):
    import backups.cos
    assert not {'app', 'flask', 'psycopg2', 'qcloud_cos'}.intersection(sys.modules)
'''
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, '-c', source], cwd=root,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_backup_components_import_without_app_io_or_worker_start(self):
        source = '''
import sys
from unittest.mock import patch
def forbidden(*args, **kwargs):
    raise AssertionError('unexpected import side effect')
with patch('os.makedirs', side_effect=forbidden), \\
     patch('socket.socket.connect', side_effect=forbidden), \\
     patch('threading.Thread.start', side_effect=forbidden), \\
     patch('subprocess.Popen', side_effect=forbidden):
    import backups.http
    import backups.transfers
    import backups.configuration
    import backups.cos
    import backups.archive_validation
    assert 'app' not in sys.modules
    assert 'qcloud_cos' not in sys.modules
'''
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, '-c', source], cwd=root,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_fresh_application_import_preserves_endpoints_limits_and_idle_scheduler(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            shutil.copy2(root / 'app.py', Path(directory) / 'app.py')
            shutil.copytree(root / 'backups', Path(directory) / 'backups', ignore=shutil.ignore_patterns('__pycache__'))
            env = {**os.environ, 'PYTHONPATH': os.pathsep.join([directory, str(root), os.environ.get('PYTHONPATH', '')])}
            result = subprocess.run([sys.executable, str(root / 'tests/backup_app_probe.py')], cwd=directory,
                                    env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        snapshot = json.loads(result.stdout)
        rules = {path: (endpoint, methods) for path, endpoint, methods in snapshot['routes']}
        self.assertEqual(rules['/api/management/backups/export'], ('export_management_full_backup', ['OPTIONS', 'POST']))
        self.assertEqual(rules['/api/management/backups/import'], ('import_management_full_backup', ['OPTIONS', 'POST']))
        self.assertEqual(snapshot['request_class'], 'PlatformRequest')
        self.assertEqual(snapshot['limits']['MAX_CONTENT_LENGTH'], 550 * 1024 * 1024)
        self.assertFalse(snapshot['backup_scheduler_started'])
        self.assertEqual(snapshot['before_request'].count('ensure_backup_scheduler_started'), 1)
