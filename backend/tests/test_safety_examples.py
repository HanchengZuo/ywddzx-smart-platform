import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from safety_report_examples import (validate_selections, with_representatives, cached_representatives,
    apply_representative_overrides, generate_representatives, reconcile_selections, REPAIR_PROMPT, SINGLE_PROMPT)
from safety_report_analysis import photo_examples, normalize_settings
from report_ai_memory import fingerprint


def issue(i):
    return {'issue_id':i,'issue_photo':'photo.jpg','description':f'接地未有效连接{i}',
        'station_name':f'测试{i}','category_name':'设备设施'}


def selection(context):
    return {'selections':[{'name':g['name'],'issue_ids':[r['issue_id'] for r in reversed(g['issues'])][:6]}
        for g in context['groups']], 'selection_signature':fingerprint(context)}


class RepresentativeTest(unittest.TestCase):
    def test_ai_ranks_all_candidates_in_bounded_batches_and_reranks_finalists(self):
        rows=[issue(i) for i in range(1,87)]
        value={'complete':True,'groups':[{'name':'接地缺失','summary':'接地连接不规范','issue_ids':list(range(1,87))}]}
        with patch('safety_report_examples.generate_representatives',side_effect=lambda c:{'payload':selection(c)}) as ai:
            result=with_representatives(value,rows,'onsite','设备设施')
        self.assertTrue(result['representatives_ready'])
        self.assertEqual(ai.call_count,4)
        self.assertTrue(all(sum(len(g['issues']) for g in call.args[0]['groups'])<=40 for call in ai.call_args_list))
        self.assertEqual(result['groups'][0]['representative_issue_ids'],[81,82,83,84,85,86])
        self.assertNotIn('representative_issue_ids',value['groups'][0])

    def test_read_cached_rankings_never_calls_ai_and_requires_same_classification_evidence(self):
        rows=[issue(1),issue(2)]
        analysis={'complete':True,'groups':[{'name':'接地','summary':'接地不规范','issue_ids':[1,2]}]}
        store={}
        def collect(context):
            result=selection(context);store[fingerprint(context)]=result
            return {'payload':result}
        with patch('safety_report_examples.generate_representatives',side_effect=collect):
            generated=with_representatives(analysis,rows,'onsite','topic:设备设施')
        cur=MagicMock()
        def execute(sql,params):cur.fetchone.return_value={'payload':store[params[0]]} if params[0] in store else None
        cur.execute.side_effect=execute
        with patch('safety_report_examples.generate_representatives',side_effect=AssertionError('paidAI')):
            self.assertEqual(cached_representatives(cur,analysis,rows,'onsite','设备设施'),generated)
            changed=copy.deepcopy(analysis);changed['groups'][0]['summary']='人工已修改的共性描述'
            self.assertFalse(cached_representatives(cur,changed,rows,'onsite','设备设施')['representatives_ready'])
            self.assertFalse(cached_representatives(cur,{**analysis,'complete':False},rows,'onsite','设备设施')['representatives_ready'])

    def test_references_must_match_their_own_group_unique_exact_integer_and_expected_count(self):
        context={'groups':[{'name':'A','issues':[issue(1),issue(2)]},{'name':'B','issues':[issue(3)]}]}
        valid={'selections':[{'name':'A','issue_ids':[2,1]},{'name':'B','issue_ids':[3]}]}
        validate_selections(valid,context)
        for replacements in ([1,3],[1,1],['1',2],[1],[],[1,2,3]):
            bad=copy.deepcopy(valid);bad['selections'][0]['issue_ids']=replacements
            with self.assertRaises(ValueError):validate_selections(bad,context)
        bad=copy.deepcopy(valid);bad['selections'][1]['name']='A'
        with self.assertRaises(ValueError):validate_selections(bad,context)

    def test_manual_picks_override_ai_without_leaking_between_classes_or_duplicating_photos(self):
        rows=[issue(i) for i in range(1,8)]
        analysis={'groups':[{'name':'A','summary':'A','issue_ids':[1,2,3,4],'representative_issue_ids':[4,3,2,1]},
            {'name':'B','summary':'B','issue_ids':[5,6],'representative_issue_ids':[6,5]},
            {'name':'C','summary':'C','issue_ids':[7],'representative_issue_ids':[7]}]}
        actual=apply_representative_overrides(analysis,rows,{'representatives':{'A':[1],'B':[2,5]}})
        self.assertEqual(actual['groups'][0]['representative_issue_ids'],[1,4,3,2])
        self.assertEqual(actual['groups'][1]['representative_issue_ids'],[5,6])
        self.assertEqual([r['issue_id'] for r in photo_examples(rows,actual,3,distinct_groups=True)],[1,5,7])
        six=photo_examples(rows,actual,6)
        self.assertEqual([r['issue_id'] for r in six],[1,5,7,4,6,3])
        self.assertEqual(len({r['issue_id'] for r in six}),6)
        self.assertNotIn('representative_source',analysis['groups'][0])

    def test_empty_photo_sources_do_not_call_ai_or_invent_examples(self):
        rows=[{**issue(1),'issue_photo':''}]
        analysis={'complete':True,'groups':[{'name':'A','summary':'A','issue_ids':[1]}]}
        with patch('safety_report_examples.generate_representatives',side_effect=AssertionError('paidAI')):
            result=with_representatives(analysis,rows,'onsite','设备设施')
        self.assertTrue(result['representatives_ready'])
        self.assertEqual(photo_examples(rows,result,3),[])

    def test_manual_selection_input_validation_and_normalization(self):
        raw={'classifications':{'onsite:设备设施':{'representatives':{'接地':[1,2]}}}}
        self.assertEqual(normalize_settings(raw)['classifications'],raw['classifications'])
        self.assertEqual(normalize_settings({'classifications':{'onsite:设备设施':{'representatives':{'接地':[]}}}})['classifications']['onsite:设备设施']['representatives']['接地'],[])
        for ids in ([1,1],['1'],list(range(7))):
            with self.assertRaises(ValueError):normalize_settings({'classifications':{'onsite:设备设施':{'representatives':{'接地':ids}}}})


class _RepresentativeFixture:
    def setUp(self):
        # Same shape as the failed October batch: 18 classes, 21 candidates,
        # including many singleton classes that the model must not omit.
        self.context = {'mode':'onsite', 'category':'设备设施', 'stage':0, 'groups':[]}
        next_id = 8534
        for index in range(18):
            size = 2 if index < 3 else 1
            self.context['groups'].append({'name':f'表现{index}', 'summary':f'共性{index}',
                'issues':[issue(i) for i in range(next_id,next_id+size)]})
            next_id += size
        self.full = selection(self.context)


class RepresentativeRepairTest(_RepresentativeFixture, unittest.TestCase):
    def test_valid_rankings_are_not_reselected_and_missing_singleton_is_repaired(self):
        partial = copy.deepcopy(self.full)
        missing = partial['selections'].pop()
        def request(prompt,evidence,tokens):
            self.assertEqual(prompt,REPAIR_PROMPT)
            self.assertEqual(len(evidence['items']),1)
            self.assertEqual(evidence['items'][0]['name'],missing['name'])
            self.assertEqual(evidence['items'][0]['reference'],'G1')
            return {'selections':{'G1':missing['issue_ids']}}
        result = reconcile_selections(partial,self.context,request)
        self.assertEqual(result['selections'],self.full['selections'])
        self.assertEqual(result['reconciliation']['missing_count'],1)
        self.assertEqual(result['reconciliation']['repaired_groups'],1)

    def test_invalid_duplicate_and_out_of_class_picks_are_repaired_not_guessed(self):
        partial=copy.deepcopy(self.full)
        partial['selections'][0]['issue_ids']=self.full['selections'][1]['issue_ids']
        partial['selections'].append(copy.deepcopy(partial['selections'][1]))
        partial['selections'].append({'name':['invalid'],'issue_ids':[1]})
        calls=[]
        def request(prompt,evidence,tokens):
            calls.append(evidence)
            return {'selections':{row['reference']:list(reversed([r['issue_id'] for r in row['issues']]))[:6]
                for row in evidence['items']}}
        result=reconcile_selections(partial,self.context,request)
        self.assertEqual([row['name'] for row in calls[0]['items']],['表现0','表现1'])
        self.assertEqual(result['selections'],self.full['selections'])
        self.assertEqual(result['reconciliation']['duplicate_groups'],1)

    def test_repair_references_are_server_owned_and_never_interpreted_as_ordinals(self):
        context={'mode':'onsite','category':'设备设施','groups':self.context['groups'][:2]}
        def request(prompt,evidence,tokens):
            if prompt==REPAIR_PROMPT:
                return {'selections':{'G1':[1,2], 'G2':self.full['selections'][1]['issue_ids'],
                    'invented':self.full['selections'][0]['issue_ids']}}
            self.assertEqual(prompt,SINGLE_PROMPT)
            self.assertEqual(evidence['name'],'表现0')
            return {'issue_ids':self.full['selections'][0]['issue_ids']}
        result=reconcile_selections(None,context,request)
        validate_selections(result,context)
        self.assertEqual(result['reconciliation']['supplemental_requests'],2)

    def test_unresolved_repair_is_bounded_and_never_returns_partial_rankings(self):
        request=MagicMock(return_value={})
        with self.assertRaisesRegex(ValueError,'18个类别未完成核验.*现场 / 设备设施'):
            reconcile_selections(None,self.context,request)
        self.assertEqual(request.call_count,5)  # Three batches of eight, then at most two singles.
        self.assertEqual(sum(call.args[0]==SINGLE_PROMPT for call in request.call_args_list),2)


class RepresentativeGenerationTest(_RepresentativeFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.client=MagicMock()
        self.client.with_options.return_value=self.client

    def run_responses(self, values):
        self.client.chat.completions.create.side_effect=[SimpleNamespace(choices=[
            SimpleNamespace(message=SimpleNamespace(content=json.dumps(value)))]) for value in values]
        with patch('ai_utils.get_deepseek_client',return_value=self.client), patch('ai_routing._loader',None):
            return generate_representatives(self.context)

    def test_valid_response_uses_one_call_and_retains_existing_signature(self):
        result=self.run_responses([self.full])
        self.assertEqual(result['usage']['request_count'],1)
        self.assertEqual(result['usage']['repair_count'],0)
        self.assertEqual(result['payload']['selection_signature'],fingerprint(self.context))
        self.assertEqual(self.client.chat.completions.create.call_count,1)

    def test_missing_group_supplement_is_counted_and_final_result_is_strictly_valid(self):
        partial=copy.deepcopy(self.full);missing=partial['selections'].pop()
        result=self.run_responses([partial,{'selections':{'G1':missing['issue_ids']}}])
        self.assertEqual(result['payload']['selections'],self.full['selections'])
        self.assertEqual(result['usage']['request_count'],2)
        self.assertEqual(result['usage']['repair_count'],1)
        self.assertTrue(result['usage']['success'])
        self.assertGreater(result['usage']['input_tokens_est'],0)
        self.assertGreater(result['usage']['output_tokens_est'],0)
        for call in self.client.with_options.call_args_list:
            self.assertEqual(call.kwargs['max_retries'],0)
            self.assertLessEqual(call.kwargs['timeout'],90)

    def test_network_failure_is_not_retried_and_failed_request_is_counted(self):
        self.client.chat.completions.create.side_effect=RuntimeError('provider unavailable')
        with patch('ai_utils.get_deepseek_client',return_value=self.client), patch('ai_routing._loader',None):
            with self.assertRaisesRegex(ValueError,'暂未完成') as error:
                generate_representatives(self.context)
        self.assertEqual(error.exception.ai_usage['request_count'],1)
        self.assertFalse(error.exception.ai_usage['success'])
        self.assertEqual(self.client.chat.completions.create.call_count,1)

    def test_deadline_prevents_additional_calls_and_preserves_usage(self):
        with patch('safety_report_examples.time.monotonic',side_effect=[0,0,181]):
            with self.assertRaisesRegex(ValueError,'核验时限') as error:
                self.run_responses([{'selections':[]}])
        self.assertEqual(error.exception.ai_usage['request_count'],1)
        self.assertEqual(self.client.chat.completions.create.call_count,1)

    def test_persistently_invalid_response_is_not_reported_as_success(self):
        with self.assertRaisesRegex(ValueError,'未完成核验') as error:
            self.run_responses([{}]*6)
        self.assertEqual(error.exception.ai_usage['request_count'],6)
        self.assertEqual(error.exception.ai_usage['repair_count'],5)
        self.assertFalse(error.exception.ai_usage['success'])
