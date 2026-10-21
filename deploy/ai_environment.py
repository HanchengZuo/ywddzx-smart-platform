"""Load only provider keys for Compose, without executing shell startup files."""
import os
from pathlib import Path
import re
import shlex
import sys


AI_KEYS = ('DEEPSEEK_API_KEY', 'ZHIPU_API_KEY', 'DASHSCOPE_API_KEY', 'MIMO_API_KEY')
DEFAULT_KEYS_FILE = Path('/etc/ywddzx/ai.env')
ASSIGNMENT = re.compile(r'^\s*(?:export\s+)?(' + '|'.join(AI_KEYS) + r')\s*=\s*(.*)$')


def read_literal_keys(path, *, required=False):
    try:
        content = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        if required:
            raise RuntimeError(f'AI 密钥配置文件不存在：{path}') from None
        return {}
    except (OSError, UnicodeError):
        raise RuntimeError(f'AI 密钥配置文件无法读取：{path}') from None
    values = {}
    for line in content.splitlines():
        match = ASSIGNMENT.match(line)
        if not match:
            continue
        name, raw = match.groups()
        try:
            tokens = shlex.split(raw, comments=True, posix=True)
        except ValueError:
            continue
        if not tokens:
            values[name] = ''
        elif len(tokens) == 1 and not any(char in tokens[0] for char in '$`;|&<>\x00\r\n'):
            values[name] = tokens[0]
    return values


def load_environment(environ, *, fallback_paths=None):
    env = dict(environ)
    # The existing deployment environment (including project .env) always wins.
    sources = {name: '部署环境 / 项目 .env' for name in AI_KEYS if env.get(name, '').strip()}
    explicit = env.get('AI_KEYS_ENV_FILE', '').strip()
    paths = [(Path(explicit) if explicit else DEFAULT_KEYS_FILE, bool(explicit))]
    if fallback_paths is None:
        home = Path(env.get('HOME') or Path.home())
        fallback_paths = [Path('/etc/environment'), home / '.profile', home / '.bash_profile',
                          home / '.bashrc', home / '.zprofile', home / '.zshrc']
    paths.extend((Path(path), False) for path in fallback_paths)
    for path, required in paths:
        if len(sources) == len(AI_KEYS):
            break
        for name, value in read_literal_keys(path, required=required).items():
            if name not in sources and value.strip():
                env[name] = value
                sources[name] = str(path)
    return env, sources


def main(argv):
    if not argv:
        print('用法：ai_environment.py --check 或 ai_environment.py <部署命令…>', file=sys.stderr)
        return 2
    try:
        env, sources = load_environment(os.environ)
        if argv == ['--check']:
            for name in AI_KEYS:
                status = '已配置 · ' + sources[name] if name in sources else '未配置（可选）'
                print(f'[AI 配置] {name}：{status}', flush=True)
            return 0
        os.execvpe(argv[0], argv, env)
    except (RuntimeError, OSError) as exc:
        # Never print the file contents, parsed values or subprocess environment.
        print(f'AI 部署环境加载失败：{exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
