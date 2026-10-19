import importlib.util
import json
import os
from contextlib import ExitStack
from datetime import date
from io import BytesIO
from pathlib import Path
import unittest
import uuid
from unittest.mock import MagicMock, patch

import psycopg2
from psycopg2.extras import RealDictCursor

import app as api
from station_plan_eligibility import enrollment_value, enrollment_error, plan_field


class StationPlanEligibilityTest(unittest.TestCase):
    def test_defaults_independent_false_and_strict_validation(self):
        for mode, field in [('offline', 'include_offline_plan'), ('online', 'include_online_plan')]:
            self.assertEqual(plan_field(mode), field)
            self.assertTrue(enrollment_value({}, field))
            self.assertFalse(enrollment_value({field: False}, field))
            self.assertFalse(enrollment_value({field: '否'}, field))
            self.assertTrue(enrollment_value({field: '是'}, field))
            for value in [None, '', 'false', 0, 1, [], {}]:
                with self.subTest(value=value), self.assertRaises(ValueError):
                    enrollment_value({field: value}, field)
        with self.assertRaises(ValueError):
            plan_field('offline; DELETE FROM stations')
        self.assertEqual(enrollment_error({'include_online_plan': False}, 'offline'), '')

    def test_payload_defaults_and_omitted_edit_markers(self):
        payload = api.build_station_payload({'station_name': '测试站', 'hos_station_code': 'TEST'})
        self.assertTrue(payload['include_offline_plan'])
        self.assertFalse(payload['include_offline_plan_provided'])
        payload = api.build_station_payload({'station_name': '测试站', 'hos_station_code': 'TEST', 'include_offline_plan': False})
        self.assertFalse(payload['include_offline_plan'])
        self.assertTrue(payload['include_offline_plan_provided'])
        self.assertTrue(payload['include_online_plan'])



@unittest.skipUnless(os.getenv('STATION_PLAN_DB_TEST') == '1', 'isolated database opt-in')
class StationPlanDatabaseTest(unittest.TestCase):
    def setUp(self):
        self.config = api.get_db_config()
        if not self.config['dbname'].startswith('test_station_plan_'):
            raise RuntimeError('Refusing non-test database')
        self.schema = 'test_plan_' + uuid.uuid4().hex
        self.conn = psycopg2.connect(**self.config, cursor_factory=RealDictCursor)
        self.cur = self.conn.cursor()
        self.cur.execute(f'CREATE SCHEMA {self.schema}; SET search_path TO {self.schema}')
        base = Path(__file__).resolve().parents[1]
        self.cur.execute((base / 'db/init/100_core_stations.sql').read_text())
        self.cur.execute('''
            CREATE TABLE users(id int PRIMARY KEY,username text,real_name text,phone text,role text,station_id int);
            INSERT INTO users VALUES(1,'root','管理','1','root',NULL),(2,'staff','检查人','2','supervisor',NULL);
            CREATE TABLE inspection_tables(id int PRIMARY KEY,table_name text,checklist_mode text,is_active boolean);
            INSERT INTO inspection_tables VALUES(1,'现场表','offline',true),(2,'视频表','online',true);
            CREATE TABLE inspections(id int PRIMARY KEY);
        ''')
        self.cur.execute("INSERT INTO stations(station_name,hos_station_code,station_type) VALUES('甲站','A','油站'),('乙站','B','油站'),('丙站','C','油站')")
        self.conn.commit()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(api, 'get_db_connection', side_effect=self.connect))
        self.stack.enter_context(patch.object(api, 'STATION_MANAGEMENT_SCHEMA_READY', True))
        self.stack.enter_context(patch.object(api, 'require_management_user', return_value={'id': 1, 'role': 'root'}))
        self.stack.enter_context(patch.object(api, 'get_user_by_id', return_value={'id': 1, 'role': 'root'}))
        self.stack.enter_context(patch.object(api, 'is_inspection_table_allowed_for_user', return_value=True))
        self.stack.enter_context(patch.object(api, 'is_station_region_allowed_for_user', return_value=True))
        self.stack.enter_context(patch.object(api, 'ensure_inspection_completion_schema'))

    def connect(self):
        return psycopg2.connect(**self.config, cursor_factory=RealDictCursor,
                                options=f'-c search_path={self.schema} -c timezone=Asia/Shanghai')

    def tearDown(self):
        self.conn.rollback()
        self.cur.execute(f'DROP SCHEMA {self.schema} CASCADE')
        self.conn.commit()
        self.cur.close()
        self.conn.close()

    def call(self, function, path, *, method='POST', data=None, args=()):
        with api.app.test_request_context(path, method=method, json=data):
            return api.app.make_response(function(*args))


    def test_migration_backfills_legacy_defaults_and_never_resets_false(self):
        self.cur.execute('CREATE TEMP TABLE stations(id int); INSERT INTO stations VALUES(10)')
        migration_path = Path(__file__).resolve().parents[1] / 'migrations/versions/20261019_001_station_plan_eligibility.py'
        spec = importlib.util.spec_from_file_location('station_plan_migration', migration_path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with patch.object(migration.op, 'execute', side_effect=self.cur.execute):
            migration.upgrade()
            self.cur.execute('SELECT include_offline_plan,include_online_plan FROM stations')
            self.assertEqual(tuple(self.cur.fetchone().values()), (True, True))
            self.cur.execute('UPDATE stations SET include_offline_plan=false')
            migration.upgrade()
        self.cur.execute('SELECT include_offline_plan,include_online_plan FROM stations')
        self.assertEqual(tuple(self.cur.fetchone().values()), (False, True))
        self.cur.execute('INSERT INTO stations(id) VALUES(11) RETURNING include_offline_plan,include_online_plan')
        self.assertEqual(tuple(self.cur.fetchone().values()), (True, True))

    def test_station_create_update_and_legacy_update_preserve_explicit_false(self):
        response = self.call(api.create_management_station, '/api/management/stations', data={'station_name': '新增站', 'hos_station_code': 'D'})
        self.assertEqual(response.status_code, 200, response.json)
        station = response.json['id']
        response = self.call(api.update_management_station, f'/api/management/stations/{station}', method='PUT', args=(station,),
                             data={'station_name': '新增站', 'hos_station_code': 'D', 'include_offline_plan': False})
        self.assertEqual(response.status_code, 200, response.json)
        response = self.call(api.update_management_station, f'/api/management/stations/{station}', method='PUT', args=(station,), data={'station_name': '改名站', 'hos_station_code': 'D'})
        self.assertEqual(response.status_code, 200, response.json)
        self.cur.execute('SELECT include_offline_plan,include_online_plan FROM stations WHERE id=%s', (station,))
        self.assertEqual(tuple(self.cur.fetchone().values()), (False, True))
        response = self.call(api.get_management_stations, '/api/management/stations', method='GET')
        self.assertEqual(next(row for row in response.json['stations'] if row['id'] == station)['include_offline_plan'], False)
        response = self.call(api.get_stations, '/api/stations?scope=plan', method='GET')
        self.assertEqual(next(row for row in response.json if row['id'] == station)['include_offline_plan'], False)

    def test_station_backup_round_trip_old_import_and_excel_labels(self):
        self.cur.execute('UPDATE stations SET include_offline_plan=false WHERE id=1')
        self.conn.commit()
        response = self.call(api.export_management_stations, '/api/management/stations/export', method='GET')
        row = response.json['stations'][0]
        self.assertIs(row['include_offline_plan'], False)
        self.assertIs(row['include_online_plan'], True)
        def restore(rows):
            with api.app.test_request_context('/api/management/stations/import', method='POST', data={
                'file': (BytesIO(json.dumps({'stations': rows}).encode()), 'stations.json')}):
                return api.app.make_response(api.import_management_stations())
        self.assertEqual(restore([row]).status_code, 200)
        row.pop('include_offline_plan'); row.pop('include_online_plan')
        self.assertEqual(restore([row]).status_code, 200)
        row.pop('id')
        self.assertEqual(restore([row]).status_code, 200)
        self.assertEqual(restore([{'station_name': '备份新站', 'hos_station_code': 'E'}]).status_code, 200)
        self.cur.execute('SELECT include_offline_plan FROM stations WHERE id=1')
        self.assertIs(self.cur.fetchone()['include_offline_plan'], False)
        from openpyxl import load_workbook
        book = load_workbook(api.build_station_data_export_workbook([{'include_offline_plan': False, 'include_online_plan': True}], ['include_offline_plan', 'include_online_plan']))
        self.assertEqual([cell.value for cell in book.active[2]], ['否', '是'])
        book.close()
