import unittest
from datetime import date

from app import (
    build_quality_measurement_report_payload,
    build_quality_measurement_report_slides,
    build_report_deep_analysis,
    build_report_flow_highlights,
)


def make_issue(issue_id, flow="人员管理", prohibited=False):
    return {
        "id": issue_id,
        "station_id": issue_id % 4 + 1,
        "station_name": f"测试站点{issue_id % 4 + 1}",
        "region": "浦东片区",
        "table_name": "计量稽查检查表（现场）",
        "standard_detail_text": (
            f"业务流程：{flow}\n是否禁止项：{'是' if prohibited else '否'}"
        ),
        "description": f"第{issue_id}条测试问题描述",
        "issue_photo": "",
        "is_excellent": False,
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
            date(2026, 7, 1), rows, distribution, None
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


if __name__ == "__main__":
    unittest.main()
