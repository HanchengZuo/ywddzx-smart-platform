"""Synthetic road responses for isolated scheduling tests; never access AMap."""
from amap_driving import DrivingService


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


def fake_driving_service(root):
    return DrivingService(root, key='test-web-service-key', fetch=fake_distance, interval=0)
