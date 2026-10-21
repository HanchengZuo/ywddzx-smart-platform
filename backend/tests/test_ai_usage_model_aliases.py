"""Disposable database checks for old/new Flash filtering; no paid model requests."""
import os
import unittest
import uuid
from unittest.mock import MagicMock, patch

from flask import Flask
import psycopg2
from psycopg2.extensions import parse_dsn
from psycopg2.extras import RealDictCursor

from ai_routing import model_aliases


@unittest.skipUnless(os.environ.get('AI_MODEL_TEST_DSN'), 'requires an isolated test PostgreSQL database')
class UsageModelAliasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import app as core
        cls.core = core
        cls.dsn = os.environ['AI_MODEL_TEST_DSN']
        if not parse_dsn(cls.dsn).get('dbname', '').startswith('test_'):
            raise RuntimeError('Only disposable test_ databases are permitted')

    def connect(self):
        return psycopg2.connect(self.dsn, options='-c search_path=' + self.schema, cursor_factory=RealDictCursor)

    def setUp(self):
        self.schema = 'flash_usage_' + uuid.uuid4().hex
        with psycopg2.connect(self.dsn) as conn, conn.cursor() as cur:
            cur.execute('CREATE SCHEMA ' + self.schema)
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute('CREATE TABLE users(id int PRIMARY KEY)')
            self.core.ensure_ai_usage_schema(cur)
            for model in [*model_aliases('deepseek-flash'), 'qwen3.8-max', 'deepseek-v4-pro']:
                cur.execute('''INSERT INTO ai_usage_logs(model,usage_module,usage_action,ai_called,
                    input_tokens_est,total_tokens_est,total_cost_est) VALUES(%s,'测试','回答',TRUE,123,123,0.42)''', (model,))
        self.app = Flask(__name__)
        self.app.add_url_rule('/usage', view_func=self.core.get_management_ai_usage)
        self.authorize = MagicMock(return_value={'id': 7})
        self.patches = [patch.object(self.core, 'get_db_connection', self.connect),
                        patch.object(self.core, 'ensure_user_security_schema'),
                        patch.object(self.core, 'require_management_user', self.authorize)]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def tearDown(self):
        with psycopg2.connect(self.dsn) as conn, conn.cursor() as cur:
            cur.execute('DROP SCHEMA ' + self.schema + ' CASCADE')

    def test_filter_includes_old_and_new_ids_once_without_rewriting_stored_usage(self):
        client = self.app.test_client()
        for selected in model_aliases('deepseek-flash'):
            response = client.get('/usage', query_string={'user_id': 7, 'model': selected})
            self.assertEqual(response.status_code, 200, response.json)
            self.assertEqual(len(response.json['items']), 3)
            self.assertEqual(len({item['id'] for item in response.json['items']}), 3)
            self.assertEqual({item['model'] for item in response.json['items']}, {'deepseek-flash'})
            self.assertTrue(all(item['pricing_known'] for item in response.json['items']))
            self.assertTrue(all(item['total_cost_est'] == .42 for item in response.json['items']))
            self.assertEqual(response.json['options']['models'], ['deepseek-flash', 'deepseek-v4-pro', 'qwen3.8-max'])
        self.assertEqual(self.authorize.call_args.args[1:], ('7', 'manage_ai_usage'))
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute('SELECT model FROM ai_usage_logs')
            self.assertCountEqual([row['model'] for row in cur.fetchall()],
                                  [*model_aliases('deepseek-flash'), 'qwen3.8-max', 'deepseek-v4-pro'])

    def test_other_models_and_denied_access_keep_existing_behavior(self):
        client = self.app.test_client()
        response = client.get('/usage', query_string={'model': 'qwen3.8-max'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json['items']), 1)
        self.assertFalse(response.json['items'][0]['pricing_known'])
        self.authorize.side_effect = PermissionError('无查看权限')
        response = client.get('/usage', query_string={'model': 'deepseek-flash'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json, {'success': False, 'error': '无查看权限'})
