"""Manual backup orchestration; archive mechanics and scheduling remain external."""
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from .cos import backup_result_metadata


class TaskLock(Protocol):
    def acquire(self, blocking: bool = True) -> bool: ...

    def release(self) -> None: ...


class BackupTaskBusy(Exception):
    """Another backup or restore owns the shared storage lock."""


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
            config.update({
                'last_backup_path': result['path'],
                'last_backup_size': result['size'],
                **backup_result_metadata(result.get('cos') or {}),
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
            config = self.read_config()
            config.update({'last_status': 'success', 'last_error': ''})
            self.write_config(config)
            return manifest
        finally:
            self.job_lock.release()
