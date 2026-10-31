import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

spec=importlib.util.spec_from_file_location('web_push_environment',Path(__file__).resolve().parents[2]/'deploy/web_push_environment.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class EnvironmentTests(unittest.TestCase):
    def test_persistent_file_only_loads_whitelisted_values_without_replacing_existing_identity(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)/'push.env'
            path.write_text('WEB_PUSH_ENABLED=true\nWEB_PUSH_VAPID_PRIVATE_KEY=test-secret\nWEB_PUSH_SUBJECT=https://example.com\nUNRELATED_SECRET=ignore\n')
            path.chmod(0o600)
            env,source=module.load_environment({'WEB_PUSH_ENV_FILE':str(path)})
            self.assertEqual(env['WEB_PUSH_VAPID_PRIVATE_KEY'],'test-secret');self.assertEqual(source,str(path))
            self.assertNotIn('UNRELATED_SECRET',env)
            env,_=module.load_environment({'WEB_PUSH_ENV_FILE':str(path),'WEB_PUSH_VAPID_PRIVATE_KEY':'existing',
                'WEB_PUSH_SUBJECT':'https://existing.example','WEB_PUSH_ENABLED':'false'})
            self.assertEqual(env['WEB_PUSH_VAPID_PRIVATE_KEY'],'existing');self.assertEqual(env['WEB_PUSH_ENABLED'],'false')

    def test_shell_commands_permissions_and_incomplete_configuration_are_rejected_without_leaks(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)/'push.env';marker=Path(folder)/'never-created'
            path.write_text(f'WEB_PUSH_VAPID_PRIVATE_KEY=$(touch {marker})\n');path.chmod(0o600)
            with self.assertRaises(RuntimeError) as error:module.load_environment({'WEB_PUSH_ENV_FILE':str(path)})
            self.assertNotIn('touch',str(error.exception));self.assertFalse(marker.exists())
            path.chmod(0o644)
            with self.assertRaisesRegex(RuntimeError,'0600'):module.load_environment({'WEB_PUSH_ENV_FILE':str(path)})
            with self.assertRaisesRegex(RuntimeError,'不存在'):module.load_environment({'WEB_PUSH_ENV_FILE':str(path)+'.missing'})
            path.chmod(0o600);path.write_text('')
            with self.assertRaisesRegex(RuntimeError,'不完整'):module.load_environment({'WEB_PUSH_VAPID_PRIVATE_KEY':'secret','WEB_PUSH_ENV_FILE':str(path)})
