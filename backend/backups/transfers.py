"""Manual backup orchestration; archive mechanics and scheduling remain external."""
from dataclasses import dataclass
from typing import Any, Callable, Protocol


class TaskLock(Protocol):
    def acquire(self, blocking: bool = True) -> bool: ...

    def release(self) -> None: ...


class BackupTaskBusy(Exception):
    """The existing process-local backup lock is already held."""


@dataclass(frozen=True)
class BackupTransfers:
    job_lock: TaskLock
    read_config: Callable[[], dict]
    write_config: Callable[[dict], Any]
    create_archive: Callable[..., dict]
    restore_archive: Callable[[Any], dict]

    def _acquire(self):
        if not self.job_lock.acquire(blocking=False):
            raise BackupTaskBusy('已有备份或恢复任务正在执行，请稍后再试。')

    def export(self):
        self._acquire()
        try:
            config = self.read_config()
            result = self.create_archive(config.get('destination_path'), reason='manual')
            cos_result = result.get('cos') or {}
            cos_status = cos_result.get('status') or 'not_configured'
            config.update({
                'last_backup_path': result['path'],
                'last_backup_size': result['size'],
                'last_cos_status': cos_status,
                'last_cos_key': cos_result.get('key'),
                'last_cos_uploaded_at': cos_result.get('uploaded_at'),
                'last_cos_retained_count': cos_result.get('retained_count') or 0,
                'last_cos_error': cos_result.get('message') if cos_status == 'error' else '',
                'last_status': 'warning' if cos_status == 'error' else 'success',
                'last_error': cos_result.get('message') if cos_status == 'error' else '',
            })
            self.write_config(config)
        finally:
            self.job_lock.release()
        return result

    def restore(self, uploaded_file: Callable[[], Any]):
        self._acquire()
        try:
            # Do not parse the upload until authorization has completed and the lock is held.
            manifest = self.restore_archive(uploaded_file())
        finally:
            self.job_lock.release()

        # Preserve the original boundary: restore releases the lock before updating config.
        config = self.read_config()
        config.update({'last_status': 'success', 'last_error': ''})
        self.write_config(config)
        return manifest
