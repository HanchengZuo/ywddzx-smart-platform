import importlib.util
import os
import unittest
import uuid
from contextlib import ExitStack
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import psycopg2
from psycopg2.extras import Json, RealDictCursor
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

import app as reports
from report_workspace import get_report_workspace, save_report_workspace, list_report_generation_requests


class ReportWorkspaceTest(unittest.TestCase):
    def test_status_ignores_historical_snapshot_and_date_parameters(self):
        with reports.app.test_request_context(
            '/api/inspection-reports/status?report_type=non_oil&snapshot_id=1&month=2024-01'
        ), patch('app.get_db_connection', return_value=MagicMock()), patch(
            'app.get_authorized_inspection_report_user', return_value={'id': 3}
        ), patch('app.get_latest_inspection_report_snapshot', return_value={'month': '2026-09'}) as latest, patch(
            'app.get_inspection_report_snapshot_by_id', side_effect=AssertionError('must not read historical snapshot')
        ), patch('app.get_active_inspection_report_job', return_value=None), patch(
            'app.get_current_report_workspace', return_value={}
        ), patch('app.list_report_generation_requests', return_value=[]), patch(
            'app.get_inspection_report_capabilities', return_value={}
        ):
            result = reports.get_inspection_report_status().get_json()
        self.assertEqual(result['report']['month'], '2026-09')
        self.assertEqual(latest.call_args.args[1:], ('non_oil',))

    def test_date_save_requires_generation_permission_and_uses_server_identity(self):
        for allowed in (True, False):
            with self.subTest(allowed=allowed), reports.app.test_request_context(
                '/api/inspection-reports/workspace', method='PUT', json={
                    'report_type': 'non_oil', 'user_id': 999,
                    'generation_options': {'date_from': '2026-07-01', 'date_to': '2026-07-31'},
                }
            ), patch('app.get_db_connection', return_value=MagicMock()), patch(
                'app.get_authorized_inspection_report_user', return_value={'id': 3}
            ), patch('app.has_permission', return_value=allowed), patch(
                'app.get_latest_inspection_report_snapshot', return_value=None
            ), patch('app.get_current_report_workspace', return_value={}), patch(
                'app.save_report_workspace'
            ) as save, patch('app.start_inspection_report_generation_job') as generate:
                response = reports.manage_inspection_report_workspace()
            generate.assert_not_called()
            if allowed:
                self.assertTrue(response.get_json()['success'])
                self.assertEqual(save.call_args.args[2]['id'], 3)
            else:
                self.assertEqual(response[1], 403)
                save.assert_not_called()

    def test_revision_alone_does_not_flag_configuration_difference(self):
        with patch('app.get_report_workspace', return_value={
            'revision': 8, 'generation_options': {'date_from': '2026-08-01', 'date_to': '2026-08-31'},
        }):
            value = reports.get_current_report_workspace(None, 'non_oil', {'workspace_revision': 7})
        self.assertNotIn('regeneration_required', value)
        self.assertEqual(value['generation_options']['date_from'], '2026-08-01')

    def test_generation_uses_last_shared_dates_not_stale_browser_dates(self):
        dates = {'date_from': '2026-08-01', 'date_to': '2026-08-31'}
        with reports.app.test_request_context(json={
            'report_type': 'non_oil', 'use_saved_configuration': True,
            'generation_options': {'date_from': '2026-07-01', 'date_to': '2026-07-31'},
        }), patch('app.get_db_connection', return_value=MagicMock()), patch(
            'app.get_authorized_inspection_report_user', return_value={'id': 2}
        ), patch('app.has_permission', return_value=True), patch(
            'app.get_report_workspace', return_value={'generation_options': dates}
        ), patch('app.save_report_workspace'), patch(
            'app.queue_or_get_inspection_report_job', return_value=(None, None, False)
        ) as queue:
            response, status = reports.create_inspection_report_generation_job()
        self.assertEqual(status, 200)
        self.assertEqual(queue.call_args.args[3], '2026-08')
        self.assertEqual(queue.call_args.args[5]['date_from'], dates['date_from'])

    def test_classification_query_enforces_approved_completed_and_scoped_issues(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        with patch('app.append_inspection_table_scope_filter', return_value=True), patch(
            'app.append_station_region_scope_filter', return_value=True
        ):
            reports.fetch_non_oil_report_issue_rows(cur, {'id': 3}, date(2026, 7, 1), date(2026, 8, 1))
        query = repr(cur.execute.call_args.args[0])
        self.assertIn("audit_status", query)
        self.assertIn("approved", query)
        self.assertIn("已确认完成", query)

    def test_report_panels_are_global_without_changing_business_page_scopes(self):
        user = {'id': 2, 'role': 'area'}
        cur = MagicMock()
        cur.fetchall.return_value = []
        restricted = {'limit_plan_inspection_table_scope': True, 'limit_plan_station_region_scope': True}
        with patch('app.get_effective_permissions', return_value=restricted), patch(
            'app.get_user_inspection_table_scope_overrides', return_value=[7]
        ), patch('app.get_user_station_region_scope_overrides', return_value=['浦东']):
            normal_where, normal_params = [], []
            reports.append_station_region_scope_filter(cur, user, normal_where, normal_params, 's.region', 'limit_plan_station_region_scope')
            self.assertEqual(normal_params, [['浦东']])
            reports.fetch_non_oil_report_issue_rows(cur, user, date(2026, 7, 1), date(2026, 8, 1))
            query, params = cur.execute.call_args.args
            self.assertNotIn(['浦东'], params)
            self.assertNotIn([7], params)


@unittest.skipUnless(os.environ.get('REPORT_AI_MEMORY_TEST_DSN'), 'requires isolated PostgreSQL test DSN')
class ReportWorkspacePostgresTest(unittest.TestCase):
    @classmethod
    def connect(cls, dictionaries=False):
        kwargs = {'cursor_factory': RealDictCursor} if dictionaries else {}
        return psycopg2.connect(cls.dsn, options=f'-c search_path={cls.schema} -c timezone=Asia/Shanghai', **kwargs)

    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ['REPORT_AI_MEMORY_TEST_DSN']
        cls.schema = 'report_workspace_test_' + uuid.uuid4().hex
        with psycopg2.connect(cls.dsn) as conn, conn.cursor() as cur:
            cur.execute(f'CREATE SCHEMA "{cls.schema}"')
        cls.engine = sa.create_engine('postgresql+psycopg2://', creator=cls.connect)
        path = Path(__file__).resolve().parents[1] / 'migrations/versions/20260903_002_report_workspace.py'
        spec = importlib.util.spec_from_file_location('workspace_migration', path)
        cls.migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.migration)
        meta_path = path.with_name('20260903_003_report_section_meta.py')
        meta_spec = importlib.util.spec_from_file_location('section_meta_migration', meta_path)
        cls.meta_migration = importlib.util.module_from_spec(meta_spec)
        meta_spec.loader.exec_module(cls.meta_migration)
        with cls.engine.begin() as connection:
            connection.execute(sa.text('CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, real_name TEXT)'))
            connection.execute(sa.text("INSERT INTO users VALUES (1, 'user1', '用户甲'), (2, 'user2', '用户乙')"))
            connection.execute(sa.text('''CREATE TABLE inspection_report_jobs (
                task_id TEXT PRIMARY KEY, report_type TEXT, requested_by INTEGER,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP, status TEXT,
                period_start DATE, period_end_exclusive DATE
            )'''))
            connection.execute(sa.text('''CREATE TABLE inspection_report_snapshots (
                id SERIAL PRIMARY KEY, report_type TEXT, report_month TEXT, report_payload JSONB,
                generated_by_name TEXT, generated_at TIMESTAMPTZ,
                period_start DATE, period_end_exclusive DATE, generation_context JSONB
            )'''))
            for table in ('inspection_report_non_oil_key_issue_classifications', 'inspection_report_non_oil_issue_classifications'):
                connection.execute(sa.text(f'''CREATE TABLE {table} (
                    issue_id INTEGER PRIMARY KEY, original_category TEXT, effective_category TEXT,
                    ai_category TEXT, classification_source TEXT, reason TEXT, model_name TEXT,
                    updated_by INTEGER, classified_at TIMESTAMPTZ, updated_at TIMESTAMPTZ
                )'''))
            with Operations.context(MigrationContext.configure(connection)):
                cls.migration.upgrade()
                cls.meta_migration.upgrade()

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        with psycopg2.connect(cls.dsn) as conn, conn.cursor() as cur:
            cur.execute(f'DROP SCHEMA "{cls.schema}" CASCADE')

    def setUp(self):
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute('''TRUNCATE inspection_report_workspaces, inspection_report_jobs,
                inspection_report_snapshots, inspection_report_non_oil_key_issue_classifications,
                inspection_report_non_oil_issue_classifications''')

    def test_workspace_survives_connections_and_repeated_migrations(self):
        dates = {'date_from': '2026-07-01', 'date_to': '2026-07-31'}
        with self.connect(True) as conn, conn.cursor() as cur:
            first = save_report_workspace(cur, 'non_oil', {'id': 1, 'real_name': '用户甲'}, dates)
            same = save_report_workspace(cur, 'non_oil', {'id': 1}, dates)
            self.assertEqual(first['revision'], same['revision'])
            save_report_workspace(cur, 'non_oil', {'id': 2, 'real_name': '用户乙'}, section='key_classification')
        with self.engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
            self.migration.upgrade()
            self.migration.upgrade()
            self.meta_migration.upgrade()
            self.meta_migration.upgrade()
        with self.connect(True) as conn, conn.cursor() as cur:
            saved = get_report_workspace(cur, 'non_oil')
            self.assertEqual(saved['generation_options'], dates)
            self.assertEqual(saved['updated_by_name'], '用户乙')
            self.assertEqual(saved['revision'], first['revision'] + 1)
            self.assertEqual(saved['section_meta']['date_range']['updated_by_name'], '用户甲')
            self.assertEqual(saved['section_meta']['key_classification']['updated_by_name'], '用户乙')
            self.assertEqual(get_report_workspace(cur, 'finance')['generation_options'], {})

    def test_request_history_keeps_same_range_and_operator_at_click_time(self):
        with self.connect(True) as conn, conn.cursor() as cur:
            for task, user, timestamp in [('first', '用户甲', '2026-09-01 10:00:01+08'), ('second', '用户乙', '2026-09-01 11:00:02+08')]:
                cur.execute('''INSERT INTO inspection_report_jobs
                    (task_id, report_type, requested_by_name, status, created_at, period_start, period_end_exclusive)
                    VALUES (%s, 'non_oil', %s, 'completed', %s, '2026-07-01', '2026-08-01')''', (task, user, timestamp))
            history = list_report_generation_requests(cur, 'non_oil')
        self.assertEqual([row['task_id'] for row in history], ['second', 'first'])
        self.assertEqual(history[0]['requested_by_name'], '用户乙')
        self.assertEqual(history[0]['requested_at'], '2026-09-01 11:00:02')
        self.assertEqual(history[0]['date_to'], '2026-07-31')

    def test_latest_report_is_latest_generation_not_latest_period(self):
        with self.connect(True) as conn, conn.cursor() as cur:
            for month, generated in [('2026-08', '2026-09-01'), ('2026-07', '2026-09-02')]:
                cur.execute('''INSERT INTO inspection_report_snapshots
                    (report_type, report_month, report_payload, generated_at, period_start, period_end_exclusive)
                    VALUES ('non_oil', %s, %s, %s, %s, %s)''', (
                    month, Json({'month': month}), generated, month + '-01', month + '-02',
                ))
            with patch('app.report_snapshot_table_available', return_value=True), patch(
                'app.is_inspection_report_snapshot_current', return_value=True
            ):
                latest = reports.get_latest_inspection_report_snapshot(cur, 'non_oil')
        self.assertEqual(latest['month'], '2026-07')

    def classification_request(self, handler, method='GET', issue_id=51, category=None):
        raw = {'id': 51, 'table_name': reports.NON_OIL_REPORT_ONSITE_TABLE,
               'standard_detail_text': '检查项目：其他', 'description': '检查问题', 'station_name': '测试站'}
        params = {'date_from': '2026-07-01', 'date_to': '2026-07-31', 'snapshot_id': 999}
        kwargs = {'query_string': params} if method == 'GET' else {
            'json': {**params, 'user_id': 999, 'classifications': [{'issue_id': issue_id, 'category': category}]},
        }
        with ExitStack() as stack:
            stack.enter_context(reports.app.test_request_context(method=method, **kwargs))
            for name, value in {
                'get_authorized_inspection_report_user': {'id': 2, 'real_name': '用户乙'},
                'fetch_non_oil_report_issue_rows': [raw],
                'get_non_oil_report_excluded_issue_ids': set(),
                'non_oil_report_classification_table_available': True,
                'non_oil_key_issue_classification_table_available': True,
            }.items():
                stack.enter_context(patch(f'app.{name}', return_value=value))
            stack.enter_context(patch('app.get_db_connection', side_effect=lambda: self.connect(True)))
            snapshot = stack.enter_context(patch('app.get_inspection_report_snapshot_by_id'))
            generate = stack.enter_context(patch('app.start_inspection_report_generation_job'))
            response = handler()
            snapshot.assert_not_called()
            generate.assert_not_called()
        return response

    def test_manual_key_classification_save_reload_and_ai_protection(self):
        handler = reports.manage_non_oil_key_issue_classifications
        for category in ('重点商品', '不纳入重点问题', '月度盘点'):
            response = self.classification_request(handler, 'PUT', category=category)
            self.assertTrue(response.get_json()['success'])
            reloaded = self.classification_request(handler).get_json()['classifications'][0]
            self.assertEqual(reloaded['effective_category'], category)
            self.assertEqual(reloaded['classification_source'], 'manual')
            self.assertEqual(reloaded['updated_by_name'], '用户乙')
        with self.connect(True) as conn, conn.cursor() as cur, patch(
            'app.non_oil_key_issue_classification_table_available', return_value=True
        ):
            reports.persist_non_oil_key_issue_classifications(cur, {51: {'category': '重点商品', 'source': 'ai'}}, 1)
            saved = reports.get_non_oil_key_issue_classification_map(cur, [51])
            self.assertEqual(saved[51]['effective_category'], '月度盘点')
            self.assertEqual(reports.build_non_oil_key_issue_classification_context([{'id': 51}], saved)['issues'], [])
            issue = reports.serialize_non_oil_report_issue({'id': 51}, {}, saved)
            self.assertEqual(issue['key_issue_category'], '月度盘点')
            cur.execute('SELECT updated_by FROM inspection_report_non_oil_key_issue_classifications WHERE issue_id=51')
            self.assertEqual(cur.fetchone()['updated_by'], 2)

    def test_other_classification_save_reload_and_out_of_scope_rejected(self):
        handler = reports.manage_non_oil_report_category_classifications
        response = self.classification_request(handler, 'PUT', category='便利店卫生情况')
        self.assertTrue(response.get_json()['success'])
        reloaded = self.classification_request(handler).get_json()['classifications'][0]
        self.assertEqual(reloaded['effective_category'], '便利店卫生情况')
        response = self.classification_request(handler, 'PUT', issue_id=99, category='便利店卫生情况')
        self.assertEqual(response[1], 400)
        with self.connect(True) as conn, conn.cursor() as cur:
            cur.execute('SELECT count(*) AS count FROM inspection_report_non_oil_issue_classifications')
            self.assertEqual(cur.fetchone()['count'], 1)


if __name__ == '__main__':
    unittest.main()
