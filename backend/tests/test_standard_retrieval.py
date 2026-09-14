import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import ai_utils
import standard_recommendation_cache as response_cache
from standard_retrieval import retrieve_standards, cached_index, excerpt, MAX_CONTEXT_CHARS


def rule(identifier, text, table='计量稽查检查表（现场）'):
    return dict(standard_id=str(identifier), detail_text=text, inspection_table_name=table)


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        cached_index.cache_clear()
        response_cache._entries.clear()

    def test_chinese_and_domain_expansion(self):
        rows = [rule(1, '加油机铅封施封无效或不规范'), rule(2, '商品未先进先出'), rule(3, '灭火器压力不足')]
        result, _ = retrieve_standards('企业封未穿过螺丝', rows)
        self.assertEqual(result[0]['standard_id'], '1')
        result, _ = retrieve_standards('最新日期放到了前面', rows)
        self.assertEqual(result[0]['standard_id'], '2')

    def test_exact_id_not_substring(self):
        rows = [rule(1000, '检查人员培训'), rule(10007, '检查人员培训')]
        result, _ = retrieve_standards('请检查规范1000', rows)
        self.assertEqual(result[0]['standard_id'], '1000')

    def test_context_bound_and_source_unchanged(self):
        rows = [rule(i, '消防器材检查。' * 300) for i in range(1, 200)]
        before = json.dumps(rows)
        result, meta = retrieve_standards('消防器材缺失', rows)
        self.assertLessEqual(len(result), 60)
        self.assertLessEqual(len(json.dumps(result, ensure_ascii=False, separators=(',', ':'))), MAX_CONTEXT_CHARS)
        self.assertLessEqual(meta['candidate_chars'], MAX_CONTEXT_CHARS)
        self.assertEqual(json.dumps(rows), before)

    def test_tail_evidence_retained(self):
        text = '检查基础管理记录。' * 300 + '灭火器称重记录缺失，必须称重。'
        self.assertIn('称重', excerpt(text, '灭火器称重记录', 250))

    def test_cache_rebuild_on_edit_disable_or_restore(self):
        rows = [rule(1, '铅封管理'), rule(2, '灭火器称重')]
        retrieve_standards('灭火器称重', rows)
        retrieve_standards('灭火器称重', list(reversed(rows)))
        self.assertEqual(cached_index.cache_info().hits, 1)
        rows[0]['detail_text'] = '消防器材灭火器'
        retrieve_standards('灭火器称重', rows)
        self.assertEqual(cached_index.cache_info().misses, 2)
        result, _ = retrieve_standards('灭火器称重', rows[:1])
        self.assertNotIn('2', [r['standard_id'] for r in result])
        result, _ = retrieve_standards('灭火器称重', rows)
        self.assertIn('2', [r['standard_id'] for r in result])

    def test_no_evidence_does_not_call_ai_or_pick_generic(self):
        with patch.object(ai_utils, 'get_deepseek_client') as client:
            result = ai_utils.generate_standard_recommendations('abcdefg', [rule(1, '检查内容：其他')])
        client.assert_not_called()
        self.assertTrue(result['no_related'])
        self.assertFalse(result['generated'])

    def test_fast_rerank_whitelist_and_failure_fallback(self):
        client = MagicMock()
        client.with_options.return_value = client
        client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
            'no_related': False, 'recommendations': [{'standard_id': '1'}, {'standard_id': '999'}]
        })))])
        rows = [rule(1, '灭火器称重记录'), rule(2, '铅封管理')]
        with patch.object(ai_utils, 'get_deepseek_client', return_value=client):
            result = ai_utils.generate_standard_recommendations('灭火器无称重记录', rows)
        self.assertEqual([r['standard_id'] for r in result['recommendations']], ['1'])
        args = client.chat.completions.create.call_args.kwargs
        self.assertEqual(args['extra_body']['thinking']['type'], 'disabled')
        self.assertNotIn('reasoning_effort', args)
        client.with_options.assert_called_with(timeout=45, max_retries=0)
        client.chat.completions.create.side_effect = TimeoutError('test timeout')
        response_cache._entries.clear()
        with patch.object(ai_utils, 'get_deepseek_client', return_value=client):
            result = ai_utils.generate_standard_recommendations('灭火器无称重记录', rows)
        self.assertFalse(result['generated'])
        self.assertEqual(result['recommendations'][0]['standard_id'], '1')
