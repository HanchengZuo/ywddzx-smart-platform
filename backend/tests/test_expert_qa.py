import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from flask import Flask
from expert_knowledge import normalize_request, period_predicates, redact, recall, safe_file, select_evidence, source, report_passages
from expert_qa import PERMISSION, ExpertCallError, generate, identity, normalize_answer, register_expert_qa


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        route_loader = patch('ai_routing._loader', None)
        route_loader.start()
        self.addCleanup(route_loader.stop)

    def test_request_bounds_and_global_period(self):
        question, options = normalize_request({'question': '系统有什么问题', 'region': ' 浦东 ',
                                               'date_from': '2026-01-01', 'date_to': '2026-01-31'})
        self.assertEqual(options, {'date_from': '', 'date_to': '', 'region': ''})
        for data in [[], {}, {'question': 'a'}, {'question': 'a' * 1501},
                     {'question': '2026年2月30日的问题'}, {'question': '2026年3月2日至2026年2月1日的问题'}]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                normalize_request(data)

    def test_sensitive_text_is_not_sent_or_displayed(self):
        self.assertNotIn('13800138000', redact('负责人13800138000'))
        self.assertNotIn('sk-abcdefghijklmnopqrstuv', redact('sk-abcdefghijklmnopqrstuv'))
        self.assertNotIn('123456', redact('password=123456'))
        answer = normalize_answer({'paragraphs': [{'text': '密码：123456', 'sources': ['S1']}]}, [{'id': 'S1'}])
        self.assertNotIn('123456', answer['paragraphs'][0]['text'])

    def test_dates_region_and_keywords_are_bound_not_sql_generated(self):
        where, params = period_predicates({'date_from': '2026-10-01', 'date_to': '2026-10-13', 'region': "x' OR TRUE --"}, 'i.created_at', 's.region')
        self.assertNotIn("x' OR TRUE", ' '.join(where))
        cur = MagicMock()
        cur.fetchall.return_value = []
        recall(cur, 'SELECT id FROM safe_business', ['description'], "x' OR TRUE --", where, params)
        statement, parameters = cur.execute.call_args.args
        self.assertNotIn("x' OR TRUE", statement)
        self.assertIn("x' OR TRUE --", parameters)
        self.assertEqual(parameters[-1], 160)
        self.assertIn('ILIKE ANY(%s)', statement)

    def test_bounded_evidence_prefers_relevant_content_and_keeps_complete_statistics(self):
        records = [source('stats:issues', '数据库统计', '统计', '登记1000项', '')]
        records += [source('issue:' + str(i), '问题', '铅封', '铅封核对检查。' * 500, '') for i in range(100)]
        evidence = select_evidence('铅封核对', records)
        self.assertEqual(evidence[0]['key'], 'stats:issues')
        self.assertLessEqual(len(evidence), 24)
        self.assertLess(sum(len(row['text']) + len(row['title']) + 200 for row in evidence), 24001)
        self.assertEqual(len(set(row['id'] for row in evidence)), len(evidence))

    def test_storage_boundary_disallows_secrets_and_symlinks(self):
        with TemporaryDirectory() as root, TemporaryDirectory() as external:
            folder = Path(root)
            (folder / 'training_materials').mkdir()
            good = folder / 'training_materials' / 'lesson.pdf'
            good.write_bytes(b'%PDF test')
            self.assertEqual(safe_file(root, '/training_materials/lesson.pdf'), good)
            secret = Path(external) / 'secret.txt'
            secret.write_text('not for AI')
            (folder / 'training_materials' / 'link.pdf').symlink_to(secret)
            self.assertIsNone(safe_file(root, '/training_materials/link.pdf'))
            self.assertIsNone(safe_file(root, '../secret.txt'))
            (folder / 'backup.txt').write_text('secret')
            self.assertIsNone(safe_file(root, '/backup.txt'))

    def test_invalid_or_missing_citations_are_not_published(self):
        evidence = [{'id': 'S1'}]
        for payload in [None, {}, {'paragraphs': []}, {'paragraphs': [{'text': '结论', 'sources': []}]},
                        {'paragraphs': [{'text': '结论', 'sources': ['S999']}]},
                        {'paragraphs': [{'text': 'x' * 1201, 'sources': ['S1']}]}]:
            with self.assertRaises(RuntimeError):
                normalize_answer(payload, evidence)

    def test_report_projection_does_not_send_blobs_or_generation_settings(self):
        payload = {'title': '检查结论', 'work_plan': [{'text': '及时整改', 'photo_path': '/private/file.jpg'}],
                   'generation_context': {'api_key': 'secret'}, 'base64': 'SECRET IMAGE'}
        passages = report_passages(payload)
        self.assertEqual(passages, ['检查结论', '及时整改'])

    def test_ai_is_existing_provider_without_tools_and_bounded_timeout(self):
        client = MagicMock()
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({'paragraphs': [{'text': '依据规范核对铅封。', 'sources': ['S1']}]})))])
        client.with_options.return_value.chat.completions.create.return_value = response
        answer, usage = generate('铅封核对', [{'id': 'S1', 'text': '应核对铅封'}], client=client)
        self.assertEqual(answer['paragraphs'][0]['sources'], ['S1'])
        self.assertTrue(usage['ai_called'])
        client.with_options.assert_called_once_with(timeout=90, max_retries=0)
        args = client.with_options.return_value.chat.completions.create.call_args.kwargs
        self.assertNotIn('tools', args)
        self.assertEqual(args['max_tokens'], 4096)

    def test_failed_provider_call_has_safe_message_and_usage_metrics(self):
        class BalanceError(Exception):
            status_code = 402
        client = MagicMock()
        client.with_options.return_value.chat.completions.create.side_effect = BalanceError('provider details must not reach UI')
        with self.assertRaises(ExpertCallError) as caught:
            generate('铅封要求', [{'id': 'S1', 'text': '资料'}], client=client)
        self.assertIn('余额不足', str(caught.exception))
        self.assertTrue(caught.exception.usage['ai_called'])
        self.assertEqual(caught.exception.usage['status_code'], 402)
        self.assertGreater(caught.exception.usage['prompt_chars'], 0)


class ExpertApiTests(unittest.TestCase):
    def setUp(self):
        route_loader = patch('ai_routing._loader', None)
        route_loader.start()
        self.addCleanup(route_loader.stop)
        self.user = {'id': 17, 'role': 'area_account', 'auth_version': 2, 'account_status': 'active'}
        self.cur = MagicMock()
        self.conn = MagicMock()
        self.conn.cursor.return_value = self.cur
        self.core = dict(get_db_connection=lambda: self.conn, get_current_request_user=lambda: self.user,
                         has_permission=MagicMock(return_value=True), close_db_resources=MagicMock(),
                         fetch_auth_user_by_id=MagicMock(side_effect=lambda cur, user_id: dict(self.user)),
                         is_password_change_enforced=MagicMock(return_value=False), fetch_password_policy=lambda cur: {},
                         record_ai_usage_log=MagicMock())
        self.app = Flask(__name__)
        register_expert_qa(self.app, self.core)
        self.client = self.app.test_client()

    def test_access_uses_independent_expert_permission_for_every_endpoint(self):
        self.assertEqual(PERMISSION, 'view_expert_qa')
        self.core['has_permission'].return_value = False
        for method, path in [('get', '/meta'), ('get', '/questions'), ('post', '/questions'), ('get', '/questions/unknown')]:
            response = getattr(self.client, method)('/api/operations/expert' + path)
            self.assertEqual(response.status_code, 403)
            self.core['has_permission'].assert_called_with(self.cur, self.user, PERMISSION)

    def test_cockpit_grant_does_not_grant_expert_and_expert_does_not_require_cockpit(self):
        for cockpit, expert, status in ((True, False, 403), (False, True, 200)):
            with self.subTest(cockpit=cockpit, expert=expert):
                self.core['has_permission'].side_effect = lambda cur, user, key: {
                    'view_operations_overview': cockpit, 'view_expert_qa': expert,
                }.get(key, False)
                self.assertEqual(self.client.get('/api/operations/expert/meta').status_code, status)

    def test_global_scope_is_visible_and_read_only_metadata_connection(self):
        response = self.client.get('/api/operations/expert/meta')
        self.assertEqual(response.status_code, 200)
        self.assertIn('全局', response.json['scope'])
        self.assertIn('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY', [call.args[0] for call in self.cur.execute.call_args_list])

    def test_another_users_or_old_sessions_history_cannot_be_read(self):
        self.cur.fetchone.return_value = None
        response = self.client.get('/api/operations/expert/questions/' + 'a' * 32)
        self.assertEqual(response.status_code, 404)
        query, params = self.cur.execute.call_args.args
        self.assertIn('user_id=%s AND session_key=%s', query)
        self.assertEqual(params[1:], [17, identity(self.user)])

    def test_history_is_bounded_and_owned(self):
        self.cur.fetchall.return_value = []
        self.assertEqual(self.client.get('/api/operations/expert/questions').status_code, 200)
        query, params = self.cur.execute.call_args.args
        self.assertIn('LIMIT 20', query)
        self.assertEqual(params, [17, identity(self.user)])

    def test_malformed_requests_and_busy_users_do_not_call_ai(self):
        self.assertEqual(self.client.post('/api/operations/expert/questions', json=[]).status_code, 400)
        self.cur.fetchone.return_value = {'running': 1, 'today': 0}
        with patch('expert_qa.executor.submit') as submit:
            response = self.client.post('/api/operations/expert/questions', json={'question': '铅封要求'})
        self.assertEqual(response.status_code, 429)
        submit.assert_not_called()

    def test_daily_budget_and_successful_background_submission(self):
        self.cur.fetchone.return_value = {'running': 0, 'today': 30}
        self.assertEqual(self.client.post('/api/operations/expert/questions', json={'question': '铅封要求'}).status_code, 429)
        self.cur.fetchone.return_value = {'running': 0, 'today': 0}
        with patch('expert_qa.capacity') as gate, patch('expert_qa.executor.submit') as submit:
            gate.acquire.return_value = True
            response = self.client.post('/api/operations/expert/questions', json={'question': '铅封要求'})
            self.assertEqual(response.status_code, 202)
            self.assertEqual(len(response.json['id']), 32)
            submit.assert_called_once()
            gate.release.assert_not_called()
            self.conn.commit.assert_called()

    def run_worker(self, cache=None, revoked=False, parent=''):
        self.cur.fetchone.side_effect = [{'running': 0, 'today': 0}, cache]
        evidence = [{'id': 'S1', 'key': 'external:1', 'text': '应核对铅封'}]
        answer = {'paragraphs': [{'text': '核对铅封', 'sources': ['S1']}], 'caveat': ''}
        with patch('expert_qa.capacity') as gate, patch('expert_qa.executor.submit') as submit, \
             patch('expert_qa.retrieve', return_value=(evidence, {'source_count': 1})) as retrieve_mock, \
             patch('expert_qa.get_deepseek_client', return_value=MagicMock()), \
             patch('expert_qa.generate', return_value=(answer, {'ai_called': True, 'success': True})) as ai:
            gate.acquire.return_value = True
            response = self.client.post('/api/operations/expert/questions', json={'question': '铅封要求', 'parent_id': parent})
            self.assertEqual(response.status_code, 202)
            if revoked:
                self.core['fetch_auth_user_by_id'].side_effect = [dict(self.user), {**self.user, 'auth_version': 99}]
            callback, *args = submit.call_args.args
            callback(*args)
            gate.release.assert_called_once()
            return ai.call_count, retrieve_mock.call_count

    def test_worker_reuses_same_evidence_without_ai_and_logs_zero_call(self):
        cached = {'result': {'answer': {'paragraphs': [{'text': '历史回答', 'sources': ['S1']}], 'caveat': ''}}}
        calls, _ = self.run_worker(cache=cached)
        self.assertEqual(calls, 0)
        logged = self.core['record_ai_usage_log'].call_args.args[2]
        self.assertFalse(logged['usage']['ai_called'])
        results = [call.args[1][1].adapted for call in self.cur.execute.call_args_list
                   if call.args[0].startswith('UPDATE expert_qa_questions SET status=') and call.args[1][0] == 'completed']
        self.assertTrue(results[0]['cache_hit'])

    def test_worker_calls_ai_when_evidence_has_no_successful_cache(self):
        self.assertEqual(self.run_worker()[0], 1)
        logged = self.core['record_ai_usage_log'].call_args.args[2]
        self.assertTrue(logged['usage']['ai_called'])

    def test_revocation_during_ai_does_not_publish_success(self):
        self.run_worker(revoked=True)
        updates = [call.args[1][0] for call in self.cur.execute.call_args_list
                   if call.args[0].startswith('UPDATE expert_qa_questions SET status=')]
        self.assertNotIn('completed', updates)
        self.assertIn('failed', updates)

    def test_foreign_parent_does_not_retrieve_or_call_ai(self):
        self.cur.fetchone.return_value = None
        with patch('expert_qa.executor.submit') as submit:
            response = self.client.post('/api/operations/expert/questions', json={'question': '铅封要求', 'parent_id': 'a' * 32})
        self.assertEqual(response.status_code, 400)
        submit.assert_not_called()

    def test_history_summaries_do_not_read_answer_blobs_and_thread_filter_is_owned(self):
        self.cur.fetchall.return_value = []
        self.assertEqual(self.client.get('/api/operations/expert/questions?summary=1').status_code, 200)
        statement, params = self.cur.execute.call_args.args
        self.assertNotIn(',result', statement)
        self.assertIn('LIMIT 100', statement)
        self.assertEqual(params, [17, identity(self.user)])
        root = 'a' * 32
        self.assertEqual(self.client.get('/api/operations/expert/questions?conversation_id=' + root).status_code, 200)
        statement, params = self.cur.execute.call_args.args
        self.assertIn("COALESCE(options->>'conversation_id',id)=%s", statement)
        self.assertEqual(params, [17, identity(self.user), root])
        self.assertEqual(self.client.get('/api/operations/expert/questions?conversation_id=invalid').status_code, 400)


if __name__ == '__main__':
    unittest.main()
