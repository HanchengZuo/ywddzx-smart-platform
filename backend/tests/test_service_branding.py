from pathlib import Path
import tempfile
import unittest
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from service_report_presentation import build_service_presentation
from tests.test_service_report import conclusion_report, conclusion_payload


class ServiceBrandingTests(unittest.TestCase):
    def test_user_assets_keep_intrinsic_ratio_on_cover_every_body_and_inherited_headers(self):
        report = conclusion_report()
        report['service_conclusion'] = conclusion_payload([1])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'service.pptx'
            build_service_presentation(report, path, directory)
            prs = Presentation(path)
            self.assertAlmostEqual(prs.slide_width/prs.slide_height, 16/9, places=5)
            cover = next(s for s in prs.slides[0].shapes if s.name == 'service-cover-wordmark')
            self.assertAlmostEqual(cover.width/cover.height, cover.image.size[0]/cover.image.size[1], places=5)
            for slide in list(prs.slides)[1:]:
                logos = [s for s in slide.shapes if s.name == 'service-header-icon']
                self.assertEqual(len(logos), 1)
                logo = logos[0]
                self.assertAlmostEqual(logo.width/logo.height, logo.image.size[0]/logo.image.size[1], places=5)
                self.assertEqual(sum(s.name == 'service-header-brand-name' and s.text == '中国石油' for s in slide.shapes), 1)
                self.assertLessEqual(logo.left+logo.width, prs.slide_width)
            for owner in [*prs.slide_masters, *prs.slide_layouts]:
                self.assertFalse(any(s.shape_type == MSO_SHAPE_TYPE.PICTURE and s.left > 10.5*914400
                    and s.top < 1.15*914400 and s.height < 1.1*914400 for s in owner.shapes))
