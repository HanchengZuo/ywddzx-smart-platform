import os
import unittest
import uuid
from datetime import date
from unittest.mock import MagicMock, patch

import psycopg2
from psycopg2.extensions import parse_dsn
from psycopg2.extras import Json, RealDictCursor

import app as reports
from report_months import list_report_months, valid_report_month


class ReportMonthsTest(unittest.TestCase):
    def test_month_validation(self):
        for value in ('2026-09', '2025-12'):
            self.assertTrue(valid_report_month(value))
        for value in ('2026-9', '2026-13', '2026-00', '2026-09-01', '', None, '2026-01\n'):
            self.assertFalse(valid_report_month(value))

    def test_catalog_filters_unusable_payloads_and_keeps_latest_generated_per_month(self):
        cur = MagicMock()
        cur.fetchall.return_value = [
            {'id': 9, 'report_month': '2026-07', 'payload_month': '2026-07', 'data_policy_version': 'current'},
            {'id': 8, 'report_month': '2026-09', 'payload_month': '2026-09', 'data_policy_version': 'old'},
            {'id': 7, 'report_month': '2026-07', 'payload_month': '2026-07', 'data_policy_version': 'current'},
            {'id': 6, 'report_month': '2026-09', 'payload_month': '2026-09', 'data_policy_version': 'current'},
            {'id': 5, 'report_month': '2026-08', 'payload_month': None, 'data_policy_version': 'current'},
        ]
        result = list_report_months(cur, 'non_oil', lambda _, payload: payload['data_policy_version'] == 'current')
        self.assertEqual(result, [{'month': '2026-07', 'snapshot_id': 9}, {'month': '2026-09', 'snapshot_id': 6}])
        self.assertEqual(cur.execute.call_args.args[1], ('non_oil',))

    def test_department_month_reads_history_and_never_reads_or_generates_workspace(self):
        user = {'id': 3, 'role': 'quality_safety'}
        months = [{'month': '2026-09', 'snapshot_id': 20}, {'month': '2026-07', 'snapshot_id': 11}]
        for month, expected_id, status in [('', 20, 200), ('2026-07', 11, 200), ('2026-08', None, 404), ('2026-13', None, 400)]:
            with self.subTest(month=month), reports.app.test_request_context('/api/inspection-reports/status?report_type=quality_measurement&month=' + month), patch('app.get_db_connection', return_value=MagicMock()), patch('app.get_authorized_inspection_report_user', return_value=user), patch('app.get_inspection_report_capabilities', return_value={'view_mode': 'department', 'can_generate': False}), patch('app.list_report_months', return_value=months), patch('app.get_inspection_report_snapshot_by_id', return_value={'month': month or '2026-09', 'snapshot': {'id': expected_id}}) as read, patch('app.get_latest_inspection_report_snapshot', side_effect=AssertionError('must use selected history')), patch('app.get_current_report_workspace', side_effect=AssertionError('no workspace')), patch('app.queue_or_get_inspection_report_job', side_effect=AssertionError('no AI')):
                response = reports.get_inspection_report_status()
                actual_status = response[1] if isinstance(response, tuple) else response.status_code
                self.assertEqual(actual_status, status)
                if expected_id:
                    data = response.get_json()
                    self.assertEqual(data['report']['snapshot']['id'], expected_id)
                    self.assertEqual(data['available_months'], months)
                    self.assertEqual(read.call_args.args[1:], (expected_id, 'quality_measurement', month or '2026-09'))
                else:
                    read.assert_not_called()

    def test_no_finished_month_has_no_report_and_cannot_queue_generation(self):
        with reports.app.test_request_context('/api/inspection-reports/status?report_type=finance'), patch('app.get_db_connection', return_value=MagicMock()), patch('app.get_authorized_inspection_report_user', return_value={'id': 3, 'role': 'finance'}), patch('app.get_inspection_report_capabilities', return_value={'view_mode': 'department'}), patch('app.list_report_months', return_value=[]), patch('app.get_inspection_report_snapshot_by_id') as read, patch('app.get_active_inspection_report_job') as jobs:
            data = reports.get_inspection_report_status().get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['available_months'], [])
        self.assertEqual(data['selected_month'], '')
        self.assertIsNone(data['report'])
        read.assert_not_called()
        jobs.assert_not_called()


@unittest.skipUnless(os.environ.get('REPORT_AI_MEMORY_TEST_DSN'), 'requires isolated PostgreSQL DSN')
class ReportMonthsPostgresTest(unittest.TestCase):
    def test_query_uses_saved_report_month_latest_success_and_type_constraints(self):
        dsn = os.environ['REPORT_AI_MEMORY_TEST_DSN']
        if not parse_dsn(dsn).get('dbname', '').startswith('test_'):
            raise RuntimeError('Refusing non-test database')
        schema = 'report_months_' + uuid.uuid4().hex
        with psycopg2.connect(dsn, cursor_factory=RealDictCursor) as conn, conn.cursor() as cur:
            cur.execute(f'CREATE SCHEMA {schema}')
            cur.execute(f'SET LOCAL search_path = {schema}')
            cur.execute('''CREATE TABLE inspection_report_snapshots (
                id SERIAL PRIMARY KEY, report_type TEXT, report_month TEXT,
                generated_at TIMESTAMP, report_payload JSONB,
                generated_by_name TEXT, period_start DATE, period_end_exclusive DATE, generation_context JSONB)''')
            for kind, month, timestamp, policy in [('non_oil', '2026-09', '2026-10-01', 'current'), ('non_oil', '2026-07', '2026-10-02', 'current'), ('non_oil', '2026-07', '2026-10-03', 'current'), ('non_oil', '2026-08', '2026-10-04', 'old'), ('finance', '2026-06', '2026-10-05', 'current')]:
                cur.execute('INSERT INTO inspection_report_snapshots (report_type,report_month,generated_at,report_payload,period_start,period_end_exclusive) VALUES (%s,%s,%s,%s,%s,%s)', (kind, month, timestamp, Json({'month': month, 'data_policy_version': policy}), date(2026, 7, 1), date(2026, 8, 1)))
            current = lambda _, payload: payload['data_policy_version'] == 'current'
            result = list_report_months(cur, 'non_oil', current)
            self.assertEqual(result, [{'month': '2026-07', 'snapshot_id': 3}, {'month': '2026-09', 'snapshot_id': 1}])
            with patch('app.report_snapshot_table_available', return_value=True), patch('app.is_inspection_report_snapshot_current', side_effect=current):
                self.assertEqual(reports.get_inspection_report_snapshot_by_id(cur, 3, 'non_oil', '2026-07')['month'], '2026-07')
                self.assertIsNone(reports.get_inspection_report_snapshot_by_id(cur, 3, 'finance', '2026-07'))
                self.assertIsNone(reports.get_inspection_report_snapshot_by_id(cur, 3, 'non_oil', '2026-09'))
            cur.execute(f'DROP SCHEMA {schema} CASCADE')
