import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
import unittest

spec=importlib.util.spec_from_file_location('driving_timer',Path(__file__).resolve().parents[2]/'deploy/install_driving_timer.py')
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class TimerTests(unittest.TestCase):
    def test_calendar_is_shanghai_persistent_and_has_no_gunicorn_thread(self):
        service,timer=module.units('/tmp/project with spaces')
        self.assertIn('OnCalendar=Mon *-*-* 09:30:00 Asia/Shanghai',timer)
        self.assertIn('Persistent=true',timer)
        self.assertIn('Type=oneshot',service)
        self.assertIn('docker exec -w /app ywddzx-backend python /app/driving_matrix_cli.py',service)
        self.assertNotIn('app.py',service)
        self.assertIn('WorkingDirectory='+str(Path('/tmp/project with spaces').resolve())+'\n',service)

    def test_installer_can_only_touch_test_directory_and_mock_systemctl(self):
        with TemporaryDirectory() as folder:
            run=Mock()
            module.install('/tmp/test-project',Path(folder),run)
            self.assertTrue((Path(folder)/'ywddzx-driving-refresh.timer').is_file())
            self.assertEqual(run.call_args_list[-1].args[0],['systemctl','start','--no-block','ywddzx-driving-refresh.service'])
            self.assertEqual(len(run.call_args_list),3)
