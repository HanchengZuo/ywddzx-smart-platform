import copy
import importlib.util
import os
from datetime import date
from pathlib import Path
import tempfile
import unittest
import uuid
from zipfile import ZipFile
from unittest.mock import MagicMock, patch

from flask import Flask
from PIL import Image
from pptx import Presentation
from psycopg2.extras import RealDictCursor
import psycopg2
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from safety_report_data import serialize, scope, period_label, pending_at, backlog, category_rows
from safety_report_analysis import (validate_analysis, analysis_context, normalize_settings,
    effective_analysis, build_report, photo_examples, load_settings, save_settings)
from safety_report_http import register_safety_report
from safety_report_presentation import build_safety_presentation, TEMPLATE_FILE


def raw_issue(issue_id=1, mode='onsite', **extra):
    return dict(dict(id=issue_id, station_id=1, station_name='测试站', region='浦东管理片区',
        checklist_mode='online' if mode == 'video' else 'offline', standard_id='1234',
        standard_detail_text='序号：26\n检查主题：设备设施\n检查内容：油罐操作井\n评分说明：跨接及接地规范，得10分。',
        description='油罐操作井接地连接缺失', issue_photo='', audit_status='approved',
        status='待整改'), **extra)


def mock_analysis(issues, *args):
    return {'groups': [{'name': '装置维护不到位', 'summary': '接地装置连接缺失，应按规范维护。',
        'issue_ids': [row['issue_id'] for row in issues]}] if issues else [],
        'causes': ['可能存在日常检查遗漏，需核实。'] if issues else [], 'suggestions': []}


def fixture_report(photo=''):
    rows = [raw_issue(), raw_issue(2, 'video'), raw_issue(3)]
    rows[1]['standard_detail_text'] = '序号：2\n检查内容：加油站设备维修作业\n评分说明：执行检维修许可。'
    for row in rows: row['issue_photo'] = photo
    with patch('safety_report_analysis.analyze', side_effect=mock_analysis), patch(
        'safety_report_analysis.generate_analysis', return_value={'payload': {'groups': [], 'causes': [],
        'suggestions': [{'title': '强化设施维护', 'content': '开展接地连接专项检查，核实问题整改。'}]}}):
        report = build_report(date(2026, 9, 1), date(2026, 10, 1), rows, [],
            {'onsite': [{'unit_name': '浦东', 'pending_sign': 2, 'pending_rectification': 1}], 'video': []}, normalize_settings({}))
    report['summary'].update(date_from='2026-09-01', date_to='2026-09-30')
    return report


class SafetyDataTest(unittest.TestCase):
    def test_content_aliases_and_ordinal_other(self):
        from safety_report_data import ALIASES
        for prefix, alias in ALIASES:
            row = raw_issue(); row['standard_detail_text'] = '检查主题：设备设施\n检查内容：'+prefix+'。\n评分说明：第一行\n第二行\n10分：完整达标'
            value = serialize(row)
            self.assertEqual(value['category_name'], alias)
            self.assertEqual(value['requirement'], '第一行\n第二行\n10分：完整达标')
        row['standard_detail_text'] = '序号：50\n检查主题：其他对生产经营有影响的问题隐患\n评分说明：评分'
        self.assertEqual((serialize(row)['topic'], serialize(row)['category_name']), ('其他隐患类', '其他'))
        row = raw_issue(2, 'video'); row['standard_detail_text'] = '序号：13\n检查内容：原其他项目'
        self.assertEqual(serialize(row)['category_name'], '其他隐患类')

    def test_scope_separates_modes_and_counts_zero_issue_stations(self):
        visits = [dict(station_id=1, region='浦东管理片区', checklist_mode='offline'),
            dict(station_id=2, region='中油奉贤公司', checklist_mode='offline'),
            dict(station_id=3, region='宝静管理片区', checklist_mode='online')]
        value = scope([serialize(raw_issue()), serialize(raw_issue(2, 'video'))], visits, 'onsite', '9月')
        self.assertEqual((value['station_count'], value['total_issue_count'], value['average_issue_count']), (2, 1, .5))
        self.assertEqual((value['region_count'], value['holding_unit_count']), (1, 1))
        self.assertEqual(scope([], [], 'video', '')['average_issue_count'], 0)
        self.assertEqual(serialize(raw_issue(station_name='中油奉贤第一'))['unit_name'], '浦东')

    def test_dates_month_or_exact_cross_month(self):
        self.assertEqual(period_label(date(2026, 9, 4), date(2026, 10, 1)), '2026年09月')
        self.assertEqual(period_label(date(2026, 9, 1), date(2026, 11, 1)), '2026年09月01日至2026年10月31日')
        from safety_report_data import is_before
        self.assertFalse(is_before('2026-09-30T20:00:00+00:00', date(2026, 10, 1)))
        self.assertTrue(is_before('2026-09-30T15:59:59+00:00', date(2026, 10, 1)))

    def test_historical_pending_ignores_later_review_and_respects_reset(self):
        end = date(2026, 10, 1)
        row = raw_issue(); row.update(status='已闭环', audited_at='2026-09-01', station_manager_signed_at='2026-09-03')
        history = [dict(action_type='audit_changed', to_status='审核通过', created_at='2026-09-01'),
            dict(action_type='inspection_signed', to_status='站经理签名确认', created_at='2026-09-03'),
            dict(action_type='review_submitted', to_status='已闭环', created_at='2026-10-03')]
        self.assertEqual(pending_at(row, history, end), '待整改')
        history.append(dict(action_type='rectification_submitted', to_status='待复核', created_at='2026-09-20'))
        history.sort(key=lambda r: r['created_at'])
        self.assertIsNone(pending_at(row, history, end))
        history.append(dict(action_type='inspection_signed', to_status='撤销站经理签名', created_at='2026-09-25'))
        self.assertEqual(pending_at(row, [history[0], history[-1]], end), '待签名')
        self.assertEqual(backlog([row], [], end, [])['onsite'], [])
        self.assertIsNone(pending_at(dict(row, audit_status='rejected'), [], end))


class SafetyAnalysisTest(unittest.TestCase):
    def test_ai_ids_complete_unique_and_no_unrelated_refs(self):
        issues = [serialize(raw_issue())]
        valid = mock_analysis(issues)
        self.assertEqual(validate_analysis(valid, issues), valid)
        for ids in ([], [1, 1], [999]):
            invalid = copy.deepcopy(valid); invalid['groups'][0]['issue_ids'] = ids
            with self.assertRaises(ValueError): validate_analysis(invalid, issues)
        invalid = copy.deepcopy(valid); invalid['causes'] = []
        with self.assertRaises(ValueError): validate_analysis(invalid, issues)

    def test_manual_grouping_summary_overrides_ai(self):
        rows = [serialize(raw_issue())]
        value = effective_analysis(mock_analysis(rows), rows,
            {'assignments': {'1': '人工核定分类'}, 'summaries': {'人工核定分类': '人工摘要'}})
        self.assertEqual(value['groups'], [{'name': '人工核定分类', 'issue_ids': [1], 'summary': '人工摘要'}])
        rows[0]['issue_photo'] = 'issue.jpg'
        self.assertEqual(photo_examples(rows, value, 3)[0]['caption'], '人工摘要')

    def test_memory_context_stable_without_dates_or_query_order(self):
        rows = [serialize(raw_issue(2)), serialize(raw_issue())]
        self.assertEqual(analysis_context(rows, 'onsite', '设备设施'), analysis_context(list(reversed(rows)), 'onsite', '设备设施'))
        self.assertNotIn('report_date', str(analysis_context(rows, 'onsite', '设备设施')))

    def test_invalid_saved_sources_and_overrides_rejected(self):
        for raw in ({'station_ids': ['1']}, {'typical_issue_ids': {'onsite': 2}},
            {'classifications': {'onsite:设备设施': {'assignments': {'999': '错'}}}}):
            with self.assertRaises(ValueError): normalize_settings(raw, [serialize(raw_issue())], {1})

    def test_empty_report_never_calls_ai(self):
        with patch('safety_report_analysis.generate_analysis', side_effect=AssertionError('paid AI')):
            report = build_report(date(2026, 9, 1), date(2026, 10, 1), [], [], {'onsite': [], 'video': []}, normalize_settings({}))
        self.assertEqual(report['summary']['total_issue_count'], 0)


class SafetyHttpTest(unittest.TestCase):
    def setUp(self):
        self.conn = MagicMock(); self.authorize = MagicMock(return_value={'id': 7, 'real_name': '测试保存人'})
        self.permission = MagicMock(return_value=False); self.workspace = MagicMock()
        self.app = Flask(__name__)
        register_safety_report(self.app, connect=lambda: self.conn, authorize=self.authorize,
            period=lambda *a: (date(2026, 9, 1), date(2026, 10, 1)),
            fetch_inputs=lambda *a: ([raw_issue()], [], []), has_permission=self.permission,
            save_workspace=self.workspace, log_usage=MagicMock())
        self.client = self.app.test_client()

    def test_read_and_save_never_call_ai_and_preserve_server_identity(self):
        with patch('safety_report_http.load_settings', return_value={'settings': {}, 'revision': 0}), patch(
            'safety_report_http.cached_analysis', return_value={}), patch('safety_report_http.analyze', side_effect=AssertionError('AI')):
            result = self.client.get('/api/inspection-reports/safety-config').get_json()
            self.assertEqual(result['summary']['issue_count'], 1)
            with patch('safety_report_http.save_settings') as save:
                response = self.client.put('/api/inspection-reports/safety-config', json={
                    'settings': {}, 'revision': 0, 'data_signature': result['data_signature'], 'user_id': 999})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(save.call_args.args[-1]['id'], 7)
                self.workspace.assert_called_once()

    def test_no_page_permission_and_no_generation_permission(self):
        self.authorize.side_effect = PermissionError('无查看权限')
        self.assertEqual(self.client.get('/api/inspection-reports/safety-config').status_code, 403)
        self.conn.rollback.assert_called()
        self.authorize.side_effect = None
        with patch('safety_report_http.load_settings', return_value={'settings': {}, 'revision': 0}), patch('safety_report_http.analyze') as ai:
            self.assertEqual(self.client.post('/api/inspection-reports/safety-analysis', json={}).status_code, 403)
            ai.assert_not_called()

    def test_failed_save_rolls_back_and_never_touches_workspace(self):
        from report_ai_memory import fingerprint
        with patch('safety_report_http.load_settings', return_value={'settings': {}, 'revision': 0}), patch(
            'safety_report_http.save_settings', side_effect=ValueError('配置已更新')):
            response = self.client.put('/api/inspection-reports/safety-config', json={
                'settings': {}, 'revision': 0, 'data_signature': fingerprint([serialize(raw_issue())])})
        self.assertEqual(response.status_code, 400)
        self.conn.rollback.assert_called(); self.conn.commit.assert_not_called(); self.workspace.assert_not_called()


class SafetyPresentationTest(unittest.TestCase):
    def test_native_editable_static_pages_and_geometry(self):
        with tempfile.TemporaryDirectory() as root:
            Image.new('RGB', (150, 600), 'steelblue').save(Path(root)/'photo.jpg')
            report = fixture_report('photo.jpg')
            output = Path(root)/'safety.pptx'
            result = build_safety_presentation(report, output, root)
            prs = Presentation(output); template = Presentation(TEMPLATE_FILE)
            self.assertEqual(result['slide_count'], 30)
            for before, after in [(1, 1), (4, 4), (6, 6), (9, 9), (24, 23), (26, 25), (30, 29)]:
                self.assertEqual([s.text for s in template.slides[before].shapes if s.has_text_frame],
                    [s.text for s in prs.slides[after].shapes if s.has_text_frame])
            charts = [s.chart for slide in prs.slides for s in slide.shapes if s.has_chart]
            self.assertGreater(len(charts), 5)
            self.assertEqual(len([s for s in prs.slides[11].shapes if s.has_chart]), 1)
            self.assertTrue(any(s.shape_type == 13 for s in prs.slides[5].shapes))
            for slide in prs.slides:
                for shape in slide.shapes:
                    if shape.has_chart or shape.has_table or (shape.has_text_frame and shape.top > 914400):
                        self.assertLessEqual(shape.left + shape.width, prs.slide_width + 1000)
                        self.assertLessEqual(shape.top + shape.height, prs.slide_height + 1000)
            with ZipFile(output) as z:
                self.assertFalse(any('comments/' in name for name in z.namelist()))
                self.assertTrue(any('embeddings/' in name for name in z.namelist()))
            self.assertNotIn('2021年4月', '\n'.join(s.text for slide in prs.slides for s in slide.shapes if s.has_text_frame))

    def test_old_snapshot_requires_regeneration_instead_of_stale_ppt(self):
        with self.assertRaises(ValueError): build_safety_presentation({}, '/tmp/should-not-exist-safety.pptx')


@unittest.skipUnless(os.environ.get('REPORT_AI_MEMORY_TEST_DSN'), 'requires isolated PostgreSQL test DSN')
class SafetySettingsPostgresTest(unittest.TestCase):
    def setUp(self):
        self.schema = 'safety_test_' + uuid.uuid4().hex
        self.dsn = os.environ['REPORT_AI_MEMORY_TEST_DSN']
        conn = psycopg2.connect(self.dsn); conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(f'CREATE SCHEMA "{self.schema}"')
            cur.execute(f'SET search_path TO "{self.schema}"')
            cur.execute('CREATE TABLE users(id INTEGER PRIMARY KEY); INSERT INTO users VALUES(7)')
            cur.execute('CREATE TABLE inspection_report_ai_memory(issue_ids BIGINT[], payload JSONB, created_at TIMESTAMPTZ, report_type TEXT, operation TEXT)')
        conn.close()
        self.engine = sa.create_engine('postgresql+psycopg2://', creator=lambda: psycopg2.connect(
            self.dsn, options=f'-csearch_path={self.schema}'))
        spec = importlib.util.spec_from_file_location('safety_migration', Path(__file__).parents[1]/'migrations/versions/20261029_001_safety_report.py')
        migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
        with self.engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade(); migration.upgrade()

    def connect(self):
        conn = psycopg2.connect(self.dsn, cursor_factory=RealDictCursor)
        with conn.cursor() as cur: cur.execute(f'SET search_path TO "{self.schema}"')
        conn.commit(); return conn

    def tearDown(self):
        self.engine.dispose()
        conn = psycopg2.connect(self.dsn); conn.autocommit = True
        with conn.cursor() as cur: cur.execute(f'DROP SCHEMA "{self.schema}" CASCADE')
        conn.close()

    def test_optimistic_revision_conflict_and_rollback_preserve_saved_settings(self):
        conn = self.connect()
        with conn.cursor() as cur: save_settings(cur, {'station_ids': [1]}, 0, {'id': 7, 'real_name': '甲'})
        conn.commit()
        with conn.cursor() as cur:
            with self.assertRaises(ValueError): save_settings(cur, {'station_ids': []}, 0, {'id': 7})
        conn.rollback()
        with conn.cursor() as cur:
            self.assertEqual(load_settings(cur)['settings'], {'station_ids': [1]})
            save_settings(cur, {'station_ids': []}, 1, {'id': 7})
        conn.rollback()
        with conn.cursor() as cur: self.assertEqual(load_settings(cur)['revision'], 1)
        conn.close()

    def test_two_concurrent_saves_cannot_overwrite_each_other(self):
        from concurrent.futures import ThreadPoolExecutor
        def save(value):
            conn = self.connect()
            try:
                with conn.cursor() as cur: save_settings(cur, {'station_ids': [value]}, 0, {'id': 7})
                conn.commit(); return True
            except ValueError:
                conn.rollback(); return False
            finally: conn.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(save, [1, 2]))
        self.assertEqual(sorted(results), [False, True])
