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
from station_plan_eligibility import SCHEMA_SQL, enrollment_value, enrollment_error, plan_field, require_plan_enrollment


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

    def test_existing_commitments_are_only_exception_to_disabled_enrollment(self):
        cur = MagicMock()
        station = dict(id=1, station_name='甲站', include_offline_plan=False)
        for previous in [None, {'is_included': False}]:
            cur.fetchone.return_value = previous
            with self.assertRaisesRegex(ValueError, '现场.*不能新增纳入'):
                require_plan_enrollment(cur, station, 'offline', 1)
        cur.fetchone.return_value = {'is_included': True}
        require_plan_enrollment(cur, station, 'offline', 1)
        cur.reset_mock()
        require_plan_enrollment(cur, station, 'online', 1)
        cur.execute.assert_not_called()


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
        self.cur.execute((base / 'db/init/500_inspection_plan_configs.sql').read_text())
        self.cur.execute((base / 'db/init/510_inspection_plan_station_items.sql').read_text())
        self.cur.execute('''
            ALTER TABLE inspection_plan_station_items ADD COLUMN assigned_inspector_ids jsonb DEFAULT '[]';
            INSERT INTO stations(station_name,hos_station_code,station_type) VALUES('甲站','A','油站'),('乙站','B','油站'),('丙站','C','油站');
            INSERT INTO inspection_plan_configs(id,inspection_table_id,coverage_type,period_key,created_by)
              VALUES(1,1,'quarterly','2026年第4季度',1),(2,2,'monthly','2026年10月',1);
            SELECT setval(pg_get_serial_sequence('inspection_plan_configs','id'),2,true);
        ''')
        self.conn.commit()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(api, 'get_db_connection', side_effect=self.connect))
        self.stack.enter_context(patch.object(api, 'STATION_MANAGEMENT_SCHEMA_READY', True))
        self.stack.enter_context(patch.object(api, 'require_management_user', return_value={'id': 1, 'role': 'root'}))
        self.stack.enter_context(patch.object(api, 'get_user_by_id', return_value={'id': 1, 'role': 'root'}))
        self.stack.enter_context(patch.object(api, 'can_manage_plan', return_value=True))
        self.stack.enter_context(patch.object(api, 'is_inspection_table_allowed_for_user', return_value=True))
        self.stack.enter_context(patch.object(api, 'is_station_region_allowed_for_user', return_value=True))
        self.stack.enter_context(patch.object(api, 'ensure_inspection_plan_assignment_schema'))
        self.stack.enter_context(patch.object(api, 'ensure_inspection_completion_schema'))
        self.stack.enter_context(patch.object(api, 'sync_plan_station_items_completion_by_history'))

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

    def save(self, plan, station, included=True):
        return self.call(api.save_inspection_plan_config_stations, f'/api/inspection-plan-configs/{plan}/stations',
                         method='PUT', data={'user_id': '1', 'stations': [{'station_id': station, 'is_included': included}]}, args=(plan,))

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

    def test_manual_enrollment_is_independent_and_cannot_bypass_with_bulk_save(self):
        self.cur.execute('UPDATE stations SET include_offline_plan=false WHERE id=1')
        self.conn.commit()
        self.assertEqual(self.save(1, 1).status_code, 400)
        self.assertEqual(self.save(2, 1).status_code, 200)
        response = self.call(api.save_inspection_plan_config_stations, '/api/inspection-plan-configs/1/stations', method='PUT', args=(1,),
                             data={'user_id': '1', 'stations': [{'station_id': 2}, {'station_id': 1}]})
        self.assertEqual(response.status_code, 400)
        self.cur.execute('SELECT count(*) AS n FROM inspection_plan_station_items WHERE plan_config_id=1')
        self.assertEqual(self.cur.fetchone()['n'], 0)

    def test_historical_enrollment_retained_but_removal_prevents_reinclusion(self):
        self.assertEqual(self.save(1, 1).status_code, 200)
        self.cur.execute('UPDATE stations SET include_offline_plan=false WHERE id=1')
        self.conn.commit()
        self.assertEqual(self.save(1, 1).status_code, 200)
        self.assertEqual(self.save(1, 1, False).status_code, 200)
        self.assertEqual(self.save(1, 1).status_code, 400)

    def test_new_plan_cannot_reuse_historical_exception_from_another_plan(self):
        self.assertEqual(self.save(1, 1).status_code, 200)
        self.cur.execute('UPDATE stations SET include_offline_plan=false WHERE id=1')
        self.conn.commit()
        response = self.call(api.create_inspection_plan_config, '/api/inspection-plan-configs', data={
            'user_id': '1', 'inspection_table_id': 1, 'coverage_type': 'quarterly', 'period_key': '2027年第1季度'})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(self.save(response.json['plan_config_id'], 1).status_code, 400)

    def test_template_preview_blocks_disabled_stations_before_writes(self):
        self.cur.execute('UPDATE stations SET include_offline_plan=false WHERE id=1')
        parsed = [{'table_name': '现场表', 'station_name': '甲站', 'inspectors': ['检查人']}]
        selected = dict(id=1, inspection_table_id=1, checklist_mode='offline', coverage_type='quarterly', period_key='2026年第4季度')
        with patch.object(api, 'select_current_plan_config', return_value=(selected, '')):
            rows, _, _ = api.resolve_plan_assignment_preview_rows(self.cur, {'id': 1}, parsed)
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]['can_apply'])
        self.assertIn('不能新增纳入', rows[0]['message'])

    def test_template_validation_rechecks_switch_and_preserves_monitoring_rule(self):
        row = {'plan_config_id': 1, 'station_id': 1, 'inspector_ids': [2]}
        api.validate_plan_assignment_apply_row(self.cur, {'id': 1}, row, date(2026, 10, 19))
        self.cur.execute('UPDATE stations SET include_offline_plan=false WHERE id=1')
        with self.assertRaisesRegex(ValueError, '不能新增纳入'):
            api.validate_plan_assignment_apply_row(self.cur, {'id': 1}, row, date(2026, 10, 19))
        self.cur.execute("UPDATE stations SET monitoring_status='未运行' WHERE id=2")
        self.conn.commit()
        self.assertEqual(self.save(2, 2).status_code, 400)

    def test_plan_detail_and_overview_show_current_flags_without_deleting_history(self):
        self.assertEqual(self.save(1, 1).status_code, 200)
        self.cur.execute('UPDATE stations SET include_offline_plan=false WHERE id=1')
        self.conn.commit()
        with patch.object(api, 'has_permission', return_value=True), patch.object(api, 'append_station_region_scope_filter', return_value=True):
            detail = self.call(api.get_inspection_plan_config_detail, '/api/inspection-plan-configs/1?user_id=1', method='GET', args=(1,))
            self.assertEqual(detail.status_code, 200, detail.json)
            self.assertIs(detail.json['item']['stations'][0]['include_offline_plan'], False)
            self.assertEqual(detail.json['item']['included_station_count'], 1)
            overview = self.call(api.get_inspection_plan_overview,
                '/api/inspection-plan-overview?user_id=1&inspection_table_id=1&coverage_type=quarterly&period_key=2026年第4季度', method='GET')
            self.assertEqual(overview.status_code, 200, overview.json)
            self.assertIs(overview.json['item']['stations'][0]['include_offline_plan'], False)

    def test_permission_denial_and_post_write_failure_leave_no_partial_data(self):
        with patch.object(api, 'require_management_user', side_effect=PermissionError('无权操作')):
            response = self.call(api.create_management_station, '/api/management/stations', data={'station_name': '无权新增', 'hos_station_code': 'Z'})
            self.assertEqual(response.status_code, 403)
        with patch.object(api, 'can_manage_plan', return_value=False):
            self.assertEqual(self.save(1, 1).status_code, 403)
        with patch.object(api, 'sync_plan_station_items_completion_by_history', side_effect=RuntimeError('forced rollback')):
            self.assertEqual(self.save(1, 1).status_code, 500)
        self.cur.execute('SELECT count(*) AS n FROM inspection_plan_station_items')
        self.assertEqual(self.cur.fetchone()['n'], 0)

    def test_enrollment_validation_locks_switch_until_transaction_finishes(self):
        api.validate_plan_assignment_apply_row(self.cur, {'id': 1}, {'plan_config_id': 1, 'station_id': 1, 'inspector_ids': [2]}, date(2026, 10, 19))
        other = self.connect()
        try:
            with other.cursor() as cur:
                cur.execute("SET LOCAL lock_timeout='100ms'")
                with self.assertRaises(psycopg2.errors.LockNotAvailable):
                    cur.execute('UPDATE stations SET include_offline_plan=false WHERE id=1')
                other.rollback()
                self.conn.rollback()
                cur.execute('UPDATE stations SET include_offline_plan=false WHERE id=1')
                other.commit()
        finally:
            other.close()
