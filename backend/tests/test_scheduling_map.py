import os
import unittest
import uuid
from datetime import date
from unittest.mock import MagicMock, patch

from flask import Flask, g

import app as core_app
from scheduling_map import PERMISSION, coverage, period, register_scheduling_map


class SchedulingMapTest(unittest.TestCase):
    def test_period_defaults_and_rollovers(self):
        chosen, start, end = period({}, date(2026, 10, 19))
        self.assertEqual((chosen['quarter'], start, end), (4, date(2026, 10, 1), date(2027, 1, 1)))
        self.assertEqual(chosen['date_to'], '2026-12-31')
        chosen, start, end = period({'mode': 'online', 'year': '2024', 'month': '2'})
        self.assertEqual((start, end, chosen['date_to']), (date(2024, 2, 1), date(2024, 3, 1), '2024-02-29'))
        self.assertEqual(period({'mode': 'online', 'month': '12', 'year': '2026'})[2], date(2027, 1, 1))

    def test_invalid_or_mixed_periods_are_rejected(self):
        for query in ({'mode': '现场'}, {'mode': 'offline', 'month': '1'},
                      {'mode': 'online', 'quarter': '1'}, {'quarter': '0'}, {'quarter': '5'},
                      {'year': '1999'}, {'year': '2101'}, {'year': True}, {'year': '2026 OR 1=1'},
                      {'mode': 'online', 'month': '13'}, {'mode': 'online', 'month': '1.5'}):
            with self.subTest(query=query), self.assertRaises(ValueError):
                period(query)

    def test_permission_is_independent_and_denied_by_default(self):
        for role in core_app.ROLE_OPTIONS:
            self.assertEqual(core_app.role_default_permission(role, PERMISSION), role == 'root', role)
        with patch.object(core_app, 'get_role_permission_overrides', return_value={}), \
             patch.object(core_app, 'get_permission_overrides', return_value={}):
            self.assertFalse(core_app.has_permission(MagicMock(), {'id': 5, 'role': 'supervisor'}, PERMISSION))
            with patch.object(core_app, 'get_permission_overrides', return_value={PERMISSION: True}):
                self.assertTrue(core_app.has_permission(MagicMock(), {'id': 5, 'role': 'supervisor'}, PERMISSION))
        self.assertEqual(core_app.app.test_client().get('/api/scheduling-map').status_code, 401)

    def api(self, user=None, allowed=True):
        app = Flask(__name__)
        app.before_request(lambda: setattr(g, 'current_user', user))
        connect = MagicMock()
        cursor = connect.return_value.cursor.return_value
        permitted = MagicMock(return_value=allowed)
        scope = MagicMock(return_value=(([], []), ([], [])))
        register_scheduling_map(app, connect=connect, has_permission=permitted, scope=scope)
        return app.test_client(), connect, cursor, permitted, scope

    def test_auth_denial_does_not_query_or_use_client_identity(self):
        client, connect, *_ = self.api()
        self.assertEqual(client.get('/api/scheduling-map?user_id=1').status_code, 401)
        connect.assert_not_called()
        user = {'id': 8, 'role': 'area_account'}
        client, connect, cursor, permitted, scope = self.api(user, False)
        self.assertEqual(client.get('/api/scheduling-map?user_id=1').status_code, 403)
        permitted.assert_called_once_with(cursor, user, PERMISSION)
        scope.assert_not_called()
        cursor.close.assert_called_once()
        connect.return_value.close.assert_called_once()

    def test_success_is_private_and_uses_server_scope(self):
        user = {'id': 8}
        client, connect, cursor, _, scope = self.api(user)
        with patch('scheduling_map.coverage', return_value={'summary': {'remaining': 2}}) as query:
            response = client.get('/api/scheduling-map?mode=online&year=2026&month=10&user_id=1&region=ALL')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'success': True, 'summary': {'remaining': 2}})
        self.assertEqual(response.headers['Cache-Control'], 'private, no-store')
        scope.assert_called_once_with(cursor, user)
        self.assertEqual(query.call_args.args[2:4], (date(2026, 10, 1), date(2026, 11, 1)))
        connect.return_value.commit.assert_not_called()
        connect.return_value.close.assert_called_once()

    def test_validation_and_query_failure_release_connection_without_commit(self):
        client, connect, cursor, _, _ = self.api({'id': 1})
        self.assertEqual(client.get('/api/scheduling-map?mode=offline&month=10').status_code, 400)
        with patch('scheduling_map.coverage', side_effect=RuntimeError('private SQL')):
            with self.assertLogs(level='ERROR'):
                response = client.get('/api/scheduling-map')
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('private SQL', response.get_data(as_text=True))
        self.assertEqual(connect.return_value.close.call_count, 2)
        self.assertEqual(cursor.close.call_count, 2)
        connect.return_value.commit.assert_not_called()


@unittest.skipUnless(os.getenv('SCHEDULING_MAP_DB_TEST') == '1', 'isolated database opt-in')
class SchedulingMapDatabaseTest(unittest.TestCase):
    def setUp(self):
        self.conn = core_app.get_db_connection()
        self.cur = self.conn.cursor()
        schema = 'test_schedule_' + uuid.uuid4().hex
        self.cur.execute(f'CREATE SCHEMA {schema}; SET LOCAL search_path TO {schema}')
        # No issues table: coverage must never depend on issue audits or presence.
        self.cur.execute('''
          CREATE TABLE stations(id int,station_name text,region text,address text,longitude numeric,latitude numeric,status text);
          CREATE TABLE inspection_tables(id int,checklist_mode text);
          CREATE TABLE inspections(id int,station_id int,inspection_table_id int,inspection_date date,
            sign_status text,completion_status text);
          INSERT INTO stations VALUES
            (1,'甲站','浦东','甲路',121.5,31.2,'营业'),(2,'乙站','浦东','乙路',121.6,31.3,'营业'),
            (3,'丙站','宝静','丙路',121.4,31.4,'停业'),(4,'无坐标站',NULL,NULL,NULL,NULL,'营业'),
            (5,'零坐标站','浦东',NULL,0,0,'营业'),(6,'非法坐标站','宝静',NULL,200,30,'营业');
          INSERT INTO inspection_tables VALUES(1,'offline'),(2,'offline'),(3,'online');
          INSERT INTO inspections VALUES
            (1,1,1,'2026-10-01','待签名确认','未确认'),(2,1,2,'2026-10-02','待签名确认','未确认'),
            (3,2,3,'2026-10-31','待签名确认','未确认'),(4,3,1,'2026-09-30','已签名确认','已确认'),
            (5,3,2,'2027-01-01','已签名确认','已确认');
        ''')

    def tearDown(self):
        self.conn.rollback()
        self.cur.close()
        self.conn.close()

    def result(self, source=None, stations=(None, None), tables=(None, None)):
        chosen, start, end = period(source or {'mode': 'offline', 'year': '2026', 'quarter': '4'})
        return coverage(self.cur, chosen, start, end,
                        (stations[0] or [], stations[1] or []), (tables[0] or [], tables[1] or []))

    def test_any_one_table_counts_even_unsigned_incomplete_zero_issue_records(self):
        result = self.result()
        self.assertEqual(result['summary'], dict(total=6, checked=1, remaining=5, missing_coordinates=3))
        self.assertEqual({s['station_id'] for s in result['stations']}, {2, 3, 4, 5, 6})
        self.assertEqual(len(result['regions']), 3)
        self.assertIn('未填写片区', [r['region'] for r in result['regions']])
        self.assertEqual(next(r for r in result['regions'] if r['region'] == '浦东')['checked'], 1)

    def test_video_uses_selected_month_and_not_offline_records(self):
        result = self.result({'mode': 'online', 'year': '2026', 'month': '10'})
        self.assertEqual(result['summary']['checked'], 1)
        self.assertNotIn(2, [s['station_id'] for s in result['stations']])
        self.assertIn(1, [s['station_id'] for s in result['stations']])
        self.assertEqual(self.result({'mode': 'online', 'year': '2026', 'month': '11'})['summary']['checked'], 0)

    def test_period_edges_and_deleted_records(self):
        self.assertEqual(self.result()['summary']['checked'], 1)
        self.cur.execute("INSERT INTO inspections VALUES(6,3,1,'2026-12-31',NULL,NULL)")
        self.assertEqual(self.result()['summary']['checked'], 2)
        self.cur.execute('DELETE FROM inspections WHERE station_id=1')
        self.assertEqual(self.result()['summary']['checked'], 1)
        self.assertIn(1, [s['station_id'] for s in self.result()['stations']])

    def test_scope_applies_to_denominator_coverage_and_pins(self):
        result = self.result(stations=(['s.region=%s'], ['浦东']), tables=(['t.id=%s'], [2]))
        self.assertEqual(result['summary'], dict(total=3, checked=1, remaining=2, missing_coordinates=1))
        self.assertTrue(all(s['region'] == '浦东' for s in result['stations']))
        result = self.result(stations=(['s.id=%s'], [3]))
        self.assertEqual(result['stations'][0]['status'], '停业')
        self.assertEqual(result['summary']['remaining'], 1)

    def test_empty_scope_and_absent_checklist_do_not_mark_all_stations_overdue(self):
        result = self.result(tables=(['FALSE'], []))
        self.assertFalse(result['has_tables'])
        self.assertEqual(result['summary']['total'], 0)
        self.assertEqual(result['stations'], [])
        self.assertEqual(self.result(stations=(['FALSE'], []))['summary']['total'], 0)

    def test_fully_covered_has_no_pins(self):
        result = self.result(stations=(['s.id=%s'], [1]))
        self.assertEqual(result['summary'], dict(total=1, checked=1, remaining=0, missing_coordinates=0))
        self.assertEqual(result['stations'], [])

    def test_response_only_includes_uncovered_station_coordinates_without_region_geometry(self):
        result = self.result(stations=(['s.id=%s'], [2]))
        self.assertNotIn('region_points', result)
        self.assertEqual([row['station_id'] for row in result['stations']], [2])
        self.assertEqual(self.result(stations=(['FALSE'], []))['stations'], [])

    def test_real_scope_builder_preserves_own_region_and_table_limits(self):
        for permissions, user, regions, table_ids, expected in [
            ({'view_all_inspection_records': True}, {'id': 1}, None, None, 6),
            ({'view_own_inspection_records': True}, {'id': 2, 'station_id': 2}, None, None, 1),
            ({'view_own_inspection_records': True}, {'id': 2}, None, None, 0),
            ({'limit_record_station_region_scope': True}, {'id': 3}, {'浦东'}, {2}, 3),
            ({'limit_record_station_region_scope': True}, {'id': 3}, set(), {2}, 0),
            ({}, {'id': 4}, None, None, 0),
        ]:
            with self.subTest(permissions=permissions, user=user, regions=regions):
                with patch.object(core_app, 'get_effective_permissions', return_value=permissions), \
                     patch.object(core_app, 'get_effective_station_region_scope_values', return_value=regions), \
                     patch.object(core_app, 'get_effective_inspection_table_scope_ids', return_value=table_ids):
                    station_scope, table_scope = core_app.scheduling_map_scope(self.cur, user)
                result = self.result(stations=station_scope, tables=table_scope)
                self.assertEqual(result['summary']['total'], expected)

    def test_query_is_one_statement_and_read_only_transaction_rolls_back(self):
        cursor = MagicMock(wraps=self.cur)
        chosen, start, end = period({'year': '2026', 'quarter': '4'})
        result = coverage(cursor, chosen, start, end, ([], []), ([], []))
        self.assertEqual(cursor.execute.call_count, 1)
        self.assertEqual(result['summary']['total'], 6)
        self.cur.execute('SELECT count(*) AS count FROM inspections')
        self.assertEqual(self.cur.fetchone()['count'], 5)
        # Rolling back removes only this disposable schema and fixture data.
        self.conn.rollback()
