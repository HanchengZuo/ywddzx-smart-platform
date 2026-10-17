"""Run after the compatible backend is deployed. Dry-run unless --apply is set."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psycopg2
from psycopg2.extras import RealDictCursor
from role_permission_transition import promote_supervisor_managers

TARGETS = {35335: 'yqy', 35677: 'bxq', 36023: 'hanxu', 36369: 'kdc',
           36717: 'lzk', 37067: 'yhs', 51021: 'hfh'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Commit the seven validated role changes and audit events')
    args = parser.parse_args()
    conn = psycopg2.connect(host=os.environ.get('DB_HOST', 'db'), port=os.environ.get('DB_PORT', '5432'),
                            dbname=os.environ.get('DB_NAME', 'ywddzx'), user=os.environ.get('DB_USER', 'postgres'),
                            password=os.environ.get('DB_PASSWORD', ''), cursor_factory=RealDictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL lock_timeout = '5s'")
            cur.execute("SELECT id, username, role FROM users WHERE username = 'root' AND role = 'root'")
            actor = cur.fetchone()
            rows = promote_supervisor_managers(cur, TARGETS, actor, apply=args.apply)
        if args.apply:
            conn.commit()
        else:
            conn.rollback()
        print(json.dumps({'applied': args.apply, 'accounts': rows, 'new_role': 'supervisor_manager'}, ensure_ascii=False))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
