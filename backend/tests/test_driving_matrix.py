"""Complete matrix publication, read-only access and weekly refresh on a test DB."""
from datetime import datetime
from itertools import combinations
import os
from pathlib import Path
from unittest.mock import Mock, patch
import unittest
from flask import Flask, g
from psycopg2.extras import Json, execute_values

from driving_matrix import DrivingService, VIEW_PERMISSION, LOCK_ID, station_snapshot, snapshot_hash, next_refresh, latest_slot
from driving_matrix_http import register_driving_matrix
from driving_matrix_refresh import run_refresh
from driving_errors import DrivingUnavailable
from schedule_common import ScheduleConflict
from schedule_driving_routes import driving_request
from tests.driving_fakes import fake_distance
from tests import test_inspection_schedule as base


def seed_ready(test):
    stations, invalid = station_snapshot(test.cur)
    count = len(stations) * (len(stations)-1)//2
    test.cur.execute('''INSERT INTO driving_matrix_runs(slot,status,stations,invalid_stations,station_hash,
        expected_pairs,completed_pairs,finished_at) VALUES('fixture','published',%s,%s,%s,%s,%s,CURRENT_TIMESTAMP) RETURNING id''',
        (Json(stations), Json(invalid), snapshot_hash(stations), count, count))
    rid = test.cur.fetchone()['id']
    values = []
    for a, b in combinations(stations, 2):
        data = fake_distance('', [a['point']], b['point'], 0)['results'][0]
        values.append((rid, a['station_id'], b['station_id'], int(data['duration']), int(data['distance']), True))
    execute_values(test.cur, 'INSERT INTO driving_matrix_pairs(run_id,origin_id,destination_id,seconds,meters,reachable) VALUES %s', values)
    test.cur.execute('UPDATE driving_matrix_state SET active_run_id=%s,published_at=CURRENT_TIMESTAMP WHERE id=1', (rid,))
    test.admin.commit()
    return rid


class CalendarTests(unittest.TestCase):
    def test_shanghai_monday_0930_and_exact_boundary(self):
        before = datetime.fromisoformat('2026-10-26T09:29:59+08:00')
        at = datetime.fromisoformat('2026-10-26T01:30:00+00:00')
        self.assertEqual(next_refresh(before).isoformat(), '2026-10-26T09:30:00+08:00')
        self.assertEqual(next_refresh(at).isoformat(), '2026-11-02T09:30:00+08:00')
        self.assertEqual(latest_slot(at), '2026-10-26T09:30:00+08:00')

    def test_unauthenticated_does_not_connect_or_leak_connection_errors(self):
        app = Flask(__name__)
        actor = None
        app.before_request(lambda: setattr(g, 'current_user', actor))
        connect = Mock(side_effect=RuntimeError('private connection details'))
        register_driving_matrix(app, connect=connect, has_permission=lambda *_: True)
        client = app.test_client()
        self.assertEqual(client.get('/api/management/driving-matrix').status_code, 401)
        connect.assert_not_called()
        actor = dict(id=1)
        with self.assertLogs(level='ERROR'):
            response = client.get('/api/management/driving-matrix')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private connection', response.get_data(as_text=True))


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST') == '1', 'isolated PostgreSQL opt-in')
class MatrixDatabaseTests(unittest.TestCase):
    connect = base.ScheduleDatabaseTest.connect
    tearDown = base.ScheduleDatabaseTest.tearDown

    def setUp(self):
        base.ScheduleDatabaseTest.setUp(self)
        self.cur.execute('UPDATE stations SET longitude=121.1+id*.01')
        self.admin.commit()
        self.permissions.add(VIEW_PERMISSION)
        register_driving_matrix(self.client.application, connect=self.connect, has_permission=lambda _, actor, key: key in self.permissions)
        self.key = patch.dict(os.environ, {'AMAP_WEB_SERVICE_KEY': 'test-never-use-real-key'})
        self.key.start(); self.addCleanup(self.key.stop)
        self.clock = datetime.fromisoformat('2026-10-26T09:30:00+08:00')

    def collect(self, **kwargs):
        return run_refresh(self.connect, now=self.clock, fetch=fake_distance, sleep=lambda _: None, **kwargs)

    def test_initial_collects_each_unordered_pair_once_and_every_read_is_offline(self):
        fetch = Mock(side_effect=fake_distance)
        result = run_refresh(self.connect, now=self.clock, fetch=fetch, sleep=lambda _: None)
        self.assertEqual(result['pairs'], 10)

        self.cur.execute('SELECT last_error FROM driving_matrix_runs WHERE id=%s', (result['run_id'],))
        self.assertIsNone(self.cur.fetchone()['last_error'])
        self.assertEqual(fetch.call_count, 4)
        self.cur.execute('SELECT * FROM driving_matrix_pairs')
        rows = self.cur.fetchall()
        self.assertEqual(len(rows), 10)
        self.assertTrue(all(r['origin_id'] < r['destination_id'] for r in rows))
        req = driving_request([dict(station_id=i,region='松金',longitude=121.1+i*.01,latitude=31.2) for i in (1,3)], 1, 2, [], [], [2])
        service = DrivingService(self.connect)
        with patch('amap_driving.urlopen', side_effect=AssertionError('planning must be database-only')):
            plan = service.prepare(req)
            self.assertEqual(plan['source'], 'database')
            self.assertEqual(plan['api_requests'], 0)
            self.assertGreater(plan['trips'][0]['seconds'], 0)
            self.assertEqual(service.prepare(req), plan)
            response = self.client.get('/api/management/driving-matrix?station=3&counterpart=1')
            self.assertEqual(response.status_code, 200, response.json)
            self.assertEqual(response.json['total'], 1)
            self.assertEqual(response.json['items'][0]['seconds'], plan['trips'][0]['seconds'])
        token = 'a'*64
        service.remember(token, 2, self.clock.date(), plan)
        self.assertEqual(service.recall(token, 2, self.clock.date()), plan)
        with self.assertRaises(ScheduleConflict): service.recall(token, 3, self.clock.date())
        self.cur.execute("UPDATE driving_matrix_previews SET expires_at=CURRENT_TIMESTAMP-INTERVAL '1 second'"); self.admin.commit()
        with self.assertRaises(ScheduleConflict): service.recall(token, 2, self.clock.date())

    def test_failed_refresh_preserves_old_complete_generation_and_resumes_without_requery(self):
        old = seed_ready(self)
        self.cur.execute("UPDATE driving_matrix_runs SET finished_at='2026-10-25T10:00:00+08:00' WHERE id=%s", (old,)); self.admin.commit()
        calls = []
        def fail(key, origins, destination, timeout):
            calls.append(destination)
            if len(calls) == 2: raise DrivingUnavailable('测试网络中断')
            return fake_distance(key, origins, destination, timeout)
        with self.assertRaises(DrivingUnavailable):
            run_refresh(self.connect, now=self.clock, fetch=fail, sleep=lambda _: None)
        self.cur.execute('SELECT active_run_id FROM driving_matrix_state')
        self.assertEqual(self.cur.fetchone()['active_run_id'], old)
        self.cur.execute('SELECT * FROM driving_matrix_runs ORDER BY id DESC LIMIT 1')
        failed = self.cur.fetchone()
        self.assertEqual((failed['status'], failed['completed_pairs']), ('failed', 1))
        resume = Mock(side_effect=fake_distance)
        result = run_refresh(self.connect, now=self.clock, fetch=resume, sleep=lambda _: None)
        self.assertEqual(result['run_id'], failed['id'])
        self.assertEqual(resume.call_count, 3)
        self.assertEqual(result['pairs'], 10)
        self.cur.execute('SELECT last_error FROM driving_matrix_runs WHERE id=%s', (result['run_id'],))
        self.assertIsNone(self.cur.fetchone()['last_error'])

    def test_168_stations_collect_14028_unique_pairs_in_234_batches_of_at_most_100(self):
        execute_values(self.cur, '''INSERT INTO stations(id,station_name,region,longitude,latitude) VALUES %s''',
                       [(sid, f'测试站{sid}', '松金', 121.5+sid*.001, 31.2) for sid in range(6,169)])
        self.admin.commit()
        fetch = Mock(side_effect=fake_distance)
        result = run_refresh(self.connect, now=self.clock, fetch=fetch, sleep=lambda _: None)
        self.assertEqual(result['pairs'], 14028)
        self.assertEqual(fetch.call_count, 234)
        self.assertEqual(max(len(call.args[1]) for call in fetch.call_args_list), 100)
        self.assertTrue(all(call.args[2] not in call.args[1] for call in fetch.call_args_list))
        self.cur.execute('SELECT COUNT(*) n FROM driving_matrix_pairs WHERE origin_id<destination_id')
        self.assertEqual(self.cur.fetchone()['n'], 14028)

    def test_publication_failure_rolls_back_active_pointer_and_can_retry_without_api(self):
        old = seed_ready(self)
        self.cur.execute("UPDATE driving_matrix_runs SET finished_at='2026-10-25T10:00:00+08:00' WHERE id=%s", (old,))
        self.cur.execute('''CREATE FUNCTION reject_publication() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'isolated publication failure'; END; $$;
            CREATE TRIGGER reject_publication BEFORE UPDATE ON driving_matrix_state
            FOR EACH ROW EXECUTE FUNCTION reject_publication();''')
        self.admin.commit()
        with self.assertRaises(Exception):
            self.collect()
        self.cur.execute('SELECT active_run_id FROM driving_matrix_state')
        self.assertEqual(self.cur.fetchone()['active_run_id'], old)
        self.cur.execute('SELECT * FROM driving_matrix_runs ORDER BY id DESC LIMIT 1')
        failed = self.cur.fetchone()
        self.assertEqual((failed['status'], failed['completed_pairs'], failed['finished_at']), ('failed', 10, None))
        self.assertNotIn('isolated publication', failed['last_error'])
        self.cur.execute('DROP TRIGGER reject_publication ON driving_matrix_state'); self.admin.commit()
        fetch = Mock(side_effect=AssertionError('all pairs already collected'))
        result = run_refresh(self.connect, now=self.clock, fetch=fetch, sleep=lambda _: None)
        fetch.assert_not_called()
        self.assertEqual(result['run_id'], failed['id'])
        self.cur.execute('SELECT active_run_id FROM driving_matrix_state')
        self.assertEqual(self.cur.fetchone()['active_run_id'], failed['id'])

    def test_weekly_due_guard_and_duplicate_worker_do_not_consume_api(self):
        rid = seed_ready(self)
        self.cur.execute("UPDATE driving_matrix_runs SET finished_at='2026-10-25T10:00:00+08:00' WHERE id=%s", (rid,)); self.admin.commit()
        fetch = Mock(side_effect=fake_distance)
        result = run_refresh(self.connect, now=datetime.fromisoformat('2026-10-26T09:29:59+08:00'), fetch=fetch)
        self.assertEqual(result['status'], 'not_due'); fetch.assert_not_called()
        lease = self.connect(); lease.autocommit = True
        try:
            with lease.cursor() as cur: cur.execute('SELECT pg_advisory_lock(%s)', (LOCK_ID,))
            self.assertEqual(run_refresh(self.connect, now=self.clock, fetch=fetch)['status'], 'busy')
            fetch.assert_not_called()
            self.assertTrue(self.client.get('/api/management/driving-matrix').json['worker_running'])
        finally: lease.close()
        self.collect()
        self.assertEqual(self.collect()['status'], 'not_due')

    def test_missing_changed_coords_and_stale_weekly_data_never_trigger_http(self):
        seed_ready(self)
        service = DrivingService(self.connect)
        req = driving_request([dict(station_id=i,region='松金',longitude=121.1+i*.01,latitude=31.2) for i in (1,3)], 1, 2, [], [], [2])
        self.cur.execute("UPDATE driving_matrix_runs SET finished_at=CURRENT_TIMESTAMP-INTERVAL '30 days'"); self.admin.commit()
        with patch('amap_driving.urlopen', side_effect=AssertionError('no realtime fallback')):
            self.assertEqual(service.prepare(req)['source'], 'database')
            req['stations'][0]['point'][0] = 121.9
            with self.assertRaises(DrivingUnavailable): service.prepare(req)

    def test_read_permission_is_independent_get_only_and_does_not_initialize(self):
        self.permissions.discard(VIEW_PERMISSION)
        response = self.client.get('/api/management/driving-matrix')
        self.assertEqual(response.status_code, 403)
        self.permissions.add(VIEW_PERMISSION)
        self.assertIsNone(self.client.get('/api/management/driving-matrix').json['active'])
        for method in ('post','put','delete'):
            self.assertEqual(getattr(self.client, method)('/api/management/driving-matrix').status_code, 405)
        self.cur.execute('SELECT COUNT(*) AS n FROM driving_matrix_runs')
        self.assertEqual(self.cur.fetchone()['n'], 0)

    def test_unreachable_is_preserved_and_migration_does_not_clear_published_data(self):
        def missing(key, origins, destination, timeout):
            data = fake_distance(key, origins, destination, timeout)
            data['results'][0] = dict(origin_id='1',dest_id='1',code='1')
            return data
        result = run_refresh(self.connect, now=self.clock, fetch=missing, sleep=lambda _: None)
        self.assertEqual(result['status'], 'published')
        response = self.client.get('/api/management/driving-matrix?state=unreachable')
        self.assertGreater(response.json['total'], 0)
        self.assertTrue(all(item['seconds'] is None for item in response.json['items']))
        sql = (Path(__file__).resolve().parents[1] / 'db/init/580_driving_matrix.sql').read_text()
        self.cur.execute(sql); self.cur.execute(sql); self.admin.commit()
        self.cur.execute('SELECT active_run_id FROM driving_matrix_state')
        self.assertEqual(self.cur.fetchone()['active_run_id'], result['run_id'])

    def test_station_name_search_matches_either_endpoint_and_uses_literal_published_names(self):
        seed_ready(self)
        self.cur.execute("UPDATE stations SET station_name='新名称' WHERE id=3"); self.admin.commit()
        response = self.client.get('/api/management/driving-matrix', query_string={'keyword': '  泗砖  '})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['total'], 4)
        self.assertTrue(any(item['origin_id'] == 3 for item in response.json['items']))
        self.assertTrue(any(item['destination_id'] == 3 for item in response.json['items']))
        for keyword in ('新名称', '%', '_', "' OR 1=1 --", '不存在的站点'):
            result = self.client.get('/api/management/driving-matrix', query_string={'keyword': keyword})
            self.assertEqual(result.status_code, 200, result.json)
            self.assertEqual(result.json['total'], 0)
        self.assertEqual(self.client.get('/api/management/driving-matrix?station=1&keyword=泗砖').json['total'], 1)
        self.assertEqual(self.client.get('/api/management/driving-matrix?state=unreachable&keyword=泗砖').json['total'], 0)

    def test_distance_sort_both_directions_keeps_unreachable_last_and_rejects_invalid_conditions(self):
        seed_ready(self)
        self.cur.execute('UPDATE driving_matrix_pairs SET meters=1000')
        self.cur.execute('UPDATE driving_matrix_pairs SET meters=9000 WHERE origin_id=1 AND destination_id=2')
        self.cur.execute('UPDATE driving_matrix_pairs SET meters=500 WHERE origin_id=1 AND destination_id=3')
        self.cur.execute('UPDATE driving_matrix_pairs SET meters=NULL,seconds=NULL,reachable=false WHERE origin_id=1 AND destination_id=4')
        self.admin.commit()
        for order, first in (('distance_asc', 500), ('distance_desc', 9000)):
            response = self.client.get('/api/management/driving-matrix', query_string={'sort': order})
            self.assertEqual(response.status_code, 200, response.json)
            rows = response.json['items']
            self.assertEqual(rows[0]['meters'], first)
            self.assertFalse(rows[-1]['reachable'])
            self.assertEqual([r['meters'] for r in rows[:-1]], sorted([r['meters'] for r in rows[:-1]], reverse=order=='distance_desc'))
        for query in ({'keyword': '站'*81}, {'sort': 'meters; DROP TABLE stations'}, {'state': 'invalid'}, {'page': '0'}):
            self.assertEqual(self.client.get('/api/management/driving-matrix', query_string=query).status_code, 400)

    def test_named_route_results_are_paginated_and_reads_do_not_start_collection(self):
        execute_values(self.cur, 'INSERT INTO stations(id,station_name,region,longitude,latitude) VALUES %s',
                       [(sid, f'搜索测试站{sid}', '松金', 121.5+sid*.001, 31.2) for sid in range(6,41)])
        self.admin.commit()
        seed_ready(self)
        one = self.client.get('/api/management/driving-matrix?keyword=搜索测试站').json
        two = self.client.get('/api/management/driving-matrix?keyword=搜索测试站&page=2').json
        self.assertEqual(one['total'], 770)
        self.assertEqual(two['total'], one['total'])
        self.assertEqual(len(one['items']), 30)
        self.assertEqual(len(two['items']), 30)
        pairs = lambda page: {(r['origin_id'], r['destination_id']) for r in page['items']}
        self.assertFalse(pairs(one) & pairs(two))
        self.cur.execute('SELECT COUNT(*) n FROM driving_matrix_runs')
        self.assertEqual(self.cur.fetchone()['n'], 1)
