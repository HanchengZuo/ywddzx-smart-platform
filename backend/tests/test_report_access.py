import os
from contextlib import ExitStack
from pathlib import Path
import unittest
import uuid
from unittest.mock import MagicMock, patch

import psycopg2
from psycopg2.extensions import parse_dsn
import app as reports
from report_access import allowed_report_types, report_perspective, DEPARTMENT_REPORT_TYPES


class ReportAccessTest(unittest.TestCase):
    def permissions(self, **extra):
        return {'view_department_inspection_reports': True, **extra}

    def authorize(self, user, permissions):
        stack = ExitStack()
        stack.enter_context(patch('app.get_authenticated_request_user_id', return_value=user.get('id')))
        stack.enter_context(patch('app.get_user_by_id', return_value=user))
        stack.enter_context(patch('app.get_effective_permissions', return_value=permissions))
        return stack

    def test_perspective_matrix_and_center_compatibility(self):
        available = reports.INSPECTION_REPORT_TYPE_CONFIGS
        for role, keys in DEPARTMENT_REPORT_TYPES.items():
            user = {'id': 3, 'role': role}
            self.assertEqual(set(allowed_report_types(user, self.permissions(), available)), set(keys))
            self.assertEqual(report_perspective(user, {}), None)
            self.assertEqual(set(allowed_report_types(user, self.permissions(view_inspection_reports=True), available)), set(available))
        for role in ('supervisor', 'supervisor_manager', 'area_account', 'station_manager'):
            self.assertIsNone(report_perspective({'role': role}, self.permissions()))
        self.assertEqual(report_perspective({'role': 'root'}, {}), 'center')

    def test_department_status_uses_last_snapshot_without_configs_jobs_or_history(self):
        user = {'id': 3, 'role': 'non_oil'}
        saved = {'month': '2026-07', 'snapshot': {'id': 7, 'date_from': '2026-07-01', 'date_to': '2026-07-31'}}
        with reports.app.test_request_context('/api/inspection-reports/status?report_type=non_oil'), self.authorize(user, self.permissions(generate_inspection_reports=True)), patch(
            'app.get_db_connection', return_value=MagicMock()
        ), patch('app.list_report_months', return_value=[{'month': '2026-07', 'snapshot_id': 7}]), patch('app.get_inspection_report_snapshot_by_id', return_value=saved), patch(
            'app.get_current_report_workspace', side_effect=AssertionError('workspace must not load')
        ), patch('app.get_active_inspection_report_job', side_effect=AssertionError('jobs must not load')), patch(
            'app.list_report_generation_requests', side_effect=AssertionError('history must not load')
        ):
            result = reports.get_inspection_report_status().get_json()
        self.assertEqual(result['report'], saved)
        self.assertEqual(result['view_mode'], 'department')
        self.assertFalse(result['can_generate'])
        self.assertEqual(result['workspace'], {})
        self.assertEqual(result['history'], [])

    def test_types_filter_and_cross_department_status_export_denied_before_side_effects(self):
        user = {'id': 3, 'role': 'finance'}
        with reports.app.test_request_context('/api/inspection-reports/types'), self.authorize(user, self.permissions()), patch('app.get_db_connection', return_value=MagicMock()):
            result = reports.get_inspection_report_types().get_json()
            self.assertEqual([item['key'] for item in result['report_types']], ['finance'])
        for endpoint, handler, method in (
            ('status?report_type=non_oil', reports.get_inspection_report_status, 'GET'),
            ('exports/latest?report_type=non_oil', reports.get_latest_inspection_report_powerpoint_export, 'GET'),
            ('exports', reports.create_inspection_report_powerpoint_export, 'POST'),
        ):
            with self.subTest(endpoint=endpoint), reports.app.test_request_context('/api/inspection-reports/' + endpoint, method=method, json={'report_type': 'non_oil', 'snapshot_id': 9}), self.authorize(user, self.permissions()), patch('app.get_db_connection', return_value=MagicMock()) as connection, patch('app.start_inspection_report_export_task') as start:
                response = handler()
                self.assertEqual(response[1], 403)
                start.assert_not_called()
                connection.return_value.cursor.return_value.execute.assert_not_called()

    def test_department_cannot_call_center_helper_even_with_generation_grant(self):
        user = {'id': 3, 'role': 'quality_safety'}
        with self.authorize(user, self.permissions(generate_inspection_reports=True)):
            with self.assertRaises(PermissionError):
                reports.get_authorized_inspection_report_user(MagicMock())
            self.assertEqual(reports.get_authorized_inspection_report_user(MagicMock(), True, 'quality_measurement'), user)
            with self.assertRaises(PermissionError):
                reports.get_authorized_inspection_report_user(MagicMock(), True, 'finance')

    def test_old_export_task_cannot_bypass_changed_department_permission(self):
        user = {'id': 3, 'role': 'finance'}
        for handler, args in ((reports.get_inspection_report_powerpoint_export, ('task',)), (reports.download_inspection_report_powerpoint_export, ('task',)), (reports.get_report_ppt_preview_slide, ('task', 1))):
            with self.subTest(handler=handler.__name__), reports.app.test_request_context(), self.authorize(user, self.permissions()), patch('app.get_db_connection', return_value=MagicMock()), patch('app.get_inspection_report_export', return_value={'report_type': 'non_oil', 'status': 'completed'}), patch('app.send_file') as send:
                self.assertEqual(handler(*args)[1], 403)
                send.assert_not_called()

    def test_department_cannot_read_or_modify_workbench_or_trigger_ai(self):
        actions = (
            (reports.get_inspection_report_history, 'GET'),
            (reports.manage_inspection_report_workspace, 'GET'),
            (reports.manage_inspection_report_workspace, 'PUT'),
            (reports.get_inspection_report_source_options, 'GET'),
            (reports.get_inspection_report_source_options, 'PUT'),
            (reports.manage_quality_report_selection_settings, 'GET'),
            (reports.manage_quality_report_selection_settings, 'PUT'),
            (reports.manage_quality_report_flow_classifications, 'GET'),
            (reports.manage_non_oil_report_issue_selection, 'GET'),
            (reports.manage_non_oil_report_category_classifications, 'GET'),
            (reports.manage_non_oil_key_issue_classifications, 'GET'),
            (reports.manage_equipment_report_issue_selection, 'GET'),
            (reports.manage_equipment_analysis, 'GET'),
            (reports.create_inspection_report_generation_job, 'POST'),
        )
        user = {'id': 3, 'role': 'quality_safety'}
        for handler, method in actions:
            with self.subTest(handler=handler.__name__, method=method), reports.app.test_request_context(
                '/api/inspection-reports/history?report_type=quality_measurement&month=2026-09',
                method=method, json={'report_type': 'quality_measurement', 'month': '2026-09', 'generation_options': {'date_from': '2026-09-01', 'date_to': '2026-09-30'}}
            ), self.authorize(user, self.permissions(generate_inspection_reports=True)), patch('app.get_db_connection', return_value=MagicMock()) as connection, patch('app.start_inspection_report_generation_job') as start:
                self.assertEqual(handler()[1], 403)
                start.assert_not_called()
                connection.return_value.commit.assert_not_called()


@unittest.skipUnless(os.environ.get('REPORT_AI_MEMORY_TEST_DSN'), 'requires isolated PostgreSQL DSN')
class ReportAccessMigrationTest(unittest.TestCase):
    def test_migration_preserves_denials_other_roles_scopes_and_rolls_back(self):
        dsn = os.environ['REPORT_AI_MEMORY_TEST_DSN']
        if not parse_dsn(dsn).get('dbname', '').startswith('test_'):
            raise RuntimeError('Refusing non-test database')
        schema = 'report_access_' + uuid.uuid4().hex
        script = (Path(__file__).resolve().parents[1] / 'db/init/575_report_perspectives.sql').read_text()
        with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
            cur.execute(f'CREATE SCHEMA {schema}')
            cur.execute(f'SET LOCAL search_path = {schema}')
            cur.execute('CREATE TABLE users (id INT PRIMARY KEY, role TEXT, region TEXT)')
            cur.execute("INSERT INTO users VALUES (1,'quality_safety','浦东'),(2,'finance','松金'),(3,'supervisor','南汇')")
            for table, identity in [('user_permissions', 'user_id INT'), ('role_permissions', 'role TEXT')]:
                key = identity.split()[0]
                cur.execute(f'CREATE TABLE {table} ({identity}, permission_key TEXT, is_allowed BOOL, updated_by INT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY({key}, permission_key))')
            cur.execute("INSERT INTO role_permissions(role,permission_key,is_allowed) VALUES ('quality_safety','view_inspection_reports',true),('finance','view_inspection_reports',true),('supervisor','view_inspection_reports',true)")
            cur.execute("INSERT INTO user_permissions(user_id,permission_key,is_allowed) VALUES (1,'view_inspection_reports',false),(2,'view_inspection_reports',true),(3,'view_inspection_reports',true),(1,'unrelated_scope',true)")
            cur.execute('SAVEPOINT before_migration')
            cur.execute(script)
            cur.execute('ROLLBACK TO before_migration')
            cur.execute("SELECT count(*) FROM role_permissions WHERE permission_key='view_department_inspection_reports'")
            self.assertEqual(cur.fetchone()[0], 0)
            cur.execute(script)
            cur.execute(script)
            cur.execute("SELECT user_id,is_allowed FROM user_permissions WHERE permission_key='view_department_inspection_reports' ORDER BY user_id")
            self.assertEqual(cur.fetchall(), [(1, False), (2, True)])
            cur.execute("SELECT role,is_allowed FROM role_permissions WHERE permission_key='view_inspection_reports' ORDER BY role")
            self.assertEqual(cur.fetchall(), [('finance', False), ('quality_safety', False), ('supervisor', True)])
            cur.execute("SELECT is_allowed FROM user_permissions WHERE user_id=3 AND permission_key='view_inspection_reports'")
            self.assertTrue(cur.fetchone()[0])
            cur.execute('SELECT region FROM users WHERE id=1')
            self.assertEqual(cur.fetchone()[0], '浦东')
            cur.execute('SELECT is_allowed FROM user_permissions WHERE user_id=1 AND permission_key=\'unrelated_scope\'')
            self.assertTrue(cur.fetchone()[0])
            cur.execute(f'DROP SCHEMA {schema} CASCADE')
