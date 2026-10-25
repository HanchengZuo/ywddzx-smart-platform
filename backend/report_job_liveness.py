"""Process-safe ownership for report threads on this platform's shared storage.

Keep lock files: unlinking a live inode could allow two owners. The OS releases
flock on worker exit, so deployment interruptions can be recognized without a
timer, another scheduler, an AI retry, or a database connection held during AI.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import os


@contextmanager
def report_job_lease(root, task_id):
    os.makedirs(root, mode=0o700, exist_ok=True)
    path = os.path.join(root, hashlib.sha256(str(task_id).encode()).hexdigest() + '.lock')
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    owned = False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            owned = True
        except BlockingIOError:
            pass
        yield owned
    finally:
        if owned:
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def claim_report_job(cur, task_id):
    # Atomic claim also serializes with a concurrent interruption reconciliation.
    cur.execute("""UPDATE inspection_report_jobs
        SET status = 'running', started_at = COALESCE(started_at, CURRENT_TIMESTAMP),
            updated_at = CURRENT_TIMESTAMP
        WHERE task_id = %s AND status = 'queued' RETURNING *;""", (task_id,))
    return cur.fetchone()


def expire_unowned_report_jobs(cur, root, report_type=None, task_id=None):
    cur.execute("""SELECT task_id FROM inspection_report_jobs
        WHERE status IN ('queued', 'running')
          AND updated_at < CURRENT_TIMESTAMP - INTERVAL '3 minutes'
          AND (%s::text IS NULL OR report_type = %s)
          AND (%s::text IS NULL OR task_id = %s);""",
        (report_type, report_type, task_id, task_id))
    expired = 0
    for row in cur.fetchall():
        with report_job_lease(root, row['task_id']) as owned:
            if not owned:
                continue
            cur.execute("""UPDATE inspection_report_jobs
                SET status = 'failed', stage_message = '报告生成已中断',
                    error_message = '生成进程已退出，可能因服务重启或部署中断。最后成功成稿与已有AI缓存均已保留；请确认后手动重新生成。',
                    finished_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE task_id = %s AND status IN ('queued', 'running')
                  AND updated_at < CURRENT_TIMESTAMP - INTERVAL '3 minutes'
                RETURNING task_id;""", (row['task_id'],))
            expired += bool(cur.fetchone())
    return expired
