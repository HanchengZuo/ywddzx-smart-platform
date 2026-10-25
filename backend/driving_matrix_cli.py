"""Run by the host timer, not by a web worker. Does not import app.py."""
import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from driving_matrix_refresh import run_refresh


def connect():
    return psycopg2.connect(host=os.environ.get('DB_HOST', 'db'), port=os.environ.get('DB_PORT', '5432'),
        dbname=os.environ.get('DB_NAME', 'ywddzx'), user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', 'postgres'), cursor_factory=RealDictCursor,
        options='-c timezone=Asia/Shanghai')


def main():
    try:
        result = run_refresh(connect)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception:
        print('路网采集未完成；已保留旧批次与采集中进度，详情见路网数据管理。')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
