"""One-off root operation; dry-run by default. Preserve area and station ownership."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psycopg2
from psycopg2.extras import RealDictCursor
from user_permission_config import clear_personal_permissions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--snapshot', help='New absolute private JSON path required before applying')
    args = parser.parse_args()
    if args.apply and (not args.snapshot or not Path(args.snapshot).is_absolute()):
        parser.error('--apply requires --snapshot with a new absolute path')
    conn = psycopg2.connect(host=os.environ.get('DB_HOST', 'db'), port=os.environ.get('DB_PORT', '5432'),
                            dbname=os.environ.get('DB_NAME', 'ywddzx'), user=os.environ.get('DB_USER', 'postgres'),
                            password=os.environ.get('DB_PASSWORD', ''), cursor_factory=RealDictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL lock_timeout = '5s'")
            cur.execute("SET LOCAL statement_timeout = '60s'")
            cur.execute("SELECT id, username, role FROM users WHERE username='root' AND role='root'")
            actor = cur.fetchone()
            summary = clear_personal_permissions(cur, actor)
            if args.apply:
                snapshot = {}
                for table in ('user_permissions', 'user_inspection_table_scopes', 'user_station_region_scopes'):
                    cur.execute(f'SELECT * FROM {table} ORDER BY user_id')
                    snapshot[table] = [dict(row) for row in cur.fetchall()]
                fd = os.open(args.snapshot, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                    json.dump(snapshot, stream, ensure_ascii=False, default=str)
                    stream.flush()
                    os.fsync(stream.fileno())
                summary = clear_personal_permissions(cur, actor, apply=True)
        conn.commit() if args.apply else conn.rollback()
        print(json.dumps({'applied': args.apply, **summary}, ensure_ascii=False))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
