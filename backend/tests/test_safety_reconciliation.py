import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from safety_report_analysis import (generate_analysis, validate_analysis, cached_analysis,
    effective_analysis, analysis_context)
from safety_report_reconciliation import reconcile, REPAIR_PROMPT, SINGLE_PROMPT
from safety_report_data import focus_topic_options


def issues(*ids):
    return [{'issue_id': i, 'description': f'问题{i}', 'topic': '设备设施',
        'category_name': '油罐操作井'} for i in ids]


def group(ids, name='连接缺失'):
    return {'name': name, 'summary': '接地连接缺失', 'issue_ids': ids}


def payload(groups):
    return {'groups': groups, 'causes': ['可能维护遗漏，需核实'], 'suggestions': []}


def completion(value):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(value)))])


class ReconciliationTest(unittest.TestCase):
    def test_valid_partition_needs_no_supplement(self):
        request = MagicMock(side_effect=AssertionError('unnecessary paid call'))
        result = reconcile({'issues': issues(8534, 9001)}, payload([group([8534, 9001])]), request)
        validate_analysis(result, issues(8534, 9001))
        request.assert_not_called()

    def test_numeric_strings_duplicate_membership_and_outside_refs_are_safe(self):
        request = MagicMock(side_effect=AssertionError('unnecessary paid call'))
        result = reconcile({'issues': issues(8534, 9001)}, payload([
            group(['8534', 8534, 999999]), group([9001])]), request)
        self.assertEqual(result['groups'][0]['issue_ids'], [8534, 9001])
        self.assertEqual(result['reconciliation']['duplicates_removed'], 1)
        self.assertEqual(result['reconciliation']['invalid_references'], 1)
        self.assertEqual(result['reconciliation']['normalized_ids'], 1)
        validate_analysis(result, issues(8534, 9001)); request.assert_not_called()

    def test_repair_only_missing_and_conflicting_with_server_owned_refs(self):
        context = {'mode': 'onsite', 'category': '设备设施', 'issues': issues(8534, 9001, 9010)}
        def request(prompt, evidence, tokens):
            self.assertEqual(prompt, REPAIR_PROMPT)
            self.assertEqual([row['reference'] for row in evidence['items']], ['R1', 'R2'])
            self.assertEqual([row['description'] for row in evidence['items']], ['问题9001', '问题9010'])
            self.assertTrue(all('issue_id' not in row for row in evidence['items']))
            return {'assignments': {'R1': {'name': '维护缺失', 'summary': '装置维护缺失'},
                'R2': {'name': '维护缺失', 'summary': '装置维护缺失'}, 'X': {'name': '伪造', 'summary': '无效'}}}
        result = reconcile(context, payload([group([8534, 9001]), group([9001], '另一类')]), request)
        validate_analysis(result, context['issues'])
        self.assertEqual(result['reconciliation']['missing_count'], 1)
        self.assertEqual(result['reconciliation']['conflict_count'], 1)
        self.assertEqual(result['groups'][0]['issue_ids'], [9001, 9010])

    def test_ordinal_guesses_are_not_interpreted_as_global_ids_and_single_fallback_is_bounded(self):
        calls = []
        def request(prompt, evidence, tokens):
            calls.append(prompt)
            if prompt == REPAIR_PROMPT: return {'assignments': {}}
            self.assertEqual(prompt, SINGLE_PROMPT)
            self.assertNotIn('issue_id', evidence)
            return {'name': '装置维护', 'summary': '装置缺少维护'}
        context = {'issues': issues(8534, 9001)}
        result = reconcile(context, payload([group([1, 2])]), request)
        validate_analysis(result, context['issues'])
        self.assertEqual(calls, [REPAIR_PROMPT, SINGLE_PROMPT, SINGLE_PROMPT])
        self.assertEqual(set(result['groups'][0]['issue_ids']), {8534, 9001})

    def test_unresolved_never_returns_partial_partition_and_has_request_limit(self):
        request = MagicMock(return_value={})
        with self.assertRaisesRegex(ValueError, '未完成核验'):
            reconcile({'issues': issues(*range(40))}, payload([]), request)
        self.assertEqual(request.call_count, 7)  # Four batches and at most three singles.

    def test_non_integer_refs_not_coerced_and_causes_are_recovered_separately(self):
        request = MagicMock(side_effect=[{'assignments': {'R1': {'name': '接地', 'summary': '接地缺失'}}},
            {'causes': ['可能检查遗漏，需核实']}])
        result = reconcile({'issues': issues(8534)}, {'groups': [group([8534.0, True])]}, request)
        validate_analysis(result, issues(8534))
        self.assertEqual(result['reconciliation']['invalid_references'], 2)
        self.assertEqual(request.call_count, 2)


class GenerationBoundaryTest(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock(); self.client.with_options.return_value = self.client
        self.context = analysis_context(issues(8534, 9001), 'onsite', '设备设施')

    def run_with_responses(self, responses):
        self.client.chat.completions.create.side_effect = [completion(value) for value in responses]
        with patch('ai_utils.get_deepseek_client', return_value=self.client), patch('ai_routing._loader', None):
            return generate_analysis(self.context)

    def test_supplemental_requests_are_counted_with_aggregated_cost_and_strict_final_validation(self):
        result = self.run_with_responses([payload([group([8534])]),
            {'assignments': {'R1': {'name': '装置维护', 'summary': '装置缺少维护'}}}])
        validate_analysis(result['payload'], self.context['issues'])
        self.assertEqual(result['usage']['request_count'], 2)
        self.assertEqual(result['usage']['repair_count'], 1)
        self.assertTrue(result['usage']['ai_called'])
        self.assertGreater(result['usage']['input_tokens_est'], 0)
        for call in self.client.with_options.call_args_list:
            self.assertEqual(call.kwargs['max_retries'], 0)
            self.assertLessEqual(call.kwargs['timeout'], 90)

    def test_network_failure_is_not_blindly_retried_and_preserves_failed_usage(self):
        self.client.chat.completions.create.side_effect = RuntimeError('provider unavailable')
        with patch('ai_utils.get_deepseek_client', return_value=self.client), patch('ai_routing._loader', None):
            with self.assertRaisesRegex(ValueError, '暂未完成分析') as error:
                generate_analysis(self.context)
        self.assertEqual(error.exception.ai_usage['request_count'], 1)
        self.assertFalse(error.exception.ai_usage['success'])
        self.assertEqual(self.client.chat.completions.create.call_count, 1)

    def test_deadline_blocks_new_requests(self):
        with patch('safety_report_analysis.time.monotonic', side_effect=[0, 0, 181]):
            with self.assertRaisesRegex(ValueError, '核验时限') as error:
                self.run_with_responses([payload([group([8534])])])
        self.assertEqual(error.exception.ai_usage['request_count'], 1)
        self.assertEqual(self.client.chat.completions.create.call_count, 1)


class ReadCoverageTest(unittest.TestCase):
    def test_partial_cached_batches_are_not_complete_even_with_manual_assignments(self):
        rows = issues(*range(41)); cur = MagicMock()
        cur.fetchone.side_effect = [{'payload': payload([group(list(range(40)))])}, None]
        value = cached_analysis(cur, rows, 'onsite', 'topic:设备设施')
        self.assertFalse(value['complete']); self.assertEqual(value['classified_count'], 40)
        edited = effective_analysis(value, rows, {'assignments': {'40': '人工'}})
        self.assertFalse(edited['complete'])
        self.assertEqual(sum(len(row['issue_ids']) for row in edited['groups']), 41)

    def test_topic_catalog_uses_field_labels_and_keeps_zero_count_choices(self):
        rows = [dict(row, mode='onsite') for row in issues(8534)]
        choices = focus_topic_options(rows, [{'name': '设备设施', 'label': '设备设施'},
            {'name': '其他隐患类', 'label': '其他对生产经营有影响的问题隐患'}])
        self.assertEqual(choices, [{'name': '设备设施', 'label': '设备设施', 'count': 1},
            {'name': '其他隐患类', 'label': '其他对生产经营有影响的问题隐患', 'count': 0}])
