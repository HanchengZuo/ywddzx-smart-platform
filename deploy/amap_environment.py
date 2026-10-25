"""Load only the backend AMap Web-service key; never execute shell startup code."""
import os
from pathlib import Path
import re
import shlex
import sys

KEY = 'AMAP_WEB_SERVICE_KEY'
ALIASES = (KEY, 'AMAP_KEY')


def load_environment(environ, *, fallback_paths=None):
    env = dict(environ)
    for name in ALIASES:
        if env.get(name, '').strip():
            env[KEY] = env[name].strip()
            return env, '部署环境 / 项目 .env · ' + name
    explicit = env.get('AMAP_KEYS_ENV_FILE', '').strip()
    paths = [(Path(explicit or '/etc/ywddzx/amap.env'), bool(explicit))]
    home = Path(env.get('HOME') or Path.home())
    paths += [(Path(p), False) for p in (fallback_paths if fallback_paths is not None else [
        '/etc/environment', home / '.profile', home / '.bash_profile', home / '.bashrc', home / '.zprofile', home / '.zshrc'])]
    for path, required in paths:
        try:
            content = path.read_text(encoding='utf-8')
        except FileNotFoundError:
            if required:
                raise RuntimeError('指定的高德配置文件不存在。') from None
            continue
        except (OSError, UnicodeError):
            raise RuntimeError('高德配置文件无法读取。') from None
        found = {}
        for line in content.splitlines():
            match = re.match(r'^\s*(?:export\s+)?(AMAP_WEB_SERVICE_KEY|AMAP_KEY)\s*=\s*(.*)$', line)
            if not match:
                continue
            try:
                values = shlex.split(match[2], comments=True)
            except ValueError:
                continue
            if len(values) == 1 and values[0] and not any(c in values[0] for c in '$`;|&<>\x00\r\n'):
                found[match[1]] = values[0]
        for name in ALIASES:
            if name in found:
                env[KEY] = found[name]
                return env, str(path) + ' · ' + name
    return env, None


def main(argv):
    try:
        env, source = load_environment(os.environ)
        if argv == ['--check']:
            print('[高德驾车配置] ' + ('已配置 · ' + source if source else '未配置Web服务Key；地图浏览不受影响，驾车智能排班会提示配置。'))
            return 0
        if not argv:
            return 2
        os.execvpe(argv[0], argv, env)
    except (RuntimeError, OSError) as exc:
        print('高德部署配置读取失败：' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
