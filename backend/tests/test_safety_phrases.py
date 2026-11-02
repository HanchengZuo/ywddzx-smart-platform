"""Source-bound phrase editing, cache reuse and permissions; never call paid AI."""

import json
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask

from safety_report_analysis import normalize_settings
from safety_report_phrases import (attach_phrases, phrase_catalog, phrase_key, load_phrases,
    ensure_phrases, phrases_signature, generate_phrases, cache_key)
from safety_phrases_http import register_safety_phrases
from tests.test_safety_report import raw_issue
from safety_report_data import serialize

CATALOG = [
    dict(key='onsite:13001', mode='onsite', external_standard_id='13001',
        fields={'检查内容': '常用计量器具管理（包括加油机、油罐）', '序号': '1'}),
    dict(key='video:14001', mode='video', external_standard_id='14001',
        fields={'检查内容': '设备维修作业', '评分项': '作业前放置围栏和消防器材'}),
    dict(key='video:14002', mode='video', external_standard_id='14002',
        fields={'检查内容': '卸油作业', '评分项': '作业前放置围栏和消防器材'}),
]
DSN = os.environ.get('REPORT_AI_MEMORY_TEST_DSN')


def response(phrases):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({'items': phrases})))])


class PhrasesUnitTests(unittest.TestCase):
    def test_catalog_uses_correct_field_and_same_source_is_one_persistent_key(self):
        rows = phrase_catalog(CATALOG)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['default_phrase'], '液位仪')
        self.assertEqual(rows[1]['standard_ids'], ['14001', '14002'])
        self.assertEqual(rows[1]['source'], '作业前放置围栏和消防器材')
        changed = {**rows[1], 'standard_ids': ['14003']}
        self.assertEqual(cache_key(changed), cache_key(rows[1]))
        self.assertNotEqual(phrase_key('onsite', rows[1]['source']), rows[1]['key'])
        self.assertEqual(phrase_catalog([{**CATALOG[1], 'fields': {'检查内容': '设备维修作业'}}]), [])
        other = phrase_catalog([dict(key='onsite:13050', mode='onsite', external_standard_id='13050', fields={'序号': '50'})])
        self.assertEqual(other[0]['default_phrase'], '其他')

    def test_attachment_uses_exact_source_manual_wins_without_touching_major_categories(self):
        issue = serialize(raw_issue(mode='video', standard_detail_text='检查内容：设备维修作业\n评分项：作业前放置围栏和消防器材'))
        key = phrase_key('video', '作业前放置围栏和消防器材')
        rows = attach_phrases([issue], [{'key': key, 'phrase': '警示防护'}], {'analysis_phrases': {key: '隔离与消防'}})
        self.assertEqual(rows[0]['analysis_phrase'], '隔离与消防')
        self.assertEqual(rows[0]['topic'], '设备维修作业')
        self.assertNotIn('analysis_phrase', issue)
        self.assertEqual(attach_phrases([issue], [])[0]['analysis_phrase'], '未配置评分项短语')
        sparse = dict(issue, external_standard_id='14001', standard_detail_text='检查内容：设备维修作业')
        library = [{**phrase_catalog(CATALOG)[1], 'phrase': '警示防护'}]
        self.assertEqual(attach_phrases([sparse], library)[0]['analysis_phrase'], '警示防护')

    def test_normalization_and_signature_only_track_effective_content(self):
        key = phrase_key('onsite', '测试')
        self.assertEqual(normalize_settings({'analysis_phrases': {key: '  人工短语  '}})['analysis_phrases'][key], '人工短语')
        for value in [{'bad': '短语'}, {key: ''}, {key: 'a'*31}, {key: '两\n行'}]:
            with self.assertRaises(ValueError): normalize_settings({'analysis_phrases': value})
        self.assertEqual(phrases_signature([{'key': key, 'phrase': '短语', 'status': 'ai'}]),
            phrases_signature([{'key': key, 'phrase': '短语', 'status': 'manual'}]))

    def test_generation_rejects_missing_or_outside_refs_without_accepting_partial(self):
        client = MagicMock(); client.with_options.return_value = client
        client.chat.completions.create.return_value = response({'P999': '范围外'})
        with patch('safety_report_phrases.get_ai_client', return_value=client), patch('ai_routing._loader', None):
            with self.assertRaisesRegex(ValueError, '未通过核验'): generate_phrases(phrase_catalog(CATALOG)[1:])
        self.assertEqual(client.chat.completions.create.call_count, 2)
        client.close.assert_called_once()

    def test_duplicate_ai_fields_are_rejected_but_json_fences_are_compatible(self):
        client = MagicMock(); client.with_options.return_value = client
        item = response({'P1': '警示防护'})
        item.choices[0].message.content = '{"items":{"P1":"错误","P1":"警示防护"}}'
        client.chat.completions.create.return_value = item
        with patch('safety_report_phrases.get_ai_client', return_value=client), patch('ai_routing._loader', None):
            with self.assertRaises(ValueError): generate_phrases(phrase_catalog(CATALOG)[1:])
            item.choices[0].message.content = '```json\n{"items":{"P1":"警示防护"}}\n```'
            value = generate_phrases(phrase_catalog(CATALOG)[1:])
            self.assertEqual(next(iter(value['payload'].values())), '警示防护')

    def test_expired_deadline_does_not_call_or_record_a_phantom_provider_request(self):
        client = MagicMock()
        with patch('safety_report_phrases.get_ai_client', return_value=client), patch('ai_routing._loader', None), patch(
                'safety_report_phrases.time.monotonic', side_effect=[0, 100]):
            with self.assertRaises(ValueError) as result:
                generate_phrases(phrase_catalog(CATALOG)[1:], timeout=1)
        self.assertEqual(result.exception.ai_usage['request_count'], 0)
        self.assertFalse(result.exception.ai_usage['ai_called'])
        client.with_options.assert_not_called()


@unittest.skipUnless(DSN, 'requires isolated PostgreSQL test DSN')
class PhrasesPostgresTests(unittest.TestCase):
    def setUp(self):
        self.schema = 'safety_phrases_' + uuid.uuid4().hex
        conn = psycopg2.connect(DSN); conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(f'CREATE SCHEMA "{self.schema}"; SET search_path TO "{self.schema}"')
            cur.execute('''CREATE TABLE inspection_report_safety_settings(id INT PRIMARY KEY, settings JSONB NOT NULL DEFAULT '{}',
                revision INT NOT NULL DEFAULT 0, updated_by INT, updated_by_name TEXT, updated_at TIMESTAMPTZ DEFAULT now());
                CREATE TABLE inspection_report_ai_memory(cache_key TEXT PRIMARY KEY, operation TEXT, report_type TEXT,
                    issue_ids BIGINT[], payload JSONB, model TEXT, source_task_id TEXT, created_at TIMESTAMPTZ DEFAULT now());
                CREATE TABLE inspection_report_jobs(task_id TEXT PRIMARY KEY, ai_generation_log JSONB);''')
        conn.close()
        self.settings = normalize_settings({})
        self.user = {'id': 7, 'real_name': '测试用户'}
        self.permission = True
        self.workspace = MagicMock()
        self.audit = MagicMock()
        self.app = Flask(__name__)
        register_safety_phrases(self.app, connect=self.connect, authorize=lambda cur: self.user,
            has_permission=lambda *args: self.permission, fetch_catalog=lambda *args: CATALOG,
            save_workspace=self.workspace, log_usage=self.audit)
        self.client = self.app.test_client()

    def connect(self):
        return psycopg2.connect(DSN, options=f'-csearch_path={self.schema}', cursor_factory=RealDictCursor)

    def tearDown(self):
        conn = psycopg2.connect(DSN); conn.autocommit = True
        with conn.cursor() as cur: cur.execute(f'DROP SCHEMA "{self.schema}" CASCADE')
        conn.close()

    def test_concurrent_generation_calls_once_and_field_changes_only_generate_missing_source(self):
        client = MagicMock(); client.with_options.return_value = client
        client.chat.completions.create.return_value = response({'P1': '警示防护'})
        with patch('safety_report_phrases.get_ai_client', return_value=client), patch('ai_routing._loader', None):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: ensure_phrases(self.connect, CATALOG, self.settings), range(2)))
            self.assertEqual(results[0], results[1])
            self.assertEqual(client.chat.completions.create.call_count, 1)
            changed = [{**CATALOG[1], 'fields': {'评分项': '维修人员正确穿戴防护用品'}}]
            ensure_phrases(self.connect, changed, self.settings)
            self.assertEqual(client.chat.completions.create.call_count, 2)
            ensure_phrases(self.connect, CATALOG, self.settings)
            self.assertEqual(client.chat.completions.create.call_count, 2)

    def test_get_put_do_not_call_ai_manual_persists_globally_and_conflicts_do_not_overwrite(self):
        with patch('safety_report_phrases.get_ai_client', side_effect=AssertionError('must not call AI')):
            value = self.client.get('/api/inspection-reports/safety-phrases').json
            key = value['rows'][1]['key']
            body = {'catalog_signature': value['catalog_signature'], 'revision': 0, 'changes': {key: '人工警示短语'}}
            self.assertEqual(self.client.put('/api/inspection-reports/safety-phrases', json=body).status_code, 200)
            self.assertEqual(self.client.get('/api/inspection-reports/safety-phrases').json['rows'][1]['phrase'], '人工警示短语')
            self.assertEqual(self.client.put('/api/inspection-reports/safety-phrases', json=body).status_code, 409)
            self.permission = False
            self.assertEqual(self.client.post('/api/inspection-reports/safety-phrases', json={**body, 'revision': 1}).status_code, 403)
            self.user = None
            self.assertEqual(self.client.get('/api/inspection-reports/safety-phrases').status_code, 403)

    def test_post_records_actor_usage_and_reuses_generated_phrases(self):
        client = MagicMock(); client.with_options.return_value = client
        client.chat.completions.create.return_value = response({'P1': '警示防护'})
        value = self.client.get('/api/inspection-reports/safety-phrases').json
        body = {'catalog_signature': value['catalog_signature'], 'revision': 0, 'user_id': 999}
        with patch('safety_report_phrases.get_ai_client', return_value=client), patch('ai_routing._loader', None):
            first = self.client.post('/api/inspection-reports/safety-phrases', json=body)
            self.assertEqual(first.status_code, 200)
            self.assertEqual(first.json['rows'][1]['phrase'], '警示防护')
            self.assertEqual(self.client.post('/api/inspection-reports/safety-phrases', json=body).status_code, 200)
            self.assertEqual(client.chat.completions.create.call_count, 1)
        self.assertEqual(self.audit.call_args_list[0].args[1]['id'], 7)
        self.assertEqual(self.workspace.call_count, 1)

    def test_concurrent_manual_saves_cannot_overwrite_each_other(self):
        value = self.client.get('/api/inspection-reports/safety-phrases').json
        def save(phrase):
            body = {'catalog_signature': value['catalog_signature'], 'revision': 0, 'changes': {value['rows'][0]['key']: phrase}}
            return self.app.test_client().put('/api/inspection-reports/safety-phrases', json=body).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(save, ['甲的短语', '乙的短语'])), [200, 409])
        self.assertEqual(self.client.get('/api/inspection-reports/safety-phrases').json['meta']['revision'], 1)

    def test_failed_workspace_write_rolls_back_phrase_changes_and_invalid_output_is_not_cached(self):
        value = self.client.get('/api/inspection-reports/safety-phrases').json
        body = {'catalog_signature': value['catalog_signature'], 'revision': 0, 'changes': {value['rows'][0]['key']: '人工短语'}}
        self.workspace.side_effect = RuntimeError('test audit failure')
        self.assertEqual(self.client.put('/api/inspection-reports/safety-phrases', json=body).status_code, 500)
        self.assertEqual(self.client.get('/api/inspection-reports/safety-phrases').json['meta']['revision'], 0)
        client = MagicMock(); client.with_options.return_value = client
        client.chat.completions.create.return_value = response({'P999': '无效'})
        with patch('safety_report_phrases.get_ai_client', return_value=client), patch('ai_routing._loader', None):
            with self.assertRaises(ValueError): ensure_phrases(self.connect, CATALOG, self.settings)
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute('SELECT count(*) AS n FROM inspection_report_ai_memory')
            self.assertEqual(cur.fetchone()['n'], 0)
