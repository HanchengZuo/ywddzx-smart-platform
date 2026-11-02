"""Regression coverage for the five reference-0804 page styles; no AI calls."""
import base64
import copy
import json
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn
from pptx.util import Inches

from quality_report_styles import RENDERER_VERSION, _lines
from report_presentation import InspectionReportPresentation


def samples():
    return [
        {'kind': 'finding_overview', 'title_prefix': '二、检查发现-', 'title_accent': '发现问题',
         'text_blocks': [{'runs': [{'text': '本次检查发现问题54项：'}]},
             {'runs': [{'text': '　　油站环节54项：', 'tone': 'blue'}, {'text': '涉及人员管理、器具管理等问题。', 'tone': 'red'}]},
             {'runs': [{'text': '　　油库环节X项：', 'tone': 'blue'}, {'text': '油库发油系统类问题。'}]},
             {'runs': [{'text': '　　运输环节X项：', 'tone': 'blue'}, {'text': '车辆铅封核对问题。'}]}],
         'rows': [{'sequence': 1, 'section': '油站环节', 'problem_type': '器具管理', 'count': 0, 'percentage': ''},
                  {'sequence': '合计', 'section': '/', 'problem_type': '/', 'count': 54, 'percentage': ''}]},
        {'kind': 'prohibited', 'subtitle': '1.禁止项问题（2/2）',
         'narrative': '本次检查发现涉及禁止项问题15项，其中油库环节X项、运输环节X项、油站环节15项。',
         'rows': [{'sequence': i, 'unit_name': '浦东片区', 'description': '未按规定核对铅封号。'*8, 'penalty': ''} for i in range(7, 13)]},
        {'kind': 'management_trace', 'title': '三、管理追溯', 'ai_generated': True,
         'typical_issue': {'station_name': '测试加油站', 'description': '加油机显示屏出现断点。'},
         'analysis_items': [{'label': f'（{i}）{level}层面', 'content': '日常检查及维修跟踪需要完善。'}
                            for i, level in enumerate(['执行', '监督', '管理'], 1)]},
        {'kind': 'trace_analysis', 'title': '三、管理追溯', 'ai_generated': True,
         'conclusion': '综上所述：需完善计量器具巡检与维护管理。',
         'improvement_measures': [{'level': level+'层面', 'content': '开展专项巡检并跟进维修。'} for level in ['管理', '监督', '执行']]},
        {'kind': 'work_plan', 'title': '四、工作计划', 'ai_generated': True,
         'items': [{'title': '开展专项巡检'+str(i), 'content': '核查问题并持续跟进整改结果。'*3} for i in range(1, 5)]},
    ]


class QualityTemplateStyleTests(unittest.TestCase):
    def build(self, data=None):
        report = {'slides': copy.deepcopy(data or samples())}
        before = copy.deepcopy(report)
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'report.pptx'
            InspectionReportPresentation('quality_measurement', report, root).build(path)
            prs = Presentation(path)
        self.assertEqual(report, before)
        return prs

    def test_only_requested_five_kinds_have_native_shapes_without_ai_badges(self):
        prs = self.build()
        self.assertEqual(len(prs.slides), 5)
        for slide in prs.slides:
            values = ''.join(s.text for s in slide.shapes if s.has_text_frame)
            self.assertNotIn('AI生成内容', values)
            for s in slide.shapes:
                self.assertLessEqual(s.left+s.width, prs.slide_width+Inches(.01))
                self.assertLessEqual(s.top+s.height, prs.slide_height)
                if s.has_text_frame:
                    for p in s.text_frame.paragraphs:
                        for r in p.runs:
                            self.assertIn(r.font.name or p.font.name, ('Microsoft YaHei', 'SimSun'))

    def test_both_tables_have_explicit_black_half_point_solid_edges_after_save(self):
        for slide in list(self.build().slides)[:2]:
            shape = next(s for s in slide.shapes if s.has_table)
            for row in shape.table.rows:
                for cell in row.cells:
                    for edge in ('lnL', 'lnR', 'lnT', 'lnB'):
                        line = cell._tc.tcPr.find(qn('a:'+edge))
                        self.assertEqual(line.get('w'), '6350')
                        self.assertEqual(line.find(qn('a:prstDash')).get('val'), 'solid')
                        self.assertEqual(line.find(qn('a:solidFill'))[0].get('val'), '000000')
            self.assertEqual(str(shape.table.cell(0, 0).fill.fore_color.rgb), '88E4F6')
            self.assertFalse(shape.table.cell(0, 0).text_frame.paragraphs[0].font.bold)

    def test_finding_geometry_sizes_indents_zero_and_blank_percentages_follow_reference(self):
        slide = self.build().slides[0]
        narrative = next(s for s in slide.shapes if s.name == 'quality-finding-narrative')
        self.assertAlmostEqual(narrative.left/Inches(1), .7424, places=4)
        self.assertAlmostEqual(narrative.width/Inches(1), 6.4792, places=4)
        for index, p in enumerate(narrative.text_frame.paragraphs):
            self.assertEqual(p.line_spacing, 1.5)
            self.assertEqual(int(p._p.pPr.get('indent')), Inches(.59375) if index else 0)
            self.assertTrue(all(r.font.size.pt == 20 and r.font.bold for r in p.runs))
        shape = next(s for s in slide.shapes if s.has_table)
        self.assertAlmostEqual(shape.left/Inches(1), 7.6812, places=4)
        self.assertAlmostEqual(shape.top/Inches(1), 1.2114, places=4)
        self.assertEqual(shape.table.cell(1, 3).text, '0')
        self.assertEqual(shape.table.cell(1, 4).text, '')

    def test_prohibited_numbering_rich_colors_and_table_do_not_overlap(self):
        slide = self.build().slides[1]
        narrative = next(s for s in slide.shapes if s.name == 'quality-prohibited-narrative')
        table = next(s for s in slide.shapes if s.has_table)
        self.assertLess(narrative.top+narrative.height, table.top)
        self.assertEqual([r.cells[0].text for r in list(table.table.rows)[1:]], list(map(str, range(7, 13))))
        runs = narrative.text_frame.paragraphs[0].runs
        self.assertTrue(any(r.text == '15项' and str(r.font.color.rgb) == 'FF0000' for r in runs))
        self.assertTrue(any(r.text == '油库环节X项' and str(r.font.color.rgb) == '2E75B6' for r in runs))
        self.assertTrue(all(r.font.size.pt == 20 for r in runs))

    def test_trace_labels_are_inline_and_conclusion_and_work_plan_use_template_paragraphs(self):
        prs = self.build()
        for index in (2, 3):
            band = next(s for s in prs.slides[index].shapes if s.name == 'quality-band')
            self.assertEqual(band.left, 0)
            self.assertAlmostEqual(band.width/Inches(1), 8.3104, places=4)
        causes = next(s for s in prs.slides[2].shapes if s.name == 'quality-trace-causes')
        self.assertEqual(len(causes.text_frame.paragraphs), 3)
        self.assertEqual(str(causes.text_frame.paragraphs[0].runs[0].font.color.rgb), '4472C4')
        self.assertIn('（1）执行层面：', causes.text)
        conclusion = next(s for s in prs.slides[3].shapes if s.name == 'quality-trace-conclusion')
        self.assertEqual(conclusion.text.count('综上所述：'), 1)
        self.assertIn('改进措施：', conclusion.text)
        plan = next(s for s in prs.slides[4].shapes if s.name == 'quality-work-plan')
        self.assertEqual(len(plan.text_frame.paragraphs), 8)
        for p in plan.text_frame.paragraphs:
            self.assertEqual(int(p._p.pPr.get('indent')), Inches(.5))
            self.assertTrue(all(r.font.size.pt == 18 and r.font.bold for r in p.runs))

    def test_trace_photo_is_uncropped_inside_reference_right_hand_slot(self):
        for size in [(2400, 400), (400, 2400)]:
            data = samples()
            image = BytesIO(); Image.new('RGB', size, 'white').save(image, format='PNG')
            data[2]['typical_issue']['issue_photo'] = 'data:image/png;base64,'+base64.b64encode(image.getvalue()).decode()
            slide = self.build(data).slides[2]
            picture = next(s for s in slide.shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE and s.top > Inches(1))
            self.assertGreaterEqual(picture.left, Inches(8.7958))
            self.assertLessEqual(picture.left+picture.width, Inches(13.0798))
            self.assertLessEqual(picture.top+picture.height, Inches(6.7806))
            self.assertAlmostEqual(picture.width/picture.height, size[0]/size[1], places=4)
            self.assertEqual((picture.crop_left, picture.crop_top, picture.crop_right, picture.crop_bottom), (0, 0, 0, 0))

    def test_long_analysis_fits_complete_text_in_fixed_template_area(self):
        data = samples()
        for row in data[2]['analysis_items']:
            row['content'] = '持续核实计量器具维护情况并跟进问题整改。'*8
        slide = self.build(data).slides[2]
        shape = next(s for s in slide.shapes if s.name == 'quality-trace-causes')
        required = 0
        for p in shape.text_frame.paragraphs:
            size = p.runs[0].font.size.pt
            required += _lines(p.text, shape.width/Inches(1)-.2, size)*size*1.5/72
        self.assertLessEqual(required, shape.height/Inches(1)-.1)
        for item in data[2]['analysis_items']:
            self.assertIn(item['content'], shape.text)

    def test_renderer_cache_upgrade_only_changes_quality_keys_and_rejects_old_exports(self):
        from report_ppt_artifacts import artifact_key, _current_renderer
        with tempfile.TemporaryDirectory() as root:
            for kind in ['quality_measurement', 'finance', 'non_oil', 'safety_quality', 'equipment_facilities', 'on_site_service']:
                first = artifact_key(kind, {}, root)
                with patch('quality_report_styles.RENDERER_VERSION', 'old-quality-style'):
                    self.assertEqual(first == artifact_key(kind, {}, root), kind != 'quality_measurement')
        self.assertFalse(_current_renderer({}, 'quality_measurement'))
        self.assertFalse(_current_renderer({'quality_renderer': 'old'}, 'quality_measurement'))
        self.assertTrue(_current_renderer({'quality_renderer': RENDERER_VERSION}, 'quality_measurement'))
        self.assertTrue(_current_renderer({}, 'finance'))

    def test_old_completed_export_task_is_rejected_even_without_loading_report_payload(self):
        from report_branding import branding_key
        from report_ppt_artifacts import (COMPATIBILITY_VERSION, FONT_ENVIRONMENT,
            export_preview_manifest, preview_slide_path)
        with tempfile.TemporaryDirectory() as root:
            key = 'a'*64
            directory = Path(root)/'report_presentations'/('compatible-'+key)
            directory.mkdir(parents=True)
            (directory/'report.pptx').write_bytes(b'fixture')
            (directory/'slide-01.jpg').write_bytes(b'fixture')
            target = Path(root)/'export.pptx'; target.write_bytes(b'fixture')
            manifest = {'version': COMPATIBILITY_VERSION, 'fonts': FONT_ENVIRONMENT,
                'branding': branding_key(), 'artifact_key': key, 'slide_count': 1}
            def write():
                (directory/'manifest.json').write_text(json.dumps(manifest))
                target.with_suffix('.preview.json').write_text(json.dumps(manifest))
            write()
            self.assertIsNone(export_preview_manifest(target, root, report_type='quality_measurement'))
            self.assertIsNone(preview_slide_path(target, root, 1, report_type='quality_measurement'))
            self.assertIsNotNone(export_preview_manifest(target, root, report_type='finance'))
            manifest.update(report_type='quality_measurement', quality_renderer=RENDERER_VERSION)
            write()
            self.assertIsNotNone(export_preview_manifest(target, root, report_type='quality_measurement'))
            self.assertIsNotNone(preview_slide_path(target, root, 1, report_type='quality_measurement'))
