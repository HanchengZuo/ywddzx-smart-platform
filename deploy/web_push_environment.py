"""Inject persistent VAPID settings into backend deployment only, without executing files."""
import os
from pathlib import Path
import re
import shlex
import sys

KEYS=('WEB_PUSH_ENABLED','WEB_PUSH_VAPID_PRIVATE_KEY','WEB_PUSH_SUBJECT')


def load_environment(environ):
    env=dict(environ)
    explicit=env.get('WEB_PUSH_ENV_FILE','').strip()
    path=Path(explicit or '/etc/ywddzx/web-push.env')
    # A complete explicit identity is authoritative; do not rotate or replace it.
    if env.get(KEYS[1],'').strip() and env.get(KEYS[2],'').strip():
        source='部署环境 / 项目 .env'
    else:
        try:
            if path.stat().st_mode & 0o077:
                raise RuntimeError('Web Push 配置文件应为0600权限。')
            content=path.read_text(encoding='utf-8')
        except FileNotFoundError:
            if explicit: raise RuntimeError('指定的 Web Push 配置文件不存在。') from None
            content=''
        except (OSError,UnicodeError):
            raise RuntimeError('Web Push 配置文件无法读取。') from None
        found={}
        for line in content.splitlines():
            match=re.match(r'^\s*(?:export\s+)?(WEB_PUSH_ENABLED|WEB_PUSH_VAPID_PRIVATE_KEY|WEB_PUSH_SUBJECT)\s*=\s*(.*)$',line)
            if not match: continue
            try: values=shlex.split(match[2],comments=True)
            except ValueError: raise RuntimeError('Web Push 配置文件格式无效。') from None
            if len(values)!=1 or any(c in values[0] for c in '$`;|&<>\x00\r\n'):
                raise RuntimeError('Web Push 配置文件只能使用固定的单行值。')
            found[match[1]]=values[0]
        for key in KEYS:
            if not env.get(key,'').strip() and key in found: env[key]=found[key]
        source=str(path) if found else None
    enabled=env.get(KEYS[0],'true').strip().lower()
    if enabled not in ('true','false','1','0','yes','no'):
        raise RuntimeError('WEB_PUSH_ENABLED 必须是明确的启用或停用值。')
    if enabled not in ('false','0','no') and bool(env.get(KEYS[1],'')) != bool(env.get(KEYS[2],'')):
        raise RuntimeError('Web Push 身份配置不完整，私钥及subject须一并配置。')
    return env,source


def main(argv):
    try:
        env,source=load_environment(os.environ)
        if argv==['--check']:
            enabled=env.get(KEYS[0],'true').lower() not in ('false','0','no')
            present=bool(env.get(KEYS[1]) and env.get(KEYS[2]))
            print('[Web Push配置] '+('已停用' if not enabled else '身份已配置 · '+str(source) if present
                else '尚未配置VAPID；站内通知可用，浏览器推送不能开通。'))
            return 0
        if not argv: return 2
        os.execvpe(argv[0],argv,env)
    except (RuntimeError,OSError) as exc:
        print('Web Push 部署配置读取失败：'+str(exc),file=sys.stderr)
        return 1


if __name__=='__main__': raise SystemExit(main(sys.argv[1:]))
