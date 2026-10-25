"""Install a host timer: one collector, independent of traffic/Gunicorn workers."""
from pathlib import Path
import subprocess


def units(root):
    # WorkingDirectory is a path-valued setting, not a shell command line.
    path = str(Path(root).resolve()).replace('%', '%%')
    service = f'''[Unit]
Description=YWDDZX weekly station driving matrix
After=docker.service network-online.target
Wants=network-online.target
StartLimitIntervalSec=1h
StartLimitBurst=3

[Service]
Type=oneshot
WorkingDirectory={path}
ExecStart=/usr/bin/docker exec -w /app ywddzx-backend python /app/driving_matrix_cli.py
TimeoutStartSec=2h
Nice=10
Restart=on-failure
RestartSec=10min
'''
    timer = '''[Unit]
Description=YWDDZX driving matrix every Monday 09:30 Shanghai

[Timer]
OnCalendar=Mon *-*-* 09:30:00 Asia/Shanghai
Persistent=true
AccuracySec=1min
Unit=ywddzx-driving-refresh.service

[Install]
WantedBy=timers.target
'''
    return service, timer


def install(root, destination=Path('/etc/systemd/system'), run=subprocess.run):
    service, timer = units(root)
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in [('service', service), ('timer', timer)]:
        target = destination / f'ywddzx-driving-refresh.{name}'
        target.write_text(content, encoding='utf-8')
        target.chmod(0o644)
    run(['systemctl', 'daemon-reload'], check=True)
    run(['systemctl', 'enable', '--now', 'ywddzx-driving-refresh.timer'], check=True)
    # The CLI skips current successful batches and resumes an interrupted one.
    run(['systemctl', 'start', '--no-block', 'ywddzx-driving-refresh.service'], check=True)


if __name__ == '__main__':
    install(Path(__file__).resolve().parents[1])
    print('路网采集任务已安装：北京时间每周一09:30，初始化/补漏任务已后台提交。')
