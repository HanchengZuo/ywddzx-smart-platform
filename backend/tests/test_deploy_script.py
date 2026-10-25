import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_VARS = (
    'APP_SECRET_KEY', 'DB_PASSWORD', 'WEBAUTHN_RP_ID',
    'WEBAUTHN_ORIGIN', 'CORS_ALLOWED_ORIGINS',
)
AI_KEYS = ('DEEPSEEK_API_KEY', 'ZHIPU_API_KEY', 'DASHSCOPE_API_KEY', 'MIMO_API_KEY')


class DeploymentScriptTests(unittest.TestCase):
    """Run only against fake commands and an isolated copy; never deploy anything."""

    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.repo = self.root / 'repo'
        (self.repo / 'frontend').mkdir(parents=True)
        shutil.copy(PROJECT_ROOT / 'deploy.sh', self.repo / 'deploy.sh')
        (self.repo / 'deploy').mkdir()
        shutil.copy(PROJECT_ROOT / 'deploy/ai_environment.py', self.repo / 'deploy/ai_environment.py')
        shutil.copy(PROJECT_ROOT / 'deploy/amap_environment.py', self.repo / 'deploy/amap_environment.py')
        self.version = json.loads((PROJECT_ROOT / 'frontend/package.json').read_text())['version']
        (self.repo / 'frontend/package.json').write_text(json.dumps({'version': self.version}))
        self.log = self.root / 'commands.log'
        self.env = dict(os.environ, PATH=f'{self.bin}:/usr/bin:/bin', TEST_LOG=str(self.log),
                        TEST_PYTHON=sys.executable)
        for key in (*REQUIRED_VARS, *AI_KEYS, 'APP_FRONTEND_VERSION', 'APP_ENV', 'TRUST_PROXY_HEADERS'):
            self.env.pop(key, None)
        self.keys_file = self.root / 'ai.env'
        self.keys_file.write_text('\n'.join(f'{key}=fake-deploy-key-{key}' for key in AI_KEYS))
        self.env['AI_KEYS_ENV_FILE'] = str(self.keys_file)
        self.amap_keys_file = self.root / 'amap.env'
        self.amap_keys_file.write_text('AMAP_KEY=test-only-web-service-key\n')
        self.env['AMAP_KEYS_ENV_FILE'] = str(self.amap_keys_file)
        shim = self.bin / 'shim'
        shim.write_text('''#!/bin/bash
name="${0##*/}"
printf '%s %s\\n' "$name" "$*" >> "$TEST_LOG"
case "$name" in
  git) [ "${FAIL_PHASE:-}" != pull ] ;;
  python3) exec "$TEST_PYTHON" "$@" ;;
  npm)
    if [ "${FAIL_PHASE:-}" = build ] && [ "$*" = 'run build' ]; then exit 1; fi
    if [ "$*" = 'run build' ] && [ "${FAIL_PHASE:-}" != empty-build ]; then
      /bin/mkdir -p dist
      printf '<html>test only</html>' > dist/index.html
    fi
    ;;
  docker|docker-compose)
    if [ "$name" = docker ]; then
      [ "$1" = compose ] || exit 1
      shift
      if [ "$1" = version ]; then [ "${COMPOSE_V1:-}" != 1 ]; exit $?; fi
    fi
    case "$1" in
      ps) [ "${WITH_FRONTEND:-}" != 1 ] || printf 'old-vite-container\\n' ;;
      up)
        printf 'backend-env version=%s env=%s proxy=%s\\n' "$APP_FRONTEND_VERSION" "$APP_ENV" "$TRUST_PROXY_HEADERS" >> "$TEST_LOG"
        for key in DEEPSEEK_API_KEY ZHIPU_API_KEY DASHSCOPE_API_KEY MIMO_API_KEY; do
          [ -z "${!key:-}" ] || printf 'backend-ai %s=present\\n' "$key" >> "$TEST_LOG"
        done
        [ -z "${AMAP_WEB_SERVICE_KEY:-}" ] || printf 'backend-amap=present\\n' >> "$TEST_LOG"
        if [ -n "${EXPECTED_ZHIPU_API_KEY:-}" ]; then
          [ "$ZHIPU_API_KEY" = "$EXPECTED_ZHIPU_API_KEY" ] || exit 1
        fi
        [ "${FAIL_PHASE:-}" != backend ] ;;
      exec)
        if [ "$4" = sh ]; then [ "${FAIL_PHASE:-}" != timeout ];
        else [ "${FAIL_PHASE:-}" != schema ]; fi ;;
    esac
    ;;
  mkdir|find|cp|sleep) : ;;
  *) exit 1 ;;
esac
''')
        shim.chmod(0o755)
        for name in ('git', 'python3', 'npm', 'docker', 'docker-compose', 'mkdir', 'find', 'cp', 'sleep'):
            (self.bin / name).symlink_to(shim)

    def configure(self, missing=None):
        values = {key: 'test-only' for key in REQUIRED_VARS if key != missing}
        values['APP_FRONTEND_VERSION'] = '0.1.0'
        (self.repo / '.env').write_text('\n'.join(f'{key}={shlex.quote(value)}' for key, value in values.items()))

    def run_script(self, **overrides):
        result = subprocess.run(['bash', str(self.repo / 'deploy.sh')], cwd=self.root,
                                env=dict(self.env, **overrides), capture_output=True, text=True, timeout=10)
        commands = self.log.read_text().splitlines() if self.log.exists() else []
        return result, commands

    def test_success_pulls_once_deploys_in_order_and_uses_package_version(self):
        self.configure()
        result, commands = self.run_script(WITH_FRONTEND='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(commands.count('git pull --ff-only'), 1)
        self.assertIn('npm ci --include=dev', commands)
        publish = commands.index('cp -a frontend/dist/. /var/www/ywddzx/')
        backend = commands.index('docker compose up --build --force-recreate -d backend')
        self.assertLess(commands.index('npm run build'), publish)
        self.assertLess(publish, commands.index('docker compose stop frontend'))
        self.assertLess(commands.index('docker compose rm -f frontend'), backend)
        self.assertIn(f'backend-env version={self.version} env=production proxy=true', commands)
        self.assertIn('docker compose exec -T backend python /app/ensure_runtime_schema.py', commands)
        self.assertNotIn('test-only', result.stdout + result.stderr)
        for key in AI_KEYS:
            self.assertIn(f'backend-ai {key}=present', commands)
            self.assertNotIn(f'fake-deploy-key-{key}', result.stdout + result.stderr + '\n'.join(commands))
        self.assertIn('backend-amap=present', commands)
        self.assertNotIn('test-only-web-service-key', result.stdout + result.stderr + '\n'.join(commands))

    def test_existing_project_and_exported_keys_are_not_overridden_by_fallback_file(self):
        self.configure()
        result, _ = self.run_script(ZHIPU_API_KEY='exported-test-key', EXPECTED_ZHIPU_API_KEY='exported-test-key')
        self.assertEqual(result.returncode, 0, result.stderr)
        with (self.repo / '.env').open('a') as file:
            file.write('\nZHIPU_API_KEY=project-test-key\n')
        result, _ = self.run_script(ZHIPU_API_KEY='exported-test-key', EXPECTED_ZHIPU_API_KEY='project-test-key')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_explicit_missing_key_file_stops_before_build_or_publish(self):
        self.configure()
        result, commands = self.run_script(AI_KEYS_ENV_FILE=str(self.root / 'missing.env'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('AI 密钥配置文件不存在', result.stderr)
        self.assertFalse(any(line.startswith(('npm ', 'find ', 'cp ')) or ' up ' in line for line in commands))

    def test_legacy_compose_and_absent_frontend_container(self):
        self.configure()
        result, commands = self.run_script(COMPOSE_V1='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('docker-compose up --build --force-recreate -d backend', commands)
        self.assertFalse(any('stop frontend' in line or 'rm -f frontend' in line for line in commands))

    def test_missing_config_stops_before_build_or_publish(self):
        self.configure(missing='DB_PASSWORD')
        result, commands = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DB_PASSWORD', result.stderr)
        self.assertFalse(any(line.startswith(('npm ', 'find ', 'cp ')) for line in commands))

    def test_pull_and_build_failures_do_not_publish(self):
        self.configure()
        for phase in ('pull', 'build', 'empty-build'):
            with self.subTest(phase=phase):
                if self.log.exists():
                    self.log.unlink()
                result, commands = self.run_script(FAIL_PHASE=phase)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(any(line.startswith(('find ', 'cp ')) or ' up ' in line for line in commands))

    def test_backend_start_or_schema_failure_is_not_reported_as_success(self):
        self.configure()
        for phase in ('backend', 'schema'):
            with self.subTest(phase=phase):
                result, _ = self.run_script(FAIL_PHASE=phase)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('部署失败', result.stderr)
                self.assertNotIn('前端与后端部署完成', result.stdout)

    def test_readiness_timeout_reports_logs_and_does_not_run_schema_check(self):
        self.configure()
        result, commands = self.run_script(FAIL_PHASE='timeout')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('120 秒', result.stderr)
        self.assertIn('docker compose logs --tail=120 backend', commands)
        self.assertEqual(sum('grep -q gunicorn' in line for line in commands), 60)
        self.assertFalse(any('ensure_runtime_schema.py' in line for line in commands))


if __name__ == '__main__':
    unittest.main()
