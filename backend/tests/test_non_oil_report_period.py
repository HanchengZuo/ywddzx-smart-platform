import unittest
from datetime import date
from unittest.mock import MagicMock, patch

import app as report_app
from app import (
    build_inspection_report_generation_context,
    build_non_oil_previous_rectification,
    normalize_inspection_report_generation_options,
    parse_non_oil_report_period,
    resolve_non_oil_rectification_period,
    resolve_non_oil_report_period,
)


class NonOilReportPeriodTest(unittest.TestCase):
    def test_rectification_default_uses_main_start_and_calendar_month(self):
        for start, previous in (
            (date(2026, 8, 15), date(2026, 7, 15)),
            (date(2026, 1, 1), date(2025, 12, 1)),
            (date(2026, 3, 31), date(2026, 2, 28)),
            (date(2024, 3, 31), date(2024, 2, 29)),
        ):
            with self.subTest(start=start):
                self.assertEqual(resolve_non_oil_rectification_period(start), (previous, start))

    def test_rectification_override_does_not_change_main_range(self):
        options = normalize_inspection_report_generation_options({
            "date_from": "2026-08-15", "date_to": "2026-09-02",
            "non_oil_rectification_date_from": "2026-06-01",
            "non_oil_rectification_date_to": "2026-07-31",
        })
        self.assertEqual(resolve_non_oil_report_period("2026-09", options), (date(2026, 8, 15), date(2026, 9, 3)))
        self.assertEqual(resolve_non_oil_rectification_period(date(2026, 8, 15), options), (date(2026, 6, 1), date(2026, 8, 1)))
        self.assertEqual(normalize_inspection_report_generation_options(options), options)

    def test_rectification_range_validation(self):
        for start, end in (
            ("2026-07-01", ""), ("", "2026-07-31"),
            ("2026-02-30", "2026-03-01"),
            ("2026-08-01", "2026-07-01"),
            ("2024-01-01", "2026-01-01"),
        ):
            with self.subTest(start=start, end=end), self.assertRaisesRegex(ValueError, "第四页整改统计"):
                normalize_inspection_report_generation_options({
                    "non_oil_rectification_date_from": start,
                    "non_oil_rectification_date_to": end,
                })

    def test_narrative_and_snapshot_store_actual_rectification_dates(self):
        rows = [
            {"unit_type": "region", "unit_type_label": "片区", "unit_name": "浦东", "status": status}
            for status in ("待整改", "待复核", "已整改")
        ]
        with patch("app.serialize_non_oil_report_issue", side_effect=lambda row: row):
            summary = build_non_oil_previous_rectification(
                date(2026, 9, 1), rows, (date(2026, 6, 15), date(2026, 8, 1)),
            )
        self.assertIn("2026年6月15日至2026年7月31日各片区整改情况", summary["narrative"])
        self.assertEqual(summary["totals"], {"total_count": 3, "pending_acceptance_count": 1, "pending_rectification_count": 1})
        context = build_inspection_report_generation_context({"previous_month_rectification": summary})
        self.assertEqual(context["non_oil_rectification_period"], {"date_from": "2026-06-15", "date_to": "2026-07-31"})

    def test_invalid_generation_dates_return_400_not_500(self):
        with report_app.app.test_request_context(json={
            "report_type": "non_oil", "month": "2026-07",
            "generation_options": {"non_oil_rectification_date_from": "2026-06-01"},
        }):
            response, status = report_app.create_inspection_report_generation_job()
        self.assertEqual(status, 400)
        self.assertIn("第四页整改统计", response.get_json()["error"])

    def test_custom_rectification_period_still_requires_generation_permission(self):
        with report_app.app.test_request_context(json={
            "report_type": "non_oil", "month": "2026-07",
            "generation_options": {
                "non_oil_rectification_date_from": "2026-05-01",
                "non_oil_rectification_date_to": "2026-06-30",
            },
        }), patch("app.get_db_connection", return_value=MagicMock()), patch(
            "app.get_authorized_inspection_report_user", return_value={"id": 2}
        ), patch("app.has_permission", return_value=False), patch("app.queue_or_get_inspection_report_job") as queue:
            _, status = report_app.create_inspection_report_generation_job()
        self.assertEqual(status, 403)
        queue.assert_not_called()

    def test_background_job_fetches_independent_range_without_calling_ai(self):
        options = {
            "date_from": "2026-08-15", "date_to": "2026-09-02",
            "non_oil_rectification_date_from": "2026-06-01",
            "non_oil_rectification_date_to": "2026-07-31",
        }
        from contextlib import ExitStack
        with ExitStack() as stack:
            mocked = {}
            for name, value in {
                "get_db_connection": MagicMock(), "get_user_by_id": {"id": 1},
                "has_permission": True, "update_inspection_report_job": None,
                "resolve_inspection_report_source_selection": ({}, {}),
                "get_non_oil_report_excluded_issue_ids": set(),
                "get_non_oil_report_classification_map": {},
                "get_non_oil_key_issue_classification_map": {},
                "append_inspection_table_scope_filter": False,
                "append_station_region_scope_filter": False,
                "fetch_non_oil_report_issue_rows": [],
                "build_non_oil_template_presentation": {"slide_count": 0},
                "save_inspection_report_snapshot": None,
                "generate_non_oil_report_insights": None,
            }.items():
                mocked[name] = stack.enter_context(patch(f"app.{name}", return_value=value))
            report_app.generate_non_oil_report_job("test-period", 1, "2026-09", "scope", options)
        calls = mocked["fetch_non_oil_report_issue_rows"].call_args_list
        self.assertEqual(calls[0].args[2:4], (date(2026, 8, 15), date(2026, 9, 3)))
        self.assertEqual(calls[1].args[2:4], (date(2026, 6, 1), date(2026, 8, 1)))
        self.assertFalse(calls[1].kwargs["apply_station_filter"])
        saved = mocked["save_inspection_report_snapshot"].call_args.args[4]
        self.assertEqual(saved["previous_month_rectification"]["date_from"], "2026-06-01")
        mocked["generate_non_oil_report_insights"].assert_not_called()

    def test_default_period_uses_calendar_month(self):
        self.assertEqual(
            parse_non_oil_report_period("2026-07"),
            (date(2026, 7, 1), date(2026, 8, 1)),
        )

    def test_custom_period_remains_inclusive(self):
        self.assertEqual(
            resolve_non_oil_report_period(
                "2026-07",
                {"date_from": "2026-06-26", "date_to": "2026-07-29"},
            ),
            (date(2026, 6, 26), date(2026, 7, 30)),
        )


if __name__ == "__main__":
    unittest.main()
