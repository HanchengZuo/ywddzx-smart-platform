"""Development startup contracts, without Docker, networks or application data."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless((ROOT / 'frontend/scripts/dev-entrypoint.sh').is_file(), 'requires the complete repository checkout')
class LocalFrontendStartupTests(unittest.TestCase):
    def test_install_once_reuse_invalidate_and_do_not_stamp_failed_installs(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            bin_dir = folder / 'bin'
            bin_dir.mkdir()
            (bin_dir / 'node').write_text('#!/bin/sh\nprintf "%s" "$TEST_FINGERPRINT"\n')
            (bin_dir / 'npm').write_text('''#!/bin/sh
printf '%s\n' "$*" >> "$TEST_CALLS"
if [ "$1" = ci ]; then
  [ "${TEST_FAIL:-0}" != 1 ] || exit 1
  mkdir -p node_modules/.bin
  touch node_modules/.bin/vite
  chmod +x node_modules/.bin/vite
fi
''')
            for path in bin_dir.iterdir():
                path.chmod(0o755)
            script = (ROOT / 'frontend/scripts/dev-entrypoint.sh').read_text().replace('cd /app', 'cd ' + shlex.quote(directory))
            log = folder / 'calls'
            env = dict(os.environ, PATH=str(bin_dir) + ':' + os.environ['PATH'], TEST_CALLS=str(log), TEST_FINGERPRINT='first')
            def run(**extra):
                result = subprocess.run(['sh', '-c', script], env=dict(env, **extra), capture_output=True, text=True)
                calls = log.read_text().splitlines()
                log.unlink()
                return result, calls
            result, calls = run()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(calls[0].startswith('ci --prefer-offline'))
            result, calls = run()
            self.assertEqual(calls, ['run dev -- --host 0.0.0.0 --strictPort'])
            self.assertIn('reusing node_modules', result.stdout)
            result, calls = run(TEST_FINGERPRINT='changed', TEST_FAIL='1')
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((folder / 'node_modules/.ywddzx-dev-dependencies').read_text(), 'first')
            result, calls = run(TEST_FINGERPRINT='changed')
            self.assertEqual(result.returncode, 0)
            self.assertTrue(calls[0].startswith('ci '))
            (folder / 'node_modules/.bin/vite').unlink()
            _, calls = run(TEST_FINGERPRINT='changed')
            self.assertTrue(calls[0].startswith('ci '))
