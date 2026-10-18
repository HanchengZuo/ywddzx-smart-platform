"""Short-lived, task-bound credentials for native browser downloads, not API access."""
from itsdangerous import BadSignature, URLSafeTimedSerializer

COOKIE_NAME = 'issue_export_download'
GRANT_SECONDS = 1800


def cookie_path(task_id):
    return f'/api/issues/export-tasks/{task_id}/download'


def mint(secret, identity, task_id, now):
    identity = dict(identity)
    identity['exp'] = min(int(identity.get('exp') or 0), now + GRANT_SECONDS)
    if not identity.get('uid') or identity['exp'] <= now:
        raise PermissionError('登录已过期，请重新登录。')
    return URLSafeTimedSerializer(secret, salt='issue-export-download-v1').dumps(
        {'task': task_id, 'identity': identity})


def unwrap(secret, token, task_id, now):
    try:
        grant = URLSafeTimedSerializer(secret, salt='issue-export-download-v1').loads(token, max_age=GRANT_SECONDS)
        identity = grant['identity']
        if grant['task'] != task_id or int(identity['exp']) <= now or not identity.get('uid'):
            raise ValueError('Invalid download scope')
        return identity
    except (BadSignature, KeyError, TypeError, ValueError) as exc:
        raise PermissionError('下载授权已过期，请重新点击下载。') from exc
