"""Use literal temporary configuration and fake commands, never real provider keys."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


LOADER_PATH = Path(__file__).resolve().parents[2] / 'deploy/ai_environment.py'
spec = importlib.util.spec_from_file_location('deploy_ai_environment', LOADER_PATH)
loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loader)


class AiEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        default_file = patch.object(loader, 'DEFAULT_KEYS_FILE', self.root / 'not-configured.env')
        default_file.start()
        self.addCleanup(default_file.stop)

    def file(self, name, content):
        target = self.root / name
        target.write_text(content)
        return target

    def test_noninteractive_shell_guard_does_not_hide_literal_exports(self):
        bashrc = self.file('.bashrc', '''case $- in *i*) ;; *) return;; esac
export ZHIPU_API_KEY="fake-glm"
export DASHSCOPE_API_KEY='fake-qwen'
export MIMO_API_KEY=fake-mimo # test only
export UNRELATED_SECRET=never-import
''')
        original = {'DEEPSEEK_API_KEY': 'fake-deepseek', 'APP_ENV': 'production'}
        env, sources = loader.load_environment(original, fallback_paths=[bashrc])
        self.assertEqual([env[name] for name in loader.AI_KEYS], ['fake-deepseek', 'fake-glm', 'fake-qwen', 'fake-mimo'])
        self.assertNotIn('UNRELATED_SECRET', env)
        self.assertEqual(sources['ZHIPU_API_KEY'], str(bashrc))
        self.assertNotIn('ZHIPU_API_KEY', original)

    def test_existing_environment_and_dedicated_file_take_precedence(self):
        dedicated = self.file('ai.env', 'ZHIPU_API_KEY=dedicated\nDASHSCOPE_API_KEY=""')
        system = self.file('system.env', 'DEEPSEEK_API_KEY=wrong\nZHIPU_API_KEY=wrong\nDASHSCOPE_API_KEY=system')
        profile = self.file('.bashrc', 'DASHSCOPE_API_KEY=wrong\nMIMO_API_KEY=profile')
        env, _ = loader.load_environment({'AI_KEYS_ENV_FILE': str(dedicated), 'DEEPSEEK_API_KEY': 'existing'},
                                         fallback_paths=[system, profile])
        self.assertEqual([env[name] for name in loader.AI_KEYS], ['existing', 'dedicated', 'system', 'profile'])

    def test_only_simple_key_assignments_are_read_and_no_shell_code_is_executed(self):
        marker = self.root / 'must-not-exist'
        source = self.file('.bashrc', f'''touch {marker}
export ZHIPU_API_KEY="$(touch {marker})"
DASHSCOPE_API_KEY=$OTHER_SECRET
MIMO_API_KEY=`whoami`
COS_SECRET_KEY=unrelated
DEEPSEEK_API_KEY='fake # quoted = key'
''')
        env, _ = loader.load_environment({}, fallback_paths=[source])
        self.assertEqual(env, {'DEEPSEEK_API_KEY': 'fake # quoted = key'})
        self.assertFalse(marker.exists())

    def test_empty_malformed_and_duplicate_values_do_not_hide_valid_fallbacks(self):
        first = self.file('one.env', '''ZHIPU_API_KEY=first
ZHIPU_API_KEY=last
DASHSCOPE_API_KEY='unclosed
MIMO_API_KEY=
''')
        second = self.file('two.env', 'DASHSCOPE_API_KEY=good\nMIMO_API_KEY=good')
        env, _ = loader.load_environment({}, fallback_paths=[first, self.root / 'missing', second])
        self.assertEqual(env['ZHIPU_API_KEY'], 'last')
        self.assertEqual(env['DASHSCOPE_API_KEY'], 'good')
        self.assertEqual(env['MIMO_API_KEY'], 'good')

    def test_no_configuration_is_optional_but_explicit_missing_or_unreadable_file_fails_safely(self):
        env, sources = loader.load_environment({}, fallback_paths=[])
        self.assertEqual((env, sources), ({}, {}))
        with self.assertRaisesRegex(RuntimeError, '不存在'):
            loader.load_environment({'AI_KEYS_ENV_FILE': str(self.root / 'missing')}, fallback_paths=[])
        invalid = self.file('invalid.env', '')
        with patch.object(Path, 'read_text', side_effect=PermissionError('private content')):
            with self.assertRaisesRegex(RuntimeError, '无法读取') as caught:
                loader.load_environment({'AI_KEYS_ENV_FILE': str(invalid)}, fallback_paths=[])
        self.assertNotIn('private content', str(caught.exception))

    def test_cli_passes_keys_to_child_without_printing_values_and_preserves_exit_status(self):
        keys = self.file('ai.env', '\n'.join(f'{name}=fake-only-{name}' for name in loader.AI_KEYS))
        environment = {name: value for name, value in os.environ.items() if name not in loader.AI_KEYS}
        environment['AI_KEYS_ENV_FILE'] = str(keys)
        checked = subprocess.run([sys.executable, str(LOADER_PATH), '--check'], env=environment,
                                 text=True, capture_output=True, timeout=10)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        for name in loader.AI_KEYS:
            self.assertIn(name + '：已配置', checked.stdout)
            self.assertNotIn('fake-only-' + name, checked.stdout + checked.stderr)
        code = 'import json,os;print(json.dumps({k:os.environ.get(k)=="fake-only-"+k for k in ' + repr(loader.AI_KEYS) + '}))'
        child = subprocess.run([sys.executable, str(LOADER_PATH), sys.executable, '-c', code], env=environment,
                               text=True, capture_output=True, timeout=10)
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertEqual(json.loads(child.stdout), dict.fromkeys(loader.AI_KEYS, True))
        failed = subprocess.run([sys.executable, str(LOADER_PATH), sys.executable, '-c', 'raise SystemExit(23)'],
                                env=environment, text=True, capture_output=True, timeout=10)
        self.assertEqual(failed.returncode, 23)
        self.assertNotIn('fake-only-', failed.stdout + failed.stderr)
