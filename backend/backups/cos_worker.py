"""Run COS work in a disposable process so a stalled SDK thread can be stopped."""
from datetime import datetime
import json
import os
import signal
import subprocess
import sys
from zoneinfo import ZoneInfo

from . import cos


def run_bounded_upload(path, filename, *, prefix, backup_prefix, retention, pass_fds=(), timeout=5400):
    command = [sys.executable, "-m", "backups.cos_worker", path, filename, prefix,
               backup_prefix, str(retention), str(timeout)]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, text=True,
                                timeout=timeout + 5, pass_fds=pass_fds)
        if result.returncode == -signal.SIGALRM:
            raise subprocess.TimeoutExpired(command, timeout)
        result.check_returncode()
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        limit = f"{timeout // 60} 分钟" if timeout % 60 == 0 else f"{timeout} 秒"
        return {"status": "error", "message": f"COS 上传超过 {limit}，已停止；本地备份已保留。"}
    except (OSError, subprocess.CalledProcessError, ValueError):
        return {"status": "error", "message": "COS 上传进程异常退出；本地备份已保留。"}


def main(path, filename, prefix, backup_prefix, retention, timeout):
    # This also bounds the child if its Gunicorn parent is killed first.
    signal.signal(signal.SIGALRM, signal.SIG_DFL)
    signal.alarm(int(timeout))
    from qcloud_cos import CosConfig, CosS3Client

    timezone = ZoneInfo("Asia/Shanghai")
    retention = int(retention)
    config = cos.get_cos_env_config(environ=os.environ, prefix=prefix, retention_count=retention,
                                   sdk_available=True)

    def client():
        return cos.get_cos_client(config, config_factory=CosConfig, client_factory=CosS3Client)

    def objects():
        return cos.list_cos_backup_objects(
            get_client=client, backup_prefix=backup_prefix,
            parse_last_modified=lambda value: cos.parse_cos_last_modified(value, timezone=timezone))

    print(json.dumps(cos.upload_backup_archive_to_cos(
        path, filename, get_environment=lambda: config, get_client=client, list_objects=objects,
        prune_objects=lambda rows: cos.prune_cos_backup_objects(
            rows, get_client=client, list_objects=objects, retention_count=retention),
        clock=lambda: datetime.now(timezone)), ensure_ascii=False))


if __name__ == "__main__":
    main(*sys.argv[1:])
