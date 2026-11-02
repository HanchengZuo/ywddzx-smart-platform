"""Chapter-three scopes and chart workbooks, using isolated fixture reports, no paid AI."""

from pathlib import Path
import tempfile
import unittest
from pptx import Presentation
from safety_problem_analysis import problem_analysis
from safety_report_presentation import build_safety_presentation, SLIDE_ORDER
from safety_template_styles import editable_plot
from tests.test_safety_report import fixture_report, raw_issue


def report_fixture():
    rows = []
    for i in range(1, 9):
        topic = "设备设施" if i <= 5 else "污染防治"
        content = ("油罐操作井" if i <= 3 else "配发电") if i <= 5 else "环保设施"
        rows.append(
            raw_issue(i, standard_detail_text=f"检查主题：{topic}\n检查内容：{content}")
        )
    # Other hazards have more video issues but are NOT a fixed report category.
    for start, count, name in [
        (20, 6, "设备维修作业"),
        (30, 4, "卸油作业"),
        (40, 2, "现场加油作业"),
        (50, 1, "油品质量控制"),
        (60, 9, "其他"),
    ]:
        for i in range(start, start + count):
            rows.append(raw_issue(i, "video", standard_detail_text=f"检查内容：{name}"))
    result = fixture_report(rows=rows)
    result["safety_analysis"]["video:设备维修作业"].update(
        groups=[
            {"name": "消防隔离不到位", "issue_ids": [20, 21, 22, 23]},
            {"name": "作业着装不规范", "issue_ids": [24, 25]},
        ],
        causes=["检修原因。"],
    )
    result["safety_analysis"]["video:卸油作业"].update(
        groups=[
            {"name": "管线连接顺序不规范", "issue_ids": [30, 31, 32]},
            {"name": "卸油应急准备不足", "issue_ids": [33]},
        ],
        causes=["卸油原因"],
    )
    result["safety_analysis"]["onsite:设备设施"]["causes"] = ["设施维护原因。"]
    return result


class KeyProblemAnalysisTest(unittest.TestCase):
    def test_onsite_top_fixed_topic_uses_only_its_inspection_contents(self):
        report = report_fixture()
        value = problem_analysis(report, "onsite")
        self.assertEqual(len(value["blocks"]), 1)
        block = value["blocks"][0]
        self.assertEqual((block["name"], block["count"]), ("设备设施", 5))
        self.assertEqual(block["issue_ids"], [1, 2, 3, 4, 5])
        self.assertEqual(
            [(r["name"], r["count"], r["percentage"]) for r in block["distribution"]],
            [("油罐操作井", 3, 60), ("配发电", 2, 40)],
        )
        self.assertNotIn("环保设施", value["narrative"])
        self.assertIn("设备设施类5项问题", value["heading"])
        self.assertEqual(value["causes"], ["设施维护原因"])

    def test_video_top_two_fixed_categories_use_manual_effective_subgroups_and_semicolon(
        self,
    ):
        report = report_fixture()
        value = problem_analysis(report, "video")
        self.assertEqual(
            [b["name"] for b in value["blocks"]], ["设备维修作业", "卸油作业"]
        )
        self.assertEqual([b["count"] for b in value["blocks"]], [6, 4])
        self.assertEqual(
            [[r["count"] for r in b["distribution"]] for b in value["blocks"]],
            [[4, 2], [3, 1]],
        )
        self.assertIn("；卸油作业类问题主要集中在", value["narrative"])
        self.assertNotIn("其他隐患", value["narrative"])
        self.assertEqual(value["causes"], ["检修原因", "卸油原因"])
        report["safety_analysis"]["video:卸油作业"]["groups"][0][
            "name"
        ] = "人工调整后的表现"
        self.assertIn(
            "人工调整后的表现", problem_analysis(report, "video")["narrative"]
        )

    def test_ties_use_fixed_order_and_risk_category_merges_its_two_topics(self):
        report = report_fixture()
        report["safety_issues"] = [
            dict(
                report["safety_issues"][0],
                issue_id=i,
                topic="风险隐患" if i < 4 else "合规性管理",
            )
            for i in range(1, 6)
        ]
        self.assertEqual(
            problem_analysis(report, "onsite")["blocks"][0]["name"], "风险合规"
        )
        report["safety_issues"] = [
            dict(report["safety_issues"][0], issue_id=i, topic=topic)
            for i, topic in enumerate(["污染防治", "设备设施"])
        ]
        self.assertEqual(
            problem_analysis(report, "onsite")["blocks"][0]["name"], "设备设施"
        )

    def test_incomplete_subgroups_never_use_wrong_whole_mode_distribution(self):
        report = report_fixture()
        report["safety_analysis"]["video:卸油作业"]["groups"] = []
        value = problem_analysis(report, "video")
        self.assertEqual(value["blocks"][1]["distribution"], [])
        self.assertIn("暂无已确认", value["narrative"])
        report["safety_analysis"]["video:卸油作业"]["groups"] = [
            {"name": "重复", "issue_ids": [30, 30]}
        ]
        with self.assertRaises(ValueError):
            problem_analysis(report, "video")

    def test_stacked_charts_have_independent_editable_workbooks_and_correct_totals(
        self,
    ):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "safety.pptx"
            report = report_fixture()
            build_safety_presentation(report, output, root)
            prs = Presentation(output)
            self.assertEqual(len(prs.slides), 31)
            for source_index, values in [(10, [[3, 2]]), (11, [[4, 2], [3, 1]])]:
                slide = prs.slides[SLIDE_ORDER.index(source_index)]
                charts = [s for s in slide.shapes if s.has_chart]
                self.assertEqual(len(charts), len(values))
                for graph, counts in zip(charts, values):
                    with editable_plot(graph.chart):
                        self.assertEqual(list(graph.chart.series[0].values), counts)
                    self.assertTrue(graph.chart._chartSpace.xpath(".//c:pie3DChart"))
                    self.assertIsNotNone(graph.chart.part.chart_workbook.xlsx_part)
                if len(charts) == 2:
                    self.assertLess(charts[0].top + charts[0].height, charts[1].top)
                    self.assertIsNot(charts[0].chart.part, charts[1].chart.part)
                    self.assertIsNot(
                        charts[0].chart.part.chart_workbook.xlsx_part,
                        charts[1].chart.part.chart_workbook.xlsx_part,
                    )
                text = next(
                    s for s in slide.shapes if s.name == "safety-key-problem-text"
                )
                self.assertTrue(text.text.startswith("占比较高问题分析"))
                self.assertEqual(len(text._element.xpath('.//a:buChar[@char="■"]')), 2)
                self.assertEqual(len(text._element.xpath('.//a:buChar[@char="□"]')), 1)
                self.assertFalse(
                    text._element.xpath('.//a:buFont[@typeface="Wingdings"]')
                )
                for p in text.text_frame.paragraphs:
                    if p.text.startswith("（"):
                        self.assertTrue(p.text.endswith("。"))
                for shape in slide.shapes:
                    self.assertGreaterEqual(shape.top, 0)
                    self.assertLessEqual(shape.top + shape.height, prs.slide_height)
                    self.assertLessEqual(shape.left + shape.width, prs.slide_width)

    def test_zero_or_one_video_category_keeps_correct_chart_count(self):
        for count in [0, 1]:
            report = report_fixture()
            report["safety_issues"] = [
                r
                for r in report["safety_issues"]
                if count and r["mode"] == "video" and r["topic"] == "设备维修作业"
            ]
            with tempfile.TemporaryDirectory() as root:
                output = Path(root) / "safety.pptx"
                build_safety_presentation(report, output, root)
                slide = Presentation(output).slides[SLIDE_ORDER.index(11)]
                self.assertEqual(sum(s.has_chart for s in slide.shapes), 1)
            self.assertEqual(len(problem_analysis(report, "video")["blocks"]), count)

    def test_dense_stacked_legends_retain_every_percentage_without_overlapping_callouts(
        self,
    ):
        report = report_fixture()
        base = next(r for r in report["safety_issues"] if r["mode"] == "video")
        report["safety_issues"] = []
        for offset, category in [(100, "设备维修作业"), (200, "卸油作业")]:
            rows = [
                dict(base, issue_id=offset + i, topic=category, category_name=category)
                for i in range(10)
            ]
            report["safety_issues"].extend(rows)
            report["safety_analysis"]["video:" + category]["groups"] = [
                {"name": f"缺陷表现{i+1}", "issue_ids": [r["issue_id"]]}
                for i, r in enumerate(rows)
            ]
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "dense.pptx"
            build_safety_presentation(report, path, root)
            prs = Presentation(path)
            slide = prs.slides[SLIDE_ORDER.index(11)]
            labels = [s for s in slide.shapes if s.name == "safety-pie-label"]
            self.assertEqual(len(labels), 20)
            self.assertTrue(all("10.00%" in s.text for s in labels))
            self.assertFalse(
                any(s.name.startswith("safety-pie-percentage-") for s in slide.shapes)
            )
            for s in slide.shapes:
                self.assertLessEqual(s.top + s.height, prs.slide_height)
