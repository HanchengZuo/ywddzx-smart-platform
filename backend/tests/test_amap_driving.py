import fcntl
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
from datetime import date

from amap_driving import DrivingService, DrivingMatrix, DrivingUnavailable, fetch_distance, parse_results
from schedule_common import ScheduleConflict
from schedule_driving_routes import driving_groups, driving_request, request_key, shortest_order
from tests.driving_fakes import fake_distance


def station(sid, region='甲', longitude=None):
    return dict(station_id=sid, region=region, covered=False, longitude=longitude or 121.1 + sid * .01, latitude=31.2)


def request(stations=None, count=1, quota=2, required=(), coverage=None):
    return driving_request(stations or [station(1), station(2), station(3)], count, quota,
                           coverage or [], required, [quota] * count)


class Matrix:
    unavailable = DrivingUnavailable

    def __init__(self, values):
        self.values = values

    def incoming(self, destination, origins):
        pass

    def edge(self, origin, destination):
        if origin == destination:
            return dict(seconds=0, meters=0)
        value = self.values.get((origin, destination))
        return None if value is None else dict(seconds=value[0], meters=value[1])


class RouteTests(unittest.TestCase):
    def test_longer_driving_distance_but_shorter_time_wins_and_order_is_directed(self):
        # 1/2 are physically closest, but reaching 2 requires a long road detour.
        stations = [station(1), station(2, longitude=121.11001), station(3)]
        matrix = Matrix({(1, 2): (1800, 1000), (2, 1): (1900, 1100),
                         (1, 3): (600, 12000), (3, 1): (300, 13000),
                         (2, 3): (2500, 16000), (3, 2): (2600, 16000)})
        result = driving_groups(request(stations), matrix)
        self.assertEqual(result[0]['station_ids'], [3, 1])
        self.assertEqual((result[0]['seconds'], result[0]['meters']), (300, 13000))
        self.assertEqual(result[0]['legs'][0]['origin_id'], 3)

    def test_road_distance_only_breaks_equal_time_ties(self):
        matrix = Matrix({(a, b): (60, 100 if {a, b} == {1, 3} else 200)
                         for a in (1, 2, 3) for b in (1, 2, 3) if a != b})
        self.assertEqual(set(driving_groups(request(), matrix)[0]['station_ids']), {1, 3})

    def test_required_metering_and_coverage_counts_override_road_time_and_keep_capacity(self):
        stations = [station(1), station(2), station(3, '乙'), station(4, '乙')]
        matrix = Matrix({(a, b): (60 if a < 3 and b < 3 else 1800, 2000)
                         for a in range(1, 5) for b in range(1, 5) if a != b})
        plan = request(stations, required=(3,), coverage=[dict(region='甲', total=2, checked=2, reserved=0),
                                                        dict(region='乙', total=2, checked=0, reserved=0)])
        result = driving_groups(plan, matrix)
        self.assertEqual(set(result[0]['station_ids']), {3, 4})

    def test_open_path_uses_measured_one_way_edges_and_no_office_detour(self):
        matrix = Matrix({(2, 1): (10, 100), (1, 3): (10, 100), (2, 3): (100, 100)})
        self.assertEqual(shortest_order([1, 2, 3], matrix), [2, 1, 3])
        with self.assertRaises(DrivingUnavailable):
            shortest_order([1, 2, 3], Matrix({}))

    def test_155_candidates_are_unique_with_capacity_and_deterministic(self):
        values = {(a, b): (abs(a - b) * 20, abs(a - b) * 100)
                  for a in range(1, 156) for b in range(1, 156) if a != b}
        data = request([station(i, str(i % 7)) for i in range(1, 156)], count=7, quota=10)
        result = driving_groups(data, Matrix(values))
        self.assertEqual([len(trip['station_ids']) for trip in result], [10] * 7)
        self.assertEqual(len({sid for trip in result for sid in trip['station_ids']}), 70)
        self.assertEqual(result, driving_groups(data, Matrix(values)))


class AmapTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.clock = Mock(return_value=1000)
        self.fetch = Mock(side_effect=fake_distance)
        self.service = DrivingService(self.folder.name, key='private-test-key', fetch=self.fetch,
                                      clock=self.clock, interval=0)

    def test_batch_driving_mode_directional_cache_coordinate_change_and_expiry(self):
        data = request([station(i) for i in range(1, 104)])
        matrix = DrivingMatrix(self.service, data['stations'])
        matrix.incoming(1, list(range(1, 104)))
        self.assertEqual([len(call.args[1]) for call in self.fetch.call_args_list], [100, 2])
        self.assertIsNotNone(matrix.edge(2, 1))
        self.assertIsNone(matrix.edge(1, 2))
        duplicate = DrivingMatrix(self.service, data['stations'])
        duplicate.incoming(1, list(range(1, 104)))
        self.assertEqual(self.fetch.call_count, 2)
        changed = request([station(1), station(2, longitude=122.9)])
        DrivingMatrix(self.service, changed['stations']).incoming(1, [2])
        self.assertEqual(self.fetch.call_count, 3)
        self.clock.return_value = 8201
        DrivingMatrix(self.service, data['stations']).incoming(1, [2])
        self.assertEqual(self.fetch.call_count, 4)

    def test_http_uses_type_one_and_hides_urls_keys_and_vendor_error_messages(self):
        with patch('amap_driving.urlopen') as url:
            response = url.return_value.__enter__.return_value
            response.status = 200
            response.read.return_value = b'{"status":"1","results":[]}'
            fetch_distance('private-test-key', ['121.1,31.2'], '121.2,31.2', 6)
            self.assertIn('type=1', url.call_args.args[0])
            self.assertNotIn('type=0', url.call_args.args[0])
            url.side_effect = RuntimeError('https://secret-url?key=private-test-key')
            with self.assertRaises(DrivingUnavailable) as caught:
                fetch_distance('private-test-key', [], '', 6)
            self.assertNotIn('private-test-key', str(caught.exception))
        for code in ('10009', '10003', '99999'):
            with self.assertRaises(DrivingUnavailable) as caught:
                parse_results(dict(status='0', infocode=code, info='private-test-key'), 1)
            self.assertNotIn('private-test-key', str(caught.exception))

    def test_invalid_negative_nan_duplicate_rows_and_unreachable_are_not_zero_minutes(self):
        normal = dict(origin_id='1', dest_id='1', duration='20', distance='200')
        for change in (dict(duration='NaN'), dict(distance='-1'), dict(origin_id='2'), dict(dest_id='2'), dict(code='9')):
            with self.assertRaises(DrivingUnavailable):
                parse_results(dict(status='1', results=[dict(normal, **change)]), 1)
        with self.assertRaises(DrivingUnavailable):
            parse_results(dict(status='1', results=[normal, normal]), 2)
        self.assertEqual(parse_results(dict(status='1', results=[dict(origin_id='1', dest_id='1', code='1')]), 1), {0: None})

    def test_prepare_reuses_across_service_instances_and_confirm_pins_snapshot(self):
        prepared = self.service.prepare(request())
        token = 'a' * 64
        self.service.remember(token, 1, date(2026, 10, 25), prepared)
        self.fetch.reset_mock()
        other = DrivingService(self.folder.name, key='test', fetch=self.fetch, clock=self.clock, interval=0)
        reused = other.prepare(request())
        self.assertTrue(reused['cache_reused'])
        self.assertEqual(reused['api_requests'], 0)
        self.assertEqual(other.recall(token, 1, date(2026, 10, 25)), prepared)
        self.fetch.assert_not_called()
        for actor, day in [(2, date(2026, 10, 25)), (1, date(2026, 10, 26))]:
            with self.assertRaises(ScheduleConflict):
                other.recall(token, actor, day)
        self.clock.return_value += 1801
        with self.assertRaises(ScheduleConflict):
            other.recall(token, 1, date(2026, 10, 25))
        self.assertEqual((Path(self.folder.name) / 'routes.sqlite3').stat().st_mode & 0o777, 0o600)

    def test_busy_cache_lock_missing_key_and_budget_fail_without_geometry_fallback(self):
        self.service.root.mkdir(exist_ok=True)
        with (self.service.root / 'prepare.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with self.assertRaisesRegex(DrivingUnavailable, '另一份'):
                self.service.prepare(request())
        self.fetch.assert_not_called()
        no_key = DrivingService(self.folder.name, key='')
        with self.assertRaisesRegex(DrivingUnavailable, 'AMAP_WEB_SERVICE_KEY'):
            no_key.prepare(request())
        self.service.budget = 0
        with self.assertRaisesRegex(DrivingUnavailable, '再次计算'):
            self.service.prepare(request())

    def test_request_cache_identity_changes_with_coordinates_targets_required_and_capacity(self):
        original = request()
        for change in (dict(required_ids=[2]), dict(capacities=[1]), dict(coverage=[dict(region='甲', total=3, checked=1, reserved=0)])):
            self.assertNotEqual(request_key(original), request_key(dict(original, **change)))
