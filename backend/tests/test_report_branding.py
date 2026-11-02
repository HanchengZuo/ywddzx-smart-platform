"""Native logo coverage across six renderers, without AI or production writes."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.util import Inches

from report_branding import LOGO_FILE, LEGACY_LOGO_DIGESTS, apply_report_branding
from report_presentation import InspectionReportPresentation
from tests.test_non_oil_report_presentation import NonOilReportPresentationTest


def pictures(shapes):
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from pictures(shape.shapes)
        elif shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            yield shape


def deck_images(prs):
    return [shape for owner in owners(prs) for shape in pictures(owner.shapes)]


def owners(prs):
    return [*prs.slide_masters, *[layout for master in prs.slide_masters for layout in master.slide_layouts], *prs.slides]


class ReportBrandingTests(unittest.TestCase):
    def assert_branding(self, prs, expected=True):
        digest = hashlib.sha256(LOGO_FILE.read_bytes()).hexdigest()
        found = []
        for shape in deck_images(prs):
            value = hashlib.sha256(shape.image.blob).hexdigest()
            self.assertNotIn(value, LEGACY_LOGO_DIGESTS)
            if value == digest:
                found.append(shape)
                self.assertAlmostEqual(shape.width/shape.height, 1, places=5)
                self.assertEqual((shape.crop_top, shape.crop_bottom, shape.crop_left, shape.crop_right), (0, 0, 0, 0))
        self.assertEqual(bool(found), expected)

    def test_template_replacement_includes_masters_layouts_wordmarks_and_is_idempotent(self):
        for name in ['safety_report_template/template.pptx', 'equipment_report_template/template.pptx',
                     'non_oil_report_template/non_oil_report_template.pptx', 'service_report_template/template.pptx']:
            with self.subTest(template=name):
                prs = Presentation(Path(__file__).parents[1]/'assets'/name)
                originals = {hashlib.sha256(s.image.blob).hexdigest(): s.image.blob for s in deck_images(prs)}
                self.assertTrue(apply_report_branding(prs))
                self.assert_branding(prs)
                before = [str(o._element.xml) for o in owners(prs)]
                self.assertFalse(apply_report_branding(prs))
                self.assertEqual(before, [str(o._element.xml) for o in owners(prs)])
                surviving = {hashlib.sha256(s.image.blob).hexdigest(): s.image.blob for s in deck_images(prs)}
                for digest, blob in originals.items():
                    if digest not in LEGACY_LOGO_DIGESTS:
                        self.assertEqual(surviving[digest], blob, 'photos and decorative artwork must remain unchanged')
                with tempfile.TemporaryDirectory() as root:
                    path = Path(root)/'deck.pptx'; prs.save(path)
                    restored = Presentation(path)
                    self.assert_branding(restored)
                    for part in restored.part.package.iter_parts():
                        if str(part.partname).startswith('/ppt/media/'):
                            self.assertNotIn(hashlib.sha256(part.blob).hexdigest(), LEGACY_LOGO_DIGESTS)

    def test_quality_cover_headers_and_ending_share_new_logo_and_centerline(self):
        builder = InspectionReportPresentation('quality_measurement', {}, '.')
        builder._render_quality_cover({'title': '质量计量监督检查报告', 'period_label': '2026年10月'})
        builder._quality_blank_slide('一、总体情况')
        builder._render_quality_ending({'title': '通报完毕'})
        self.assert_branding(builder.prs)
        first = next(pictures(builder.prs.slides[0].shapes))
        self.assertLess(first.left, Inches(1))
        header = next(pictures(builder.prs.slides[1].shapes))
        self.assertGreater(header.left, Inches(12))
        last = builder.prs.slides[-1]
        logo = next(s for s in pictures(last.shapes) if s.top > Inches(2))
        label = next(s for s in last.shapes if s.has_text_frame and s.text == '通报完毕')
        for shape in (logo, label):
            self.assertAlmostEqual(shape.left+shape.width/2, builder.prs.slide_width/2, delta=1)
        self.assertLess(logo.top+logo.height, label.top)

    def test_all_six_cached_artifacts_and_exported_previews_use_same_branded_bytes(self):
        from report_ppt_artifacts import build_artifact, attach_export
        from tests.test_safety_report import fixture_report as safety_fixture
        from tests.test_service_report import fixture_report as service_fixture
        # Check financial decks independently: they have no original petroleum mark.
        with tempfile.TemporaryDirectory() as root:
            for kind in ('quality_measurement', 'safety_quality', 'finance', 'on_site_service', 'equipment_facilities', 'non_oil'):
                report = safety_fixture() if kind == 'safety_quality' else service_fixture() if kind == 'on_site_service' else NonOilReportPresentationTest().make_report()
                if kind == 'quality_measurement':
                    report['slides'] = [{'kind': 'cover', 'title': '质量计量监督检查报告'},
                        {'kind': 'agenda'}, {'kind': 'ending', 'title': '通报完毕'}]
                with self.subTest(kind=kind):
                    def renderer(path, directory):
                        self.assert_branding(Presentation(path), expected=kind != 'finance')
                        files = []
                        for i in range(len(Presentation(path).slides)):
                            target = Path(directory)/f'slide-{i+1:02d}.jpg'; target.write_bytes(b'test-preview'); files.append(str(target))
                        return files
                    with patch('non_oil_report_presentation._render_presentation_preview', side_effect=renderer):
                        directory, manifest = build_artifact(kind, report, root)
                        exported = Path(root)/(kind+'.pptx')
                        attach_export(directory, manifest, exported)
                        self.assertEqual(exported.read_bytes(), (directory/'report.pptx').read_bytes())
                        self.assertEqual(hashlib.sha256(exported.read_bytes()).hexdigest(), manifest['sha256'])

    def test_saved_non_oil_copy_rebrands_without_changing_source_and_can_be_reused(self):
        from non_oil_report_presentation import TEMPLATE_FILE, copy_existing_non_oil_presentation
        from pptx_compatibility import COMPATIBILITY_VERSION
        with tempfile.TemporaryDirectory() as root:
            source = Path(root)/'saved.pptx'
            original = Presentation(TEMPLATE_FILE); original.core_properties.version = COMPATIBILITY_VERSION; original.save(source)
            before = source.read_bytes()
            report = {'presentation': {'ppt_path': 'saved.pptx', 'slide_count': 45}}
            output = Path(root)/'export.pptx'
            copy_existing_non_oil_presentation(report, output, root)
            self.assertEqual(source.read_bytes(), before)
            self.assert_branding(Presentation(output))
            second = Path(root)/'second.pptx'
            copy_existing_non_oil_presentation({'presentation': {'ppt_path': str(output)}}, second, root)
            self.assertEqual(output.read_bytes(), second.read_bytes())

    def test_all_cache_keys_change_with_brand_asset_version_without_changing_reports(self):
        from report_ppt_artifacts import artifact_key
        report = {'month': '2026-10'}
        with tempfile.TemporaryDirectory() as root:
            for kind in ('quality_measurement', 'safety_quality', 'finance', 'on_site_service', 'equipment_facilities', 'non_oil'):
                first = artifact_key(kind, report, root)
                with patch('report_branding.BRANDING_VERSION', 'another-logo'):
                    self.assertNotEqual(first, artifact_key(kind, report, root))
        self.assertEqual(report, {'month': '2026-10'})

    def test_completed_exports_without_current_branding_are_not_reused(self):
        from report_branding import branding_key
        from report_ppt_artifacts import (COMPATIBILITY_VERSION, FONT_ENVIRONMENT,
            _read_artifact, export_preview_manifest)
        with tempfile.TemporaryDirectory() as root:
            key = 'a'*64
            directory = Path(root)/'report_presentations'/('compatible-'+key)
            directory.mkdir(parents=True)
            (directory/'report.pptx').write_bytes(b'saved-pptx')
            (directory/'slide-01.jpg').write_bytes(b'saved-preview')
            path = Path(root)/'export.pptx'
            path.write_bytes(b'saved-pptx')
            manifest = {'version':COMPATIBILITY_VERSION, 'fonts':FONT_ENVIRONMENT,
                'artifact_key':key, 'slide_count':1}
            for brand in (None, 'old-brand', branding_key()):
                if brand is not None:
                    manifest['branding'] = brand
                (directory/'manifest.json').write_text(json.dumps(manifest))
                path.with_suffix('.preview.json').write_text(json.dumps(manifest))
                expected = brand == branding_key()
                self.assertEqual(bool(_read_artifact(directory)), expected)
                # Existing task serialization and preview URLs do not supply a report.
                self.assertEqual(bool(export_preview_manifest(path, root)), expected)
