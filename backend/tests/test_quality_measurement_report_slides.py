import unittest
from datetime import date

from app import (
    build_quality_measurement_report_payload,
    build_quality_measurement_report_slides,
    build_report_deep_analysis,
    build_report_flow_highlights,
    build_report_prohibited_examples,
)
from report_presentation import InspectionReportPresentation


def make_issue(issue_id, flow="人员管理", prohibited=False, standard_id=None, excellent=False):
    return {
        "id": issue_id,
        "station_id": issue_id % 4 + 1,
        "station_name": f"测试站点{issue_id % 4 + 1}",
        "region": "浦东片区",
        "table_name": "计量稽查检查表（现场）",
        "standard_id": standard_id or 1000 + issue_id,
        "standard_detail_text": (
            f"业务流程：{flow}\n是否禁止项：{'是' if prohibited else '否'}"
        ),
        "description": f"第{issue_id}条测试问题描述",
        "issue_photo": "",
        "is_excellent": excellent,
    }


class QualityMeasurementReportSlidesTest(unittest.TestCase):
    def test_highlight_sample_thresholds(self):
        cases = ((21, 8), (11, 6), (5, 4), (4, 2), (1, 1))
        for issue_count, expected_count in cases:
            serialized = [
                {
                    "issue_id": index,
                    "business_flow": "人员管理",
                    "description": f"问题{index}",
                }
                for index in range(1, issue_count + 1)
            ]
            result = build_report_flow_highlights(
                [{"name": "人员管理", "count": issue_count, "percentage": 100}],
                serialized,
                None,
                {},
            )
            self.assertEqual(len(result[0]["highlighted_issues"]), expected_count)

    def test_payload_and_slides_share_requested_structure(self):
        rows = [
            make_issue(index, "人员管理" if index <= 6 else "器具管理", index == 3)
            for index in range(1, 10)
        ]
        report = build_quality_measurement_report_payload(date(2026, 7, 1), rows)
        distribution = report["finding_summary"]["business_flow_distribution"]
        report["deep_analysis"] = build_report_deep_analysis(
            date(2026, 7, 1), rows, distribution, None, {}
        )
        report["slides"] = build_quality_measurement_report_slides(report)

        self.assertEqual(report["rows"][0]["oil_depot_count"], 0)
        self.assertEqual(report["rows"][0]["transport_vehicle_count"], 0)
        self.assertEqual(report["rows"][0]["violation_issue_count"], 0)
        self.assertIn("X座油库", report["overview_text"])
        self.assertIn("抽检4把加油枪", report["overview_text"])
        self.assertEqual(
            [slide["kind"] for slide in report["slides"][:4]],
            ["overall", "finding_overview", "prohibited", "flow_chart"],
        )
        self.assertEqual(report["slides"][-3]["kind"], "management_trace")
        self.assertEqual(report["slides"][-2]["kind"], "trace_analysis")
        self.assertEqual(report["slides"][-1]["kind"], "work_plan")

    def test_custom_sample_counts_and_standard_priority(self):
        serialized = [
            {
                "issue_id": index,
                "standard_id": 2000 + index,
                "business_flow": "器具管理",
                "description": f"问题{index}",
            }
            for index in range(1, 13)
        ]
        settings = {
            "sample_counts": {
                "more_than_20": 10,
                "more_than_10": 4,
                "more_than_4": 2,
                "at_most_4": 1,
            },
            "flow_standard_priorities": {"器具管理": [2011, 2008]},
        }
        result = build_report_flow_highlights(
            [{"name": "器具管理", "count": 12, "percentage": 100}],
            serialized,
            None,
            settings,
        )
        selected = result[0]["highlighted_issues"]
        self.assertEqual(len(selected), 4)
        self.assertEqual([item["standard_id"] for item in selected[:2]], [2011, 2008])

    def test_prohibited_selection_prefers_star_then_priority_then_ai(self):
        starred_rows = [
            make_issue(1, prohibited=True, standard_id=1001),
            make_issue(2, prohibited=True, standard_id=1002, excellent=True),
        ]
        selected = build_report_prohibited_examples(
            starred_rows,
            {"prohibited_standard_priorities": [1001]},
            None,
        )
        self.assertEqual(selected[0]["issue_id"], 2)
        self.assertEqual(selected[0]["selection_source"], "starred")

        priority_rows = [
            make_issue(3, prohibited=True, standard_id=1003),
            make_issue(4, prohibited=True, standard_id=1004),
        ]
        selected = build_report_prohibited_examples(
            priority_rows,
            {"prohibited_standard_priorities": [1004, 1003]},
            None,
        )
        self.assertEqual(selected[0]["issue_id"], 4)
        self.assertEqual(selected[0]["selection_source"], "standard_priority")

        ai_rows = [
            make_issue(5, prohibited=True, standard_id=1005),
            make_issue(6, prohibited=True, standard_id=1006),
        ]
        selected = build_report_prohibited_examples(
            ai_rows,
            {},
            {
                "prohibited_decisions": [
                    {"unit_key": "region:浦东片区", "issue_id": 6}
                ]
            },
        )
        self.assertEqual(selected[0]["issue_id"], 6)
        self.assertEqual(selected[0]["selection_source"], "ai")

    def test_ppt_quality_table_preserves_zero_values(self):
        builder = InspectionReportPresentation("quality_measurement", {}, ".")
        slide = builder._quality_blank_slide("零值显示测试")
        table = builder._quality_table(
            slide,
            ["检查油库数量", "违规违纪问题"],
            [[0, 0]],
            0.8,
            1.5,
            5,
            1.2,
        )
        self.assertEqual(table.cell(1, 0).text, "0")
        self.assertEqual(table.cell(1, 1).text, "0")


if __name__ == "__main__":
    unittest.main()
