"""Serialize backup, restore and configuration writes on the shared storage volume."""
import fcntl
import os
import threading


class BackupJobLock:
    def __init__(self, storage_root):
        self.storage_root = storage_root
        self.local = threading.local()

    def acquire(self, blocking=True):
        root = self.storage_root()
        os.makedirs(root, exist_ok=True)
        # The restore clears children of this directory, never the directory inode.
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError:
            os.close(fd)
            return False
        except BaseException:
            os.close(fd)
            raise
        self.local.fd = fd
        return True

    def inherited_fds(self):
        fd = getattr(self.local, "fd", None)
        return (fd,) if fd is not None else ()

    def release(self):
        fd = self.local.fd
        del self.local.fd
        # A running upload subprocess can still own this open file description.
        os.close(fd)
