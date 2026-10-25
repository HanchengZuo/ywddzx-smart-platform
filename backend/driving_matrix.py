"""Database-only planning adapter. This module never imports an HTTP client."""
from datetime import datetime, timedelta
import hashlib
import json
import re
from zoneinfo import ZoneInfo
from psycopg2.extras import Json

from driving_errors import DrivingUnavailable
from schedule_common import ScheduleConflict
from schedule_driving_routes import driving_groups, request_key
from schedule_routes import coordinate

ZONE = ZoneInfo('Asia/Shanghai')
VIEW_PERMISSION = 'view_driving_matrix'
POLICY = 'amap-driving-single-direction-v1'
LOCK_ID = 11110001


def point(value):
    coords = coordinate(value)
    return ','.join(f'{v:.6f}' for v in coords) if coords else None


def next_refresh(now):
    local = now.astimezone(ZONE)
    monday = (local + timedelta(days=-local.weekday())).replace(hour=9, minute=30, second=0, microsecond=0)
    return monday if monday > local else monday + timedelta(days=7)


def latest_slot(now):
    return (next_refresh(now) - timedelta(days=7)).isoformat()


def station_snapshot(cur):
    cur.execute('SELECT id,station_name,region,longitude,latitude FROM stations ORDER BY id')
    valid, invalid = [], []
    for row in cur.fetchall():
        item = dict(station_id=row['id'], station_name=row['station_name'], region=row['region'] or '')
        if point(row):
            valid.append(dict(item, point=point(row)))
        else:
            invalid.append(item)
    return valid, invalid


def snapshot_hash(stations):
    return hashlib.sha256(json.dumps([(s['station_id'], s['point']) for s in stations], separators=(',', ':')).encode()).hexdigest()


class DatabaseMatrix:
    unavailable = DrivingUnavailable

    def __init__(self, points, values):
        self.points, self.values = points, values

    def edge(self, origin, destination):
        if origin == destination:
            return dict(seconds=0, meters=0)
        return self.values.get(tuple(sorted((origin, destination))))

    def incoming(self, destination, origins):
        if any(origin != destination and tuple(sorted((origin, destination))) not in self.values for origin in origins):
            raise DrivingUnavailable('站间路网数据尚未采集完整，请在路网数据管理查看采集状态；不会实时调用高德。')


class DrivingService:
    def __init__(self, connect):
        self.connect = connect

    def prepare(self, request):
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute('''SELECT r.* FROM driving_matrix_state s JOIN driving_matrix_runs r
                    ON r.id=s.active_run_id WHERE s.id=1 AND r.status='published' ''')
                run = cur.fetchone()
                points = {s['station_id']: ','.join(f'{v:.6f}' for v in s['point']) for s in request['stations']}
                # Video-only previews need no road data, including initialization.
                if not request['capacities'] or not points:
                    return dict(request_key=request_key(request), trips=[], dataset_id=run['id'] if run else None,
                                calculated_at=run['finished_at'].isoformat() if run else None, api_requests=0,
                                cache_reused=True, source='database', provider='amap')
                if not run:
                    raise DrivingUnavailable('路网数据库正在初始化，完成后即可使用现场智能排班；请查看路网数据管理。')
                saved = {s['station_id']: s['point'] for s in run['stations']}
                if any(saved.get(sid) != coords for sid, coords in points.items()):
                    raise DrivingUnavailable('部分站点新增或坐标已调整，尚未纳入最新路网批次，请等待定时更新；不会实时查询高德。')
                ids = list(points)
                cur.execute('''SELECT origin_id,destination_id,seconds,meters,reachable FROM driving_matrix_pairs
                    WHERE run_id=%s AND origin_id=ANY(%s) AND destination_id=ANY(%s)''', (run['id'], ids, ids))
                values = {(r['origin_id'], r['destination_id']):
                          dict(seconds=r['seconds'], meters=r['meters']) if r['reachable'] else None for r in cur.fetchall()}
        finally:
            conn.close()
        trips = driving_groups(request, DatabaseMatrix(points, values))
        return dict(request_key=request_key(request), trips=trips, dataset_id=run['id'], source='database',
                    provider='amap', calculated_at=run['finished_at'].isoformat(), api_requests=0, cache_reused=True)

    def remember(self, token, actor, day, result):
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute('DELETE FROM driving_matrix_previews WHERE expires_at<=CURRENT_TIMESTAMP')
                cur.execute('''INSERT INTO driving_matrix_previews(token,actor_id,day,payload,expires_at)
                    VALUES(%s,%s,%s,%s,CURRENT_TIMESTAMP+INTERVAL '30 minutes')
                    ON CONFLICT(token) DO UPDATE SET payload=EXCLUDED.payload,expires_at=EXCLUDED.expires_at''',
                    (token, actor, day, Json(result)))
            conn.commit()
        finally:
            conn.close()

    def recall(self, token, actor, day):
        if not isinstance(token, str) or not re.fullmatch('[a-f0-9]{64}', token):
            raise ScheduleConflict('智能方案不存在或已过期，请重新预览。')
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute('''SELECT payload FROM driving_matrix_previews WHERE token=%s AND actor_id=%s
                    AND day=%s AND expires_at>CURRENT_TIMESTAMP''', (token, actor, day))
                row = cur.fetchone()
                if not row:
                    raise ScheduleConflict('智能方案已过期，请重新计算后再应用。')
                return row['payload']
        finally:
            conn.close()
