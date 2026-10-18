"""Content-addressed, permission-sanitized Excel artifacts shared by export tasks."""
import hashlib
import json
import os


BASE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS issue_export_tasks (
    task_id TEXT PRIMARY KEY,
    created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending',
    selected_count INTEGER NOT NULL DEFAULT 0,
    exported_count INTEGER NOT NULL DEFAULT 0,
    filter_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    export_options JSONB NOT NULL DEFAULT '{}'::jsonb,
    file_path TEXT, download_filename TEXT, error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP, expires_at TIMESTAMP NOT NULL
);
"""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS issue_export_artifacts (
    cache_key TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    exported_count INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_issue_export_artifacts_expiry ON issue_export_artifacts(expires_at);
ALTER TABLE issue_export_tasks ADD COLUMN IF NOT EXISTS cache_key TEXT;
ALTER TABLE issue_export_tasks ADD COLUMN IF NOT EXISTS issue_ids JSONB;
ALTER TABLE issue_export_tasks ADD COLUMN IF NOT EXISTS cache_reused BOOLEAN NOT NULL DEFAULT FALSE;
"""


def ensure_schema(cur):
    cur.execute(SCHEMA_SQL)


def fingerprint(rows, options, table_fields, resolve_photo):
    # Hash the actual sanitized row snapshot, never a user-supplied filter or just IDs.
    digest = hashlib.sha256()
    def add(value):
        digest.update(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str,
                                 separators=(',', ':')).encode('utf-8'))
        digest.update(b'\n')
    add({'renderer': 'issues-xlsx-v9.4', 'options': options,
         'tables': {str(key): value for key, value in table_fields.items()}})
    photo_keys = [key for key, enabled in options.get('include_photos', {}).items() if enabled]
    for row in sorted(rows, key=lambda item: int(item['id']), reverse=True):
        add(dict(row))
        for key in sorted(photo_keys):
            path = resolve_photo(row.get(key)) if row.get(key) else None
            try:
                stat = os.stat(path) if path else None
            except OSError:
                stat = None
            add([key, [stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns] if stat else None])
    return digest.hexdigest()


def find_artifact(cur, cache_key, resolve_path):
    cur.execute('''SELECT cache_key,file_path,exported_count,expires_at
        FROM issue_export_artifacts WHERE cache_key=%s AND expires_at>CURRENT_TIMESTAMP''', (cache_key,))
    row = cur.fetchone()
    if row and row.get('file_path'):
        path = resolve_path(row['file_path'])
        if path and os.path.isfile(path) and os.path.getsize(path) > 0:
            return row
    return None


def lock_artifact(cur, cache_key):
    # PostgreSQL, not threading.Lock: serialize identical renders across Gunicorn workers.
    cur.execute('SELECT pg_advisory_xact_lock_shared(940, 1)')
    lock_key = int.from_bytes(bytes.fromhex(cache_key[:16]), 'big', signed=True)
    cur.execute('SELECT pg_advisory_xact_lock(%s)', (lock_key,))


def store_artifact(cur, cache_key, file_path, count):
    cur.execute('''INSERT INTO issue_export_artifacts(cache_key,file_path,exported_count,expires_at)
        VALUES(%s,%s,%s,CURRENT_TIMESTAMP+INTERVAL '7 days')
        ON CONFLICT(cache_key) DO UPDATE SET file_path=EXCLUDED.file_path,
          exported_count=EXCLUDED.exported_count,created_at=CURRENT_TIMESTAMP,expires_at=EXCLUDED.expires_at
        RETURNING cache_key,file_path,exported_count,expires_at''', (cache_key,file_path,count))
    return cur.fetchone()
