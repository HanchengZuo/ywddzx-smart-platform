import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app import normalize_issue_export_options, write_issue_export_xlsx


class IssueExportEmbeddedImageTests(unittest.TestCase):
    def test_issue_photos_are_embedded_in_cells_instead_of_floating(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_root = Path(temp_dir)
            image_path = storage_root / "issue.png"
            Image.new("RGB", (160, 90), "#d9483b").save(image_path)

            export_options = normalize_issue_export_options(
                {
                    "include_fields": {
                        "id": True,
                        "description": True,
                        "issue_photo": True,
                        "rectification_photo": True,
                        "review_photo": True,
                    },
                    "include_photos": {
                        "issue_photo": True,
                        "rectification_photo": True,
                        "review_photo": True,
                    },
                }
            )
            rows = [
                {
                    "id": 17,
                    "inspection_table_id": 3,
                    "inspection_table_name": "测试检查表",
                    "description": "=SUM(1,1)",
                    "issue_photo": "/issue.png",
                    "rectification_photo": "/issue.png",
                    "review_photo": "/issue.png",
                },
                {
                    "id": 18,
                    "inspection_table_id": 4,
                    "inspection_table_name": "测试检查表",
                    "description": "第二张同名检查表",
                    "issue_photo": "/issue.png",
                    "rectification_photo": "/issue.png",
                    "review_photo": "/issue.png",
                },
            ]
            output = BytesIO()

            with patch("app.STORAGE_ROOT", str(storage_root)):
                write_issue_export_xlsx(output, rows, export_options, {})

            output.seek(0)
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
                sheet_xml = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
                second_sheet_xml = archive.read("xl/worksheets/sheet2.xml").decode("utf-8")

            self.assertIn("xl/richData/rdrichvalue.xml", names)
            self.assertIn("xl/richData/richValueRel.xml", names)
            self.assertTrue(any(name.startswith("xl/media/image") for name in names))
            self.assertFalse(any(name.startswith("xl/drawings/") for name in names))
            self.assertNotIn("<drawing", sheet_xml)
            self.assertNotIn("<drawing", second_sheet_xml)
            self.assertEqual(sheet_xml.count(' t="e" vm="'), 3)
            self.assertEqual(second_sheet_xml.count(' t="e" vm="'), 3)
            self.assertNotIn("<f>", sheet_xml)


if __name__ == "__main__":
    unittest.main()
