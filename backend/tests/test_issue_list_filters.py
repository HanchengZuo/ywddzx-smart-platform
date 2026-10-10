import os
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch
from werkzeug.datastructures import MultiDict

import app as api
from app import append_issue_list_filter_clauses, normalize_issue_list_filters
from issue_description_filter import (
    IssueDescriptionFilterError, description_filter_clause, parse_description_keywords,
)


class IssueListFilterTests(unittest.TestCase):
    def test_month_becomes_an_inclusive_calendar_range(self):
        filters = normalize_issue_list_filters(
            {
                "month": "2026-09",
                "date_from": "2020-01-01",
                "date_to": "2020-01-02",
            }
        )

        self.assertEqual(filters["date_from"], "2026-09-01")
        self.assertEqual(filters["date_to"], "2026-09-30")

    def test_multi_select_and_camel_case_values_are_normalized(self):
        filters = normalize_issue_list_filters(
            {
                "regions": '["浦东", "松金", "浦东"]',
                "inspectionTableName": ["计量稽查检查表（现场）"],
                "standardTags": '["区域：卸油区"]',
                "issueDescription": "铅封",
            }
        )

        self.assertEqual(filters["regions"], ["浦东", "松金"])
        self.assertEqual(filters["inspection_tables"], ["计量稽查检查表（现场）"])
        self.assertEqual(filters["standard_tags"], ["区域：卸油区"])
        self.assertEqual(filters["issue_description"], "铅封")

    def test_filters_build_server_side_date_and_status_conditions(self):
        filters = normalize_issue_list_filters(
            {
                "date_from": "2026-09-01",
                "date_to": "2026-09-04",
                "status": "待签名",
                "audit_state": "done",
            }
        )
        clauses = []
        params = []

        append_issue_list_filter_clauses(clauses, params, filters)

        sql_text = " ".join(clauses)
        self.assertIn("i.created_at >= %s::date", sql_text)
        self.assertIn("i.created_at < (%s::date + INTERVAL '1 day')", sql_text)
        self.assertIn("i.status = '待整改'", sql_text)
        self.assertIn("COALESCE(i.audit_status, 'pending') <> 'pending'", sql_text)
        self.assertEqual(params[:2], ["2026-09-01", "2026-09-04"])

    def test_closed_status_keeps_legacy_status_aliases_visible(self):
        filters = normalize_issue_list_filters({"status": "已闭环"})
        clauses = []
        params = []

        append_issue_list_filter_clauses(clauses, params, filters)

        self.assertIn("i.status = ANY(%s)", " ".join(clauses))
        self.assertEqual(params[-1], ["已闭环", "已整改"])

    def test_keyword_separators_deduplication_and_empty_input(self):
        self.assertEqual(parse_description_keywords(' 接地,锈蚀，接地;破损；损坏、ETC\nEtc\t油品 '),
                         ['接地', '锈蚀', '破损', '损坏', 'ETC', '油品'])
        self.assertEqual(description_filter_clause(' ,，；、 '), ('', []))
        self.assertEqual(description_filter_clause('铅封')[1], ['%铅封%'])

    def test_get_and_export_json_preserve_commas_and_match_mode(self):
        for source in (MultiDict({'issue_description': '接地,锈蚀', 'description_match': 'any'}),
                       {'issueDescription': '接地,锈蚀', 'descriptionMatch': 'any'}):
            filters = normalize_issue_list_filters(source)
            self.assertEqual(filters['issue_description'], '接地,锈蚀')
            clauses, params = [], []
            append_issue_list_filter_clauses(clauses, params, filters)
            self.assertIn(' OR ', clauses[0])
            self.assertTrue(clauses[0].startswith('(') and clauses[0].endswith(')'))
            self.assertEqual(params, ['%接地%', '%锈蚀%'])

    def test_and_mode_and_literal_wildcards_are_bound_parameters(self):
        clause, params = description_filter_clause("50% A_B C!D 'OR")
        self.assertEqual(clause.count(' AND '), 3)
        self.assertNotIn('50%', clause)
        self.assertNotIn("'OR", clause)
        self.assertEqual(params, ['%50!%%', '%A!_B%', '%C!!D%', "%'OR%"])

    def test_limits_and_invalid_mode_rejected_without_silent_truncation(self):
        self.assertEqual(len(parse_description_keywords(' '.join(f'词{i}' for i in range(20)))), 20)
        for value in ('词' * 1001, '😀' * 1001, ' '.join(f'词{i}' for i in range(21))):
            with self.assertRaises(IssueDescriptionFilterError):
                normalize_issue_list_filters({'issue_description': value})
        with self.assertRaises(IssueDescriptionFilterError):
            normalize_issue_list_filters({'description_match': 'any) OR TRUE --'})

    def test_any_mode_keeps_visibility_and_other_filters_outside_or_group(self):
        cur = MagicMock()
        with patch.object(api, 'build_issue_list_visibility_scope', return_value=(['i.station_id = %s'], [7])), \
             patch.object(api, 'should_hide_inspector_contact_info', return_value=False):
            source = {'issue_description': '接地 锈蚀', 'description_match': 'any', 'regions': ['浦东']}
            _, where, params, _ = api.build_issue_list_query_context(cur, {'id': 1}, source)
            self.assertTrue(where.startswith('WHERE i.station_id = %s AND s.region = ANY(%s) AND ('))
            self.assertEqual(params, [7, ['浦东'], '%接地%', '%锈蚀%'])
            cur.fetchall.return_value = [{'id': 2}, {'id': 1}]
            self.assertEqual(api.fetch_issue_list_ids(cur, {'id': 1}, source), [2, 1])
            query, export_params = cur.execute.call_args.args
            self.assertIn(where, str(query))
            self.assertEqual(export_params, params)

    def test_invalid_description_returns_actionable_400(self):
        conn = MagicMock()
        conn.cursor.return_value.fetchone.return_value = {'id': 1, 'role': 'root'}
        with ExitStack() as stack:
            stack.enter_context(api.app.test_request_context('/api/issues', query_string={'user_id': 1, 'issue_description': '词' * 1001}))
            stack.enter_context(patch.object(api, 'get_db_connection', return_value=conn))
            for name in ('ensure_issue_inspector_schema', 'ensure_inspection_completion_schema', 'auto_complete_overdue_inspections',
                         'can_edit_inspection_issues', 'can_delete_inspection_issues', 'can_audit_inspection_issues', 'can_change_issue_inspector'):
                stack.enter_context(patch.object(api, name))
            response, status = api.get_issues()
            self.assertEqual(status, 400)
            self.assertIn('1000', response.get_json()['error'])

    def test_export_summary_retains_description_and_mode_label(self):
        summary = {'issueDescription': '任一包含：接地、锈蚀'}
        self.assertEqual(api.normalize_issue_export_filter_summary(summary), summary)

    @unittest.skipUnless(os.environ.get('ISSUE_LIFECYCLE_DB_TEST') == '1', 'local PostgreSQL; temporary table only')
    def test_postgres_literal_matches_scope_count_and_pagination(self):
        conn = api.get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute('CREATE TEMP TABLE issues(id int, station_id int, description text)')
            rows = [(1, 1, '接地线锈蚀'), (2, 1, '接地损坏'), (3, 1, '锈蚀的接地线'),
                    (4, 2, '锈蚀'), (5, 1, '50% A_B C!D'), (6, 1, '500 A0B CDD'), (7, 1, None)]
            cur.executemany('INSERT INTO issues VALUES(%s,%s,%s)', rows)
            for mode, expected in [('all', [1, 3]), ('any', [1, 2, 3])]:
                clause, params = description_filter_clause('接地,锈蚀', mode)
                where = 'i.station_id = %s AND ' + clause
                cur.execute('SELECT count(*) AS n FROM issues i WHERE ' + where, [1, *params])
                self.assertEqual(cur.fetchone()['n'], len(expected))
                for offset, expected_id in enumerate(expected):
                    cur.execute('SELECT id FROM issues i WHERE ' + where + ' ORDER BY id LIMIT 1 OFFSET %s', [1, *params, offset])
                    self.assertEqual(cur.fetchone()['id'], expected_id)
            for text in ('50%', 'A_B', 'C!D'):
                clause, params = description_filter_clause(text)
                cur.execute('SELECT id FROM issues i WHERE ' + clause, params)
                self.assertEqual([row['id'] for row in cur.fetchall()], [5])
        finally:
            conn.rollback()
            conn.close()


if __name__ == "__main__":
    unittest.main()
