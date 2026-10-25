import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

spec = importlib.util.spec_from_file_location('amap_environment', Path(__file__).resolve().parents[2] / 'deploy/amap_environment.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class EnvironmentTests(unittest.TestCase):
    def test_existing_environment_wins_and_only_web_service_key_is_loaded(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'amap.env'
            path.write_text('VITE_AMAP_KEY=browser-only\nAMAP_WEB_SERVICE_KEY=web-only\nOTHER_SECRET=not-used\n')
            env, source = module.load_environment(dict(AMAP_KEYS_ENV_FILE=str(path)), fallback_paths=[])
            self.assertEqual(env[module.KEY], 'web-only')
            self.assertEqual(source, str(path) + ' · AMAP_WEB_SERVICE_KEY')
            self.assertNotIn('VITE_AMAP_KEY', env)
            self.assertNotIn('OTHER_SECRET', env)
            env, _ = module.load_environment(dict(AMAP_WEB_SERVICE_KEY='existing', AMAP_KEYS_ENV_FILE=str(path)))
            self.assertEqual(env[module.KEY], 'existing')
            env, _ = module.load_environment(dict(AMAP_KEY='alias-from-system'))
            self.assertEqual(env[module.KEY], 'alias-from-system')
            path.write_text('export AMAP_KEY="alias-from-bashrc"\n')
            env, _ = module.load_environment(dict(AMAP_KEYS_ENV_FILE=str(path)), fallback_paths=[])
            self.assertEqual(env[module.KEY], 'alias-from-bashrc')

    def test_shell_is_never_executed_and_explicit_missing_file_fails_safely(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'amap.env'
            marker = Path(folder) / 'never-created'
            path.write_text(f'AMAP_WEB_SERVICE_KEY=$(touch {marker})\n')
            env, source = module.load_environment(dict(AMAP_KEYS_ENV_FILE=str(path)), fallback_paths=[])
            self.assertNotIn(module.KEY, env)
            self.assertIsNone(source)
            self.assertFalse(marker.exists())
            with self.assertRaises(RuntimeError):
                module.load_environment(dict(AMAP_KEYS_ENV_FILE=str(path) + '.missing'), fallback_paths=[])
