import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import app as api


class PendingReviewPaginationTests(unittest.TestCase):
    def test_default_has_no_date_limit_and_cannot_override_pending_status(self):
        where, params = api.build_pending_review_filters({'status': '已闭环', 'audit_status': 'rejected'})
        self.assertIn(api.PENDING_REVIEW_WHERE, where)
        self.assertNotIn('created_at', where)
        self.assertEqual(params, [])

    def test_exact_ids_dates_multiple_selection_and_parameterized_keywords(self):
        where, params = api.build_pending_review_filters({
            'issue_id': '1000', 'standard_id': '1000', 'month': '2026-09',
            'date_from': '2026-09-05', 'date_to': '2026-09-09',
            'stations': '["甲站", "乙站"]', 'regions': '["浦东"]',
            'inspectors': '["测试人"]', 'inspection_tables': '["现场表"]',
            'standard_tags': '["区域：加油区"]', 'station_manager': '站长',
            'standard_detail': '库存', 'issue_description': "' OR TRUE --",
        })
        self.assertIn('i.id::text = %s', where)
        self.assertIn("COALESCE(i.standard_id::text, '') = %s", where)
        self.assertIn('EXISTS', where)
        self.assertNotIn("' OR TRUE --", where)
        self.assertIn(["甲站", "乙站"], params)
        for value in ('2026-09-05', '2026-09-09', '2026-09-01', '2026-09-30'):
            self.assertIn(value, params)

    def test_page_is_bounded_and_reads_only_current_page_without_sync(self):
        for role in ('root', 'supervisor'):
            with self.subTest(role=role), ExitStack() as stack:
                stack.enter_context(api.app.test_request_context('/api/my-issues?page=999&page_size=5'))
                stack.enter_context(patch('app.get_authenticated_request_user_id', return_value=7))
                conn = MagicMock(); cur = conn.cursor.return_value
                cur.fetchone.side_effect = [{'id': 7, 'role': role}, {'total': 11}]
                cur.fetchall.return_value = [{'id': 1}]
                stack.enter_context(patch('app.get_db_connection', return_value=conn))
                tags = stack.enter_context(patch('app.attach_internal_standard_tags_to_issue_rows'))
                stack.enter_context(patch('app.normalize_issue_row_for_response', side_effect=lambda row, *args: row))
                for name in ('can_edit_inspection_issues', 'can_delete_inspection_issues', 'can_change_issue_inspector'):
                    stack.enter_context(patch('app.' + name, return_value=False))
                for name in ('ensure_issue_inspector_schema', 'ensure_inspection_completion_schema',
                             'sync_signed_inspections_completion', 'auto_complete_overdue_inspections'):
                    stack.enter_context(patch('app.' + name, side_effect=AssertionError('read must not synchronize')))
                result = api.get_my_issues().get_json()
                self.assertEqual((result['total'], result['page'], result['page_size']), (11, 3, 5))
                query, params = cur.execute.call_args.args
                self.assertIn('WITH page_ids AS MATERIALIZED', query)
                self.assertIn('LIMIT %s OFFSET %s', query)
                self.assertEqual(params[-2:], [5, 10])
                self.assertEqual(tags.call_args.args[1], [{'id': 1}])
                conn.commit.assert_not_called()

    def test_options_are_role_protected_and_not_page_limited(self):
        with api.app.test_request_context(), patch('app.get_db_connection', return_value=MagicMock()), patch(
            'app.get_current_request_user', return_value={'id': 2, 'role': 'station_manager'}
        ):
            self.assertEqual(api.get_pending_review_filter_options()[1], 403)
        conn = MagicMock(); cur = conn.cursor.return_value
        cur.fetchone.return_value = {'stations': ['第一页以外的站点'], 'codes': []}
        with api.app.test_request_context(), patch('app.get_db_connection', return_value=conn), patch(
            'app.get_current_request_user', return_value={'id': 1, 'role': 'supervisor'}
        ), patch('app.fetch_internal_standard_tags_by_codes', return_value={}):
            result = api.get_pending_review_filter_options().get_json()
        self.assertEqual(result['filter_options']['stations'], ['第一页以外的站点'])
        self.assertNotIn('LIMIT', cur.execute.call_args.args[0])

    @unittest.skipUnless(os.environ.get('ISSUE_LIFECYCLE_DB_TEST') == '1', 'Requires local PostgreSQL; temporary tables only')
    def test_real_postgres_pages_filters_and_repeatable_index(self):
        conn = api.get_db_connection(); cur = conn.cursor()
        try:
            cur.execute('''
                CREATE TEMP TABLE inspections (id int, inspector_id int);
                CREATE TEMP TABLE stations (id int, region text, station_name text, station_manager_name text);
                CREATE TEMP TABLE users (id int, real_name text);
                CREATE TEMP TABLE inspection_tables (id int, table_name text);
                CREATE TEMP TABLE issues (id int, inspection_id int, station_id int, inspection_table_id int,
                    inspector_id int, status text, audit_status text, created_at timestamp,
                    standard_id text, standard_detail_text text, internal_standard_detail_text text, description text);
                INSERT INTO inspections VALUES (1,1);
                INSERT INTO stations VALUES (1,'浦东','甲站','甲经理');
                INSERT INTO users VALUES (1,'甲检查人');
                INSERT INTO inspection_tables VALUES (1,'现场表');
                INSERT INTO issues SELECT n,1,1,1,1,'待复核','approved',
                    CASE WHEN n<100 THEN '2025-01-01'::timestamp ELSE '2026-09-01'::timestamp END,
                    CASE WHEN n=1 THEN '1000' ELSE '11000' END,'库存','','积水'
                    FROM generate_series(1,121) n;
                INSERT INTO issues VALUES (999,1,1,1,1,'待复核','rejected',now(),'1000','','','');
            ''')
            where, params = api.build_pending_review_filters({})
            cur.execute(f'SELECT COUNT(*) AS total {api.PENDING_REVIEW_JOINS} {where}', params)
            self.assertEqual(cur.fetchone()['total'], 121)
            cur.execute(f'SELECT i.id {api.PENDING_REVIEW_JOINS} {where} ORDER BY i.id DESC LIMIT 20 OFFSET 20', params)
            self.assertEqual([r['id'] for r in cur.fetchall()], list(range(101,81,-1)))
            where, params = api.build_pending_review_filters({'standard_id': '1000'})
            cur.execute(f'SELECT i.id {api.PENDING_REVIEW_JOINS} {where}', params)
            self.assertEqual([r['id'] for r in cur.fetchall()], [1])
            path = Path(__file__).parents[1] / 'migrations/versions/20260907_001_pending_review_pagination.py'
            spec = importlib.util.spec_from_file_location('review_index', path)
            migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
            migration.op = SimpleNamespace(execute=cur.execute)
            migration.upgrade(); migration.upgrade()
            cur.execute("SELECT count(*) AS n FROM pg_indexes WHERE tablename='issues' AND indexname='idx_issues_pending_review_id' AND schemaname LIKE 'pg_temp_%'")
            self.assertEqual(cur.fetchone()['n'], 1)
        finally:
            conn.rollback(); cur.close(); conn.close()
