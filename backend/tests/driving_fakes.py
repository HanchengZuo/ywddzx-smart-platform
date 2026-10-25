"""Synthetic road responses for isolated scheduling tests; never access AMap."""
from datetime import datetime, timezone
from schedule_common import ScheduleConflict
from schedule_driving_routes import driving_groups, request_key


def fake_distance(_key, origins, destination, _timeout):
    def point(value):
        return [float(n) for n in value.split(',')]
    target = point(destination)
    results = []
    for index, source in enumerate(origins):
        value = point(source)
        length = round(sum(abs(a - b) for a, b in zip(value, target)) * 100000)
        results.append(dict(origin_id=str(index + 1), dest_id='1', distance=str(length), duration=str(length // 10)))
    return dict(status='1', results=results)


class MemoryDrivingService:
    """Keep unrelated scheduling tests independent of collection fixtures."""
    def __init__(self):
        self.previews = {}

    def prepare(self, request):
        points = {s['station_id']: s['point'] for s in request['stations']}
        class Matrix:
            from driving_errors import DrivingUnavailable as unavailable
            def incoming(self, destination, origins):
                pass
            def edge(self, a, b):
                length = round(sum(abs(x-y) for x,y in zip(points[a], points[b])) * 100000)
                return dict(seconds=length//10, meters=length)
        return dict(request_key=request_key(request), trips=driving_groups(request, Matrix()),
                    calculated_at=datetime.now(timezone.utc).isoformat(), source='database', dataset_id=1,
                    cache_reused=True, api_requests=0, provider='amap')

    def remember(self, token, actor, day, result):
        self.previews[(token,actor,day)] = result

    def recall(self, token, actor, day):
        try:
            return self.previews[(token,actor,day)]
        except KeyError:
            raise ScheduleConflict('请重新预览。') from None


def fake_driving_service():
    return MemoryDrivingService()
