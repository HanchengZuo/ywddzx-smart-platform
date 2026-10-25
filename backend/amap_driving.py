"""Private, bounded AMap driving matrix/cache; no imports start jobs or HTTP calls."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import time
from urllib.parse import urlencode
from urllib.request import urlopen

from schedule_common import ScheduleConflict
from schedule_driving_routes import driving_groups, request_key

AMAP_DISTANCE_URL = 'https://restapi.amap.com/v3/distance'
CACHE_SECONDS = 7200
PLAN_SECONDS = 1800


class DrivingUnavailable(Exception):
    pass


def fetch_distance(key, origins, destination, timeout):
    parameters = dict(key=key, origins='|'.join(origins), destination=destination, type='1', output='JSON')
    try:
        with urlopen(AMAP_DISTANCE_URL + '?' + urlencode(parameters), timeout=timeout) as response:
            if response.status != 200:
                raise ValueError()
            return json.loads(response.read(2_000_001))
    except Exception:
        # urllib's exception text contains the URL/key: never propagate it.
        raise DrivingUnavailable('高德驾车服务暂时无法连接，请稍后重新计算；未改动现有排班。') from None


def parse_results(data, count):
    if not isinstance(data, dict) or data.get('status') != '1':
        code = str(data.get('infocode', '')) if isinstance(data, dict) else ''
        if code in ('10001', '10009', '10010', '10012', '10013'):
            raise DrivingUnavailable('高德驾车服务Key未授权或平台类型不匹配，请管理员配置Web服务类型的AMAP_WEB_SERVICE_KEY。')
        if code in ('10003', '10004', '10019', '10020', '10021', '10044'):
            raise DrivingUnavailable('高德驾车服务额度或频率受限，请稍后重新计算；不会退回直线距离派工。')
        raise DrivingUnavailable('高德驾车服务返回异常，请稍后重新计算；未改动现有排班。')
    values = data.get('results')
    if not isinstance(values, list) or len(values) != count:
        raise DrivingUnavailable('高德驾车数据不完整，请稍后重新计算。')
    result = {}
    for value in values:
        try:
            if not isinstance(value, dict) or isinstance(value.get('origin_id'), bool):
                raise ValueError()
            index = int(value['origin_id']) - 1
            if index in result or not 0 <= index < count or str(value.get('dest_id')) != '1':
                raise ValueError()
            if str(value.get('code', '0')) in ('1', '2', '3'):
                result[index] = None
                continue
            if value.get('info') or str(value.get('code', '0')) != '0':
                raise ValueError()
            seconds, meters = float(value['duration']), float(value['distance'])
            if not all(math.isfinite(n) and n >= 0 for n in (seconds, meters)):
                raise ValueError()
            result[index] = dict(seconds=round(seconds), meters=round(meters))
        except (ValueError, KeyError, TypeError, OverflowError):
            raise DrivingUnavailable('高德驾车数据格式异常，请稍后重新计算。') from None
    return result


class DrivingService:
    def __init__(self, root, *, key=None, fetch=fetch_distance, clock=time.time, monotonic=time.monotonic,
                 sleep=time.sleep, budget=65, interval=0.6):
        self.root = Path(root)
        self.key = key
        self.fetch = fetch
        self.clock = clock
        self.monotonic = monotonic
        self.sleep = sleep
        self.budget = budget
        self.interval = interval

    @contextmanager
    def database(self):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = self.root / 'routes.sqlite3'
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        os.close(fd)
        connection = sqlite3.connect(path, timeout=3)
        try:
            connection.executescript('''CREATE TABLE IF NOT EXISTS routes(
                origin TEXT, destination TEXT, result TEXT, expires REAL,
                PRIMARY KEY(origin,destination));
                CREATE TABLE IF NOT EXISTS plans(
                token TEXT PRIMARY KEY, actor INTEGER, day TEXT, value TEXT, expires REAL);
                CREATE TABLE IF NOT EXISTS computations(
                id TEXT PRIMARY KEY, value TEXT, expires REAL);''')
            yield connection
            connection.commit()
        finally:
            connection.close()

    def prepare(self, request):
        digest = request_key(request)
        with self.database() as db:
            row = db.execute('SELECT value FROM computations WHERE id=? AND expires>?', (digest, self.clock())).fetchone()
        if row:
            result = json.loads(row[0])
            result['cache_reused'] = True
            result['api_requests'] = 0
            return result
        lock_path = self.root / 'prepare.lock'
        with os.fdopen(os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600), 'r+') as lock:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise DrivingUnavailable('另一份智能方案正在核算驾车时间，请稍后重新计算；现有排班不受影响。') from None
            # The lock spans only the route cache, never a scheduling transaction.
            matrix = DrivingMatrix(self, request['stations'])
            trips = driving_groups(request, matrix)
            expiry = min(matrix.expiries, default=self.clock() + CACHE_SECONDS)
            result = dict(request_key=digest, trips=trips, provider='amap',
                          calculated_at=datetime.fromtimestamp(self.clock(), timezone.utc).isoformat(),
                          expires_at=expiry, api_requests=matrix.api_requests, cache_reused=matrix.api_requests == 0)
            with self.database() as db:
                db.execute('DELETE FROM plans WHERE expires<=?', (self.clock(),))
                db.execute('DELETE FROM computations WHERE expires<=?', (self.clock(),))
                db.execute('DELETE FROM routes WHERE expires<=?', (self.clock(),))
                db.execute('INSERT OR REPLACE INTO computations VALUES(?,?,?)', (digest, json.dumps(result), expiry))
            return result

    def remember(self, token, actor, day, result):
        with self.database() as db:
            db.execute('INSERT OR REPLACE INTO plans VALUES(?,?,?,?,?)',
                       (token, actor, day.isoformat(), json.dumps(result), self.clock() + PLAN_SECONDS))

    def recall(self, token, actor, day):
        if not isinstance(token, str) or not re.fullmatch('[a-f0-9]{64}', token):
            raise ScheduleConflict('智能方案不存在或已过期，请重新预览。')
        with self.database() as db:
            row = db.execute('SELECT value FROM plans WHERE token=? AND actor=? AND day=? AND expires>?',
                             (token, actor, day.isoformat(), self.clock())).fetchone()
        if not row:
            raise ScheduleConflict('驾车方案已过期，请重新计算智能方案后再应用。')
        return json.loads(row[0])


class DrivingMatrix:
    unavailable = DrivingUnavailable

    def __init__(self, service, stations):
        self.service = service
        self.points = {s['station_id']: ','.join(f'{n:.6f}' for n in s['point']) for s in stations}
        self.values = {}
        self.expiries = []
        self.api_requests = 0
        self.started = service.monotonic()
        self.next_request = self.started

    def edge(self, origin, destination):
        if origin == destination or self.points[origin] == self.points[destination]:
            return dict(seconds=0, meters=0)
        return self.values.get((origin, destination))

    def incoming(self, destination, origins):
        origins = sorted(set(origins) - {destination})
        pending = [sid for sid in origins if (sid, destination) not in self.values and self.points[sid] != self.points[destination]]
        if not pending:
            return
        now = self.service.clock()
        with self.service.database() as db:
            for sid in pending:
                row = db.execute('SELECT result,expires FROM routes WHERE origin=? AND destination=? AND expires>?',
                                 (self.points[sid], self.points[destination], now)).fetchone()
                if row:
                    self.values[(sid, destination)] = json.loads(row[0])
                    self.expiries.append(row[1])
        pending = [sid for sid in pending if (sid, destination) not in self.values]
        if not pending:
            return
        key = self.service.key if self.service.key is not None else (
            os.environ.get('AMAP_WEB_SERVICE_KEY', '').strip() or os.environ.get('AMAP_KEY', '').strip())
        if not key:
            raise DrivingUnavailable('尚未配置高德驾车服务，请管理员设置Web服务类型的AMAP_WEB_SERVICE_KEY；地图浏览器Key不能替代。')
        for offset in range(0, len(pending), 100):
            elapsed = self.service.monotonic() - self.started
            if elapsed >= self.service.budget - 7:
                raise DrivingUnavailable('首次驾车数据查询较多，已缓存已完成的结果；请再次计算继续，现有排班未改变。')
            self.service.sleep(max(0, self.next_request - self.service.monotonic()))
            batch = pending[offset:offset + 100]
            data = self.service.fetch(key, [self.points[sid] for sid in batch], self.points[destination], 6)
            self.api_requests += 1
            self.next_request = self.service.monotonic() + self.service.interval
            values = parse_results(data, len(batch))
            with self.service.database() as db:
                for index, sid in enumerate(batch):
                    edge = values[index]
                    expiry = self.service.clock() + (CACHE_SECONDS if edge is not None else 600)
                    self.values[(sid, destination)] = edge
                    self.expiries.append(expiry)
                    db.execute('INSERT OR REPLACE INTO routes VALUES(?,?,?,?)',
                               (self.points[sid], self.points[destination], json.dumps(edge), expiry))
