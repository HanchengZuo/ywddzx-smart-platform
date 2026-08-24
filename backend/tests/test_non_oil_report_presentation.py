import tempfile
import unittest
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from ai_prompts import (
    build_non_oil_category_classification_prompt,
    build_non_oil_report_insight_prompt,
)
from non_oil_report_presentation import (
    CANVAS_SIZE,
    build_non_oil_template_presentation,
    copy_existing_non_oil_presentation,
)


class NonOilReportPresentationTest(unittest.TestCase):
    def make_report(self):
        categories = [
            {"name": "店销商品摆放情况", "count": 3},
            {"name": "便利店卫生情况", "count": 2},
        ]
        return {
            "month": "2026-07",
            "period_text": "7月巡检，2026年6月25日-2026年7月24日",
            "scope_text": "7月非油现场抽检2座站点，涉及1个管理片区。",
            "unit_overview_text": "本次非油巡检共发现5项问题。",
            "summary": {"total_issue_count": 5, "category_count": 2},
            "previous_month_rectification": {"narrative": "上期暂无待整改问题。", "units": []},
            "category_distribution": categories,
            "key_issue_count": 2,
            "key_issue_percentage": 40,
            "units": [
                {
                    "unit_type": "region",
                    "unit_name": "浦东",
                    "station_count": 2,
                    "station_names": ["测试一站", "测试二站"],
                    "issue_count": 5,
                    "average_issue_count": 2.5,
                    "percentage": 100,
                    "category_distribution": categories,
                    "station_issue_rows": [
                        {
                            "station_name": "测试一站",
                            "issue_count": 3,
                            "category_counts": {"店销商品摆放情况": 2, "便利店卫生情况": 1},
                        },
                        {
                            "station_name": "测试二站",
                            "issue_count": 2,
                            "category_counts": {"店销商品摆放情况": 1, "便利店卫生情况": 1},
                        },
                    ],
                }
            ],
        }

    def test_ai_prompts_remain_independent_and_complete(self):
        insight_prompt = build_non_oil_report_insight_prompt({"issues": [{"issue_id": 7}]})
        classification_prompt = build_non_oil_category_classification_prompt(
            {"allowed_categories": ["便利店卫生情况"], "issues": [{"issue_id": 7}]}
        )
        self.assertIn("typical_issues", insight_prompt)
        self.assertIn("attribution_analysis", insight_prompt)
        self.assertIn("classifications", classification_prompt)
        self.assertIn("不能输出‘其他’", classification_prompt)

    def test_preview_images_and_export_share_the_same_slide_set(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            slides_dir = root / "report_presentations" / "task-1"
            ppt_path = slides_dir / "report.pptx"
            result = build_non_oil_template_presentation(
                self.make_report(),
                slides_dir,
                ppt_path,
            )
            self.assertEqual(result["slide_count"], 35)
            self.assertEqual(len(list(slides_dir.glob("slide-*.jpg"))), 35)
            with Image.open(slides_dir / "slide-01.jpg") as image:
                self.assertEqual(image.size, CANVAS_SIZE)
            presentation = Presentation(ppt_path)
            self.assertEqual(len(presentation.slides), result["slide_count"])
            self.assertTrue(
                any(shape.has_text_frame for shape in presentation.slides[0].shapes)
            )
            self.assertTrue(
                any(shape.has_table for shape in presentation.slides[4].shapes)
            )
            self.assertGreaterEqual(
                sum(
                    shape.shape_type == MSO_SHAPE_TYPE.CHART
                    for shape in presentation.slides[8].shapes
                ),
                2,
            )
            self.assertGreaterEqual(
                sum(
                    shape.shape_type == MSO_SHAPE_TYPE.CHART
                    for shape in presentation.slides[9].shapes
                ),
                2,
            )
            self.assertFalse(
                len(presentation.slides[0].shapes) == 1
                and presentation.slides[0].shapes[0].shape_type == MSO_SHAPE_TYPE.PICTURE
            )

            copied_path = root / "exports" / "copy.pptx"
            copied = copy_existing_non_oil_presentation(
                {
                    "presentation": {
                        "ppt_path": "report_presentations/task-1/report.pptx",
                        "slide_count": result["slide_count"],
                    }
                },
                copied_path,
                root,
            )
            self.assertEqual(copied["slide_count"], result["slide_count"])
            self.assertEqual(copied_path.read_bytes(), ppt_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
