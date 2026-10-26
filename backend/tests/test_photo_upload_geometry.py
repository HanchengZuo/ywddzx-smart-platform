from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw
from werkzeug.datastructures import FileStorage
import app as api


class PhotoUploadGeometryTests(unittest.TestCase):
    def test_issue_and_review_storage_preserve_aspect_and_four_corners(self):
        with tempfile.TemporaryDirectory() as root, patch.multiple(
            api, STORAGE_ROOT=root, ISSUES_STORAGE_DIR=str(Path(root) / 'issues'),
            RECTIFICATIONS_STORAGE_DIR=str(Path(root) / 'rectifications'),
        ), patch('app.get_db_connection', side_effect=AssertionError('No database access in photo test')):
            for category in ('issues', 'rectifications'):
                for width, height in ((2400, 200), (300, 2400), (1200, 800)):
                    with self.subTest(category=category, size=(width, height)):
                        image = Image.new('RGB', (width, height), 'white')
                        draw = ImageDraw.Draw(image)
                        colors = [(255,0,0), (0,255,0), (0,0,255), (255,0,255)]
                        corners = [(0,0), (width*.8,0), (0,height*.8), (width*.8,height*.8)]
                        for color, (x,y) in zip(colors, corners):
                            draw.rectangle((int(x),int(y),int(x+width*.2),int(y+height*.2)), fill=color)
                        data = BytesIO()
                        image.save(data, format='PNG')
                        data.seek(0)
                        relative = api.save_uploaded_file(FileStorage(data, filename='test.png', content_type='image/png'), category)
                        path = Path(root) / relative.lstrip('/')
                        self.assertTrue(path.is_relative_to(root))
                        with Image.open(path) as saved:
                            expected_width = min(1600, width)
                            self.assertEqual(saved.size, (expected_width, max(1,int(height*expected_width/width))))
                            for color, (x,y) in zip(colors, ((.1,.1),(.9,.1),(.1,.9),(.9,.9))):
                                pixel = saved.getpixel((int(saved.width*x),int(saved.height*y)))
                                self.assertTrue(all(abs(a-b)<35 for a,b in zip(pixel,color)), (pixel,color))
