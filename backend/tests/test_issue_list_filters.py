import unittest

from app import append_issue_list_filter_clauses, normalize_issue_list_filters


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


if __name__ == "__main__":
    unittest.main()
