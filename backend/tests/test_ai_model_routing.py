import json
import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import ai_routing as routing
from ai_model_settings import catalog, save_settings, SettingsConflict
from ai_usage import build_ai_usage_meta
import ai_utils
from report_ai_memory import _current


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.loader = patch.object(routing, '_loader', None)
        self.loader.start()
        self.addCleanup(self.loader.stop)

    def test_catalog_contains_requested_models_and_all_scenarios_no_secrets(self):
        with patch.dict(os.environ, {'ZHIPU_API_KEY': 'secret-not-in-json'}):
            data = catalog()
        self.assertEqual(len(data['models']), 10)
        self.assertEqual(len(data['scenarios']), 15)
        self.assertIn('mimo-v2.6-pro-ultraspeed', [row['id'] for row in data['models']])
        self.assertNotIn('secret-not-in-json', json.dumps(data))
        self.assertTrue(next(row for row in data['providers'] if row['id'] == 'zhipu')['configured'])

    def test_default_override_and_snapshot_during_config_change(self):
        config = {'default_model': 'qwen3.8-max', 'overrides': {'expert_qa': 'glm-5.3'}}
        routing.configure_routing(lambda: config)
        self.assertEqual(routing.resolve_model('finance_insights'), 'qwen3.8-max')
        with routing.model_scope('expert_qa'):
            config['overrides']['expert_qa'] = 'mimo-v2.6-pro'
            with routing.model_scope('expert_qa'):
                self.assertEqual(routing.current_model(), 'glm-5.3')
        self.assertEqual(routing.resolve_model('expert_qa'), 'mimo-v2.6-pro')
        self.assertEqual(routing.current_model(), routing.DEFAULT_MODEL)

    def test_context_isolation_under_parallel_calls_and_exception(self):
        routing.configure_routing(lambda: {'default_model': 'glm-5.3', 'overrides': {'expert_qa': 'qwen3.8-max'}})
        barrier = threading.Barrier(2)
        @routing.ai_scene(lambda scene: scene)
        def run(scene):
            barrier.wait(timeout=3)
            return routing.current_model()
        with ThreadPoolExecutor(2) as executor:
            a = executor.submit(run, 'expert_qa')
            b = executor.submit(run, 'feedback_title')
            self.assertEqual([a.result(), b.result()], ['qwen3.8-max', 'glm-5.3'])
        with self.assertRaises(RuntimeError), routing.model_scope('expert_qa'):
            raise RuntimeError('test')
        self.assertEqual(routing.current_model(), routing.DEFAULT_MODEL)

    def test_all_provider_protocols_keep_json_messages_and_do_not_mutate_input(self):
        original = {'messages': [{'role': 'user', 'content': 'json'}], 'response_format': {'type': 'json_object'},
                    'max_tokens': 1800, 'extra_body': {'thinking': {'type': 'disabled'}}}
        for model in routing.MODELS:
            with self.subTest(model=model):
                params = routing.completion_options(model, original)
                self.assertEqual(params['model'], model)
                self.assertEqual(params['messages'], original['messages'])
                self.assertEqual(params['response_format'], original['response_format'])
                provider = routing.MODELS[model][0]
                if provider == 'zhipu':
                    self.assertEqual(params['extra_body']['thinking']['type'], 'enabled')
                    self.assertEqual(params['reasoning_effort'], 'low')
                    self.assertGreaterEqual(params['max_tokens'], 16384)
                elif provider == 'qwen':
                    self.assertIs(params['extra_body']['enable_thinking'], False)
                    self.assertNotIn('thinking', params['extra_body'])
                elif provider == 'mimo':
                    self.assertEqual(params['max_completion_tokens'], 1800)
                    self.assertNotIn('max_tokens', params)
        self.assertEqual(original['extra_body'], {'thinking': {'type': 'disabled'}})

    def test_real_sdk_serializes_each_provider_request_without_network(self):
        try:
            import httpx2 as httpx
        except ImportError:
            import httpx
        from openai import OpenAI
        received = []
        def handle(request):
            received.append((str(request.url), json.loads(request.content)))
            return httpx.Response(200, json={'id': 'test', 'object': 'chat.completion', 'created': 0,
                'model': received[-1][1]['model'], 'choices': [{'index': 0, 'finish_reason': 'stop',
                'message': {'role': 'assistant', 'content': '{"ok":true}'}}]})
        with httpx.Client(transport=httpx.MockTransport(handle)) as transport:
            for model in routing.MODELS:
                routing.configure_routing(lambda: {'default_model': model})
                info = routing.model_info(model)
                client = OpenAI(api_key='fake-test-only', base_url=info['base_url'], http_client=transport)
                with routing.model_scope('expert_qa'):
                    response = routing.create_ai_completion(client, messages=[{'role': 'user', 'content': 'json'}],
                        max_tokens=1024, response_format={'type': 'json_object'})
                self.assertEqual(response.choices[0].message.content, '{"ok":true}')
                self.assertEqual(received[-1][0], info['base_url'].rstrip('/') + '/chat/completions')
                self.assertEqual(received[-1][1]['model'], model)
        self.assertEqual(len(received), len(routing.MODELS))

    def test_routing_failure_does_not_fallback_to_another_provider_or_leak_database_errors(self):
        routing.configure_routing(MagicMock(side_effect=RuntimeError('private database details')))
        with patch('openai.OpenAI') as client, self.assertRaisesRegex(RuntimeError, '大模型配置暂时不可用') as caught:
            ai_utils.generate_feedback_title('Bug反馈', '巡检系统', '问题')
        self.assertNotIn('private database', str(caught.exception))
        client.assert_not_called()

    def test_clients_read_only_selected_key_and_fixed_official_endpoint(self):
        with patch.dict(os.environ, {row['key_env']: 'test-secret-' + key for key, row in routing.PROVIDERS.items()}, clear=True), \
             patch('openai.OpenAI') as client:
            for model in routing.MODELS:
                routing.configure_routing(lambda: {'default_model': model})
                with routing.model_scope('expert_qa'):
                    routing.get_ai_client()
                info = routing.model_info(model)
                self.assertEqual(client.call_args.kwargs['api_key'], 'test-secret-' + info['provider'])
                self.assertEqual(client.call_args.kwargs['base_url'], info['base_url'])
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(routing.get_ai_client())

    def test_unpriced_provider_is_not_charged_using_deepseek_prices(self):
        usage = build_ai_usage_meta('qwen3.8-max', '测试输入', '测试回答', ai_called=True)
        self.assertFalse(usage['pricing_known'])
        self.assertEqual(usage['total_cost_est'], 0)
        self.assertGreater(usage['total_tokens_est'], 0)
        self.assertIn('dashscope', usage['base_url'])

    def test_business_functions_and_report_memory_use_runtime_model(self):
        config = {'default_model': 'qwen3.8-flash'}
        routing.configure_routing(lambda: config)
        memory = MagicMock()
        memory.batch.side_effect = lambda function, context, *args: function(context)
        token = _current.set(memory)
        self.addCleanup(_current.reset, token)
        client = MagicMock()
        client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{}'))])
        with patch.object(ai_utils, 'get_deepseek_client', return_value=client):
            result = ai_utils.generate_finance_report_insights({})
        self.assertEqual(memory.batch.call_args.args[-1], 'qwen3.8-flash')
        self.assertEqual(client.chat.completions.create.call_args.kwargs['model'], 'qwen3.8-flash')
        self.assertEqual(result['usage']['model'], 'qwen3.8-flash')

    def test_every_paid_business_entry_uses_its_scene_override(self):
        import equipment_report_analysis
        import expert_qa
        overrides = {key: list(routing.MODELS)[index % len(routing.MODELS)]
                     for index, key in enumerate(routing.SCENARIOS)}
        routing.configure_routing(lambda: {'default_model': routing.DEFAULT_MODEL, 'overrides': overrides})
        client = MagicMock()
        client.with_options.return_value = client
        client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{}'))])
        functions = {
            'quality_insights': ai_utils.generate_quality_measurement_report_insights,
            'quality_flow': ai_utils.classify_quality_measurement_report_flows,
            'non_oil_category': ai_utils.classify_non_oil_report_categories,
            'non_oil_key': ai_utils.classify_non_oil_key_issues,
            'non_oil_insights': ai_utils.generate_non_oil_report_insights,
            'equipment_insights': ai_utils.generate_equipment_facilities_report_insights,
            'safety_insights': ai_utils.generate_safety_quality_report_insights,
            'finance_insights': ai_utils.generate_finance_report_insights,
            'service_insights': ai_utils.generate_on_site_service_report_insights,
        }
        with patch.object(ai_utils, 'get_deepseek_client', return_value=client):
            for scene, function in functions.items():
                with self.subTest(scene=scene):
                    result = function({})
                    self.assertEqual(result['usage']['model'], overrides[scene])
                    self.assertEqual(client.chat.completions.create.call_args.kwargs['model'], overrides[scene])
            ai_utils.generate_feedback_title('Bug反馈', '巡检系统', '无法查看铅封')
            self.assertEqual(client.chat.completions.create.call_args.kwargs['model'], overrides['feedback_title'])
            import standard_recommendation_cache
            standard_recommendation_cache._entries.clear()
            ai_utils.generate_standard_recommendations('铅封缺失', [{'standard_id': '1', 'detail_text': '铅封缺失'}])
            self.assertEqual(client.chat.completions.create.call_args.kwargs['model'], overrides['standard_recommendation'])
            standard_recommendation_cache._entries.clear()
            client.chat.completions.create.return_value.choices[0].message.content = '{"issue_ids":[]}'
            for kind in ('high', 'special', 'severe'):
                result = equipment_report_analysis.choose_topics({'kind': kind, 'issues': [{'issue_id': 1}]})
                self.assertEqual(result['usage']['model'], overrides['equipment_' + kind])
            client.chat.completions.create.return_value.choices[0].message.content = '{"paragraphs":[{"text":"依据","sources":["S1"]}]}'
            _, usage = expert_qa.generate('依据是什么', [{'id': 'S1'}], client=client)
            self.assertEqual(usage['model'], overrides['expert_qa'])

    def test_recommendation_cache_is_invalidated_by_model(self):
        import standard_recommendation_cache as cache
        cache._entries.clear()
        self.addCleanup(cache._entries.clear)
        config = {'default_model': routing.DEFAULT_MODEL}
        routing.configure_routing(lambda: config)
        result = {'generated': True, 'retrieval': {}, 'usage': {}}
        with patch.object(ai_utils, '_generate_retrieved_standard_recommendations', return_value=result) as generate:
            rows = [{'standard_id': '1', 'detail_text': '铅封缺失', 'inspection_table_name': '检查表'}]
            ai_utils.generate_standard_recommendations('铅封缺失', rows)
            ai_utils.generate_standard_recommendations('铅封缺失', rows)
            self.assertEqual(generate.call_count, 1)
            config['default_model'] = 'glm-5.3'
            ai_utils.generate_standard_recommendations('铅封缺失', rows)
            self.assertEqual(generate.call_count, 2)

    def test_api_permission_rejection_rolls_back_without_writing(self):
        from flask import Flask, g
        from ai_model_http import register_ai_model_management
        app = Flask(__name__)
        @app.before_request
        def login():
            g.current_user = {'id': 1}
        conn = MagicMock()
        authorize = MagicMock(side_effect=PermissionError('无权限'))
        register_ai_model_management(app, connect=lambda: conn, require_management_user=authorize)
        for method in ('get', 'put'):
            response = getattr(app.test_client(), method)('/api/management/ai-models', json={})
            self.assertEqual(response.status_code, 403)
        conn.commit.assert_not_called()
        self.assertEqual(conn.rollback.call_count, 2)
        self.assertEqual(conn.close.call_count, 2)
        conn.cursor.return_value.__enter__.return_value.execute.assert_not_called()

    def test_invalid_settings_and_missing_key_never_write(self):
        cur = MagicMock()
        for data in (None, {}, {'revision': 0, 'default_model': 'arbitrary', 'overrides': {}},
                     {'revision': 0, 'default_model': [], 'overrides': {}},
                     {'revision': 0, 'default_model': routing.DEFAULT_MODEL, 'overrides': {'expert_qa': []}},
                     {'revision': 0, 'default_model': routing.DEFAULT_MODEL, 'overrides': {'unknown': 'glm-5.3'}}):
            with self.assertRaises(ValueError):
                save_settings(cur, data, {'id': 1})
        cur.execute.assert_not_called()
        cur.fetchone.return_value = {'revision': 1, 'default_model': routing.DEFAULT_MODEL, 'overrides': {}}
        with self.assertRaises(SettingsConflict):
            save_settings(cur, {'revision': 0, 'default_model': 'glm-5.3', 'overrides': {}}, {'id': 1})
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(ValueError, 'ZHIPU_API_KEY'):
            save_settings(cur, {'revision': 1, 'default_model': 'glm-5.3', 'overrides': {}}, {'id': 1})
        self.assertTrue(all(call.args[0].startswith('SELECT') for call in cur.execute.call_args_list))


@unittest.skipUnless(os.environ.get('AI_MODEL_TEST_DSN'), 'requires an isolated test PostgreSQL database')
class SettingsPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg2
        from psycopg2.extensions import parse_dsn
        from psycopg2.extras import RealDictCursor
        cls.dsn = os.environ['AI_MODEL_TEST_DSN']
        if not parse_dsn(cls.dsn).get('dbname', '').startswith('test_'):
            raise RuntimeError('Only test_ databases may be used')
        cls.psycopg2 = psycopg2
        cls.cursor_type = RealDictCursor

    def connect(self):
        return self.psycopg2.connect(self.dsn, cursor_factory=self.cursor_type)

    def setUp(self):
        self.loader = patch.object(routing, '_loader', None)
        self.loader.start()
        self.addCleanup(self.loader.stop)
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute((Path(__file__).parents[1] / 'db/init/720_ai_model_settings.sql').read_text())
            cur.execute('TRUNCATE ai_model_setting_events')
            cur.execute("UPDATE ai_model_settings SET default_model='deepseek-v4-pro',overrides='{}',revision=0,updated_by_name=''")

    def test_atomic_save_read_noop_conflict_and_audit(self):
        from ai_model_settings import read_settings
        payload = {'default_model': 'glm-5.3', 'overrides': {'expert_qa': 'qwen3.8-max'}, 'revision': 0}
        with patch.dict(os.environ, {'ZHIPU_API_KEY': 'fake', 'DASHSCOPE_API_KEY': 'fake'}):
            with self.connect() as conn, conn.cursor() as cur:
                saved = save_settings(cur, payload, {'id': 7, 'real_name': '测试管理员'})
                self.assertEqual(saved['revision'], 1)
            with self.connect() as conn, conn.cursor() as cur:
                payload['revision'] = 1
                self.assertEqual(save_settings(cur, payload, {'id': 7})['revision'], 1)
                cur.execute('SELECT count(*) AS n FROM ai_model_setting_events')
                self.assertEqual(cur.fetchone()['n'], 1)
            with self.connect() as conn, conn.cursor() as cur:
                saved = save_settings(cur, dict(payload, mode='all'), {'id': 8})
                self.assertEqual(saved['overrides'], {})
                self.assertEqual(saved['revision'], 2)
            with self.connect() as conn, conn.cursor() as cur:
                with self.assertRaises(SettingsConflict):
                    save_settings(cur, payload, {'id': 7})
                self.assertEqual(read_settings(cur)['revision'], 2)

    def test_failure_rolls_back_both_setting_and_event(self):
        conn = self.connect()
        try:
            with conn.cursor() as cur, patch.dict(os.environ, {'ZHIPU_API_KEY': 'fake'}):
                save_settings(cur, {'default_model': 'glm-5.3', 'overrides': {}, 'revision': 0}, {'id': 1})
                cur.execute('SELECT 1/0')
        except self.psycopg2.Error:
            conn.rollback()
        finally:
            conn.close()
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute('SELECT revision FROM ai_model_settings')
            self.assertEqual(cur.fetchone()['revision'], 0)
            cur.execute('SELECT count(*) AS n FROM ai_model_setting_events')
            self.assertEqual(cur.fetchone()['n'], 0)

    def test_explicit_model_matching_default_stays_pinned_after_default_changes(self):
        with patch.dict(os.environ, {'ZHIPU_API_KEY': 'fake', 'DEEPSEEK_API_KEY': 'fake'}):
            with self.connect() as conn, conn.cursor() as cur:
                saved = save_settings(cur, {'revision': 0, 'default_model': routing.DEFAULT_MODEL,
                    'overrides': {'expert_qa': routing.DEFAULT_MODEL}}, {'id': 1})
                self.assertEqual(saved['overrides']['expert_qa'], routing.DEFAULT_MODEL)
            with self.connect() as conn, conn.cursor() as cur:
                saved = save_settings(cur, {'revision': 1, 'default_model': 'glm-5.3',
                    'overrides': {'expert_qa': routing.DEFAULT_MODEL}}, {'id': 1})
                self.assertEqual(saved['overrides']['expert_qa'], routing.DEFAULT_MODEL)

    def test_migration_round_trip_preserves_existing_settings_when_run_twice(self):
        import importlib.util
        import sqlalchemy as sa
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        source = Path(__file__).parents[1] / 'migrations/versions/20261017_003_ai_model_routing.py'
        spec = importlib.util.spec_from_file_location('ai_model_migration', source)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        engine = sa.create_engine('postgresql+psycopg2://', creator=lambda: self.psycopg2.connect(self.dsn))
        try:
            with engine.begin() as conn, Operations.context(MigrationContext.configure(conn)):
                migration.downgrade()
                migration.upgrade()
                conn.execute(sa.text("UPDATE ai_model_settings SET default_model='glm-5.3',revision=3"))
                migration.upgrade()
                row = conn.execute(sa.text('SELECT default_model,revision FROM ai_model_settings')).one()
                self.assertEqual(tuple(row), ('glm-5.3', 3))
        finally:
            engine.dispose()

    def test_concurrent_admins_only_one_commits(self):
        barrier = threading.Barrier(2)
        def change(model):
            with self.connect() as conn, conn.cursor() as cur:
                barrier.wait(timeout=3)
                try:
                    save_settings(cur, {'default_model': model, 'overrides': {}, 'revision': 0}, {'id': 1})
                    return 'saved'
                except SettingsConflict:
                    return 'conflict'
        with patch.dict(os.environ, {'ZHIPU_API_KEY': 'fake', 'DASHSCOPE_API_KEY': 'fake'}), ThreadPoolExecutor(2) as executor:
            results = list(executor.map(change, ['glm-5.3', 'qwen3.8-max']))
        self.assertCountEqual(results, ['saved', 'conflict'])

    def test_http_success_and_transaction_rollback_on_response_failure(self):
        from flask import Flask, g
        from ai_model_http import register_ai_model_management
        app = Flask(__name__)
        @app.before_request
        def login():
            g.current_user = {'id': 7}
        register_ai_model_management(app, connect=self.connect,
                                     require_management_user=lambda *args: {'id': 7, 'username': 'root-test'})
        client = app.test_client()
        self.assertEqual(client.get('/api/management/ai-models').status_code, 200)
        self.assertEqual(client.put('/api/management/ai-models', json={'revision': 0}).status_code, 400)
        payload = {'default_model': 'glm-5.3', 'overrides': {}, 'revision': 0}
        with patch.dict(os.environ, {'ZHIPU_API_KEY': 'fake'}), patch('ai_model_http.catalog', side_effect=RuntimeError('test')):
            self.assertEqual(client.put('/api/management/ai-models', json=payload).status_code, 503)
        self.assertEqual(client.get('/api/management/ai-models').json['settings']['revision'], 0)
        with patch.dict(os.environ, {'ZHIPU_API_KEY': 'fake'}):
            response = client.put('/api/management/ai-models', json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['events'][0]['actor_name'], 'root-test')
            self.assertEqual(client.put('/api/management/ai-models', json=payload).status_code, 409)


if __name__ == '__main__':
    unittest.main()
