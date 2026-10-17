from datetime import date
import json
import unittest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

from expert_query import date_scope, infer_options, resolve_region, resolve_entities, explicit_issue_ids
from expert_conversations import load_context, parent_metadata
from expert_retrieval import chunks, ranked_chunks, select_evidence
from expert_knowledge import source, retrieve, business_evidence, knowledge_evidence
from expert_qa import normalize_answer


class QueryTests(unittest.TestCase):
    def test_default_is_all_history_and_relative_dates_use_beijing_calendar(self):
        today = date(2026, 10, 17)
        self.assertEqual(infer_options('有什么规范要求', today=today), {'date_from': '', 'date_to': '', 'region': ''})
        cases = {'本月问题数量': ('2026-10-01', '2026-10-17'), '上个月问题': ('2026-09-01', '2026-09-30'),
                 '最近7天的问题': ('2026-10-11', '2026-10-17'), '今天问题': ('2026-10-17', '2026-10-17'),
                 '2026年2月的问题': ('2026-02-01', '2026-02-28'), '7月8日的问题': ('2026-07-08', '2026-07-08'),
                 '2024年2月': ('2024-02-01', '2024-02-29'), '2026-08的问题': ('2026-08-01', '2026-08-31'),
                 '2026-07-01至2026-08-31': ('2026-07-01', '2026-08-31')}
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(date_scope(text, today)[:2], expected)

    def test_follow_up_inherits_only_recognized_data_conditions_and_explicit_reset_wins(self):
        previous = {'date_from': '2026-07-01', 'date_to': '2026-07-31', 'region': '浦东管理片区',
                    'station_names': ['国郃'], 'table_patterns': ['%非油%'], 'password': 'not-context'}
        options = infer_options('这些问题怎么处理', previous)
        self.assertEqual(options['station_names'], ['国郃'])
        self.assertEqual(options['region'], '浦东管理片区')
        self.assertNotIn('password', options)
        self.assertEqual(infer_options('查询全部历史、全部片区', previous)['date_from'], '')
        self.assertEqual(infer_options('查询全部历史、全部片区', previous)['region'], '')

    def test_invalid_ambiguous_dates_are_not_silently_miscounted(self):
        for text in ('2026年13月', '2026年2月30日', '2026年7月10日至2026年7月1日', '最近0天', '7月和8月对比'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                date_scope(text)

    def test_region_names_and_exact_issue_references(self):
        regions = ['浦东管理片区', '中油浦东公司', '南汇管理片区']
        self.assertEqual(resolve_region('浦东片区的问题', regions), '浦东管理片区')
        self.assertEqual(resolve_region('中油浦东公司的问题', regions), '中油浦东公司')
        self.assertEqual(resolve_region('全部片区的问题', regions, '南汇管理片区'), '')
        self.assertEqual(explicit_issue_ids('问题ID 6597 和问题 #6598，规范9000，2026年7月'), [6597, 6598])

    def test_changed_region_or_station_does_not_keep_a_conflicting_old_filter(self):
        stations = [{'station_name': '国郃', 'region': '浦东管理片区'}, {'station_name': '金山第二', 'region': '松金管理片区'}]
        previous = {'region': '浦东管理片区', 'station_names': ['国郃']}
        changed = resolve_entities('松金片区呢', previous, stations)
        self.assertEqual(changed['region'], '松金管理片区')
        self.assertNotIn('station_names', changed)
        self.assertEqual(resolve_entities('金山第二呢', previous, stations)['region'], '松金管理片区')
        self.assertNotIn('station_names', resolve_entities('看看全部片区', previous, stations))
        self.assertNotIn('station_names', resolve_entities('其他片区呢', previous, stations))
        with self.assertRaises(ValueError):
            resolve_entities('浦东片区金山第二的情况', previous, stations)


class RetrievalTests(unittest.TestCase):
    def test_old_relevant_file_beyond_first_80_is_prioritized_and_not_permanently_excluded(self):
        class File:
            def __init__(self, name):
                self.name = name
            def __str__(self):
                return self.name
            def stat(self):
                return SimpleNamespace(st_mtime_ns=1, st_size=10)
        files = [{'id': index, 'title': '常规文件', 'file_path': 'regular-' + str(index)} for index in range(80)]
        files.append({'id': 81, 'title': '稀有接地专题', 'file_path': 'target'})
        cur = MagicMock()
        cur.fetchall.side_effect = [[], files, [], []]
        core = SimpleNamespace(STORAGE_ROOT='/test-only', disabled_standard_ids=lambda cur: set(), fetch_external_standard_map=lambda cur: {})
        with patch('expert_knowledge.safe_file', side_effect=lambda root, relative: File(relative)), \
             patch('expert_knowledge.file_text', return_value=('可以提取的正文', '可读文本')) as extract:
            knowledge_evidence(core, cur, '稀有接地专题')
        self.assertEqual(extract.call_args_list[0].args[0], 'target')
        self.assertEqual(extract.call_count, 81)

    def test_long_document_tail_is_recalled_without_indexing_every_window(self):
        record = source('file:1', '检查表原件', '安全规程', '一般性要求。' * 9000 + '\n卸油前需要核对铅封号。', '')
        selected = chunks(record, '卸油前铅封核对')
        self.assertLessEqual(len(selected), 4)
        self.assertTrue(any('核对铅封号' in item['text'] for item in selected))
        self.assertTrue(all(item['parent_key'] == 'file:1' and item['locator'] for item in selected))

    def test_title_and_body_fuse_with_exact_id_and_source_diversity(self):
        records = [source('issue:100', '巡检问题', '问题100', '卸油铅封异常', ''),
                   source('external:9000', '外部规范', '卸油铅封核对规范', '规范要求', ''),
                   source('workflow:1', '系统流程说明', '问题整改流程', '卸油铅封问题的整改', '')]
        records += [source('issue:' + str(index), '巡检问题', '卸油铅封异常', '卸油铅封异常' * 30, '') for index in range(101, 130)]
        result = ranked_chunks('问题ID 100 卸油铅封异常有什么规范', records)
        self.assertEqual(result[0]['parent_key'], 'issue:100')
        self.assertIn('外部规范', {item['kind'] for item in result[:12]})
        self.assertIn('系统流程说明', {item['kind'] for item in result[:12]})

    def test_full_statistics_not_query_windowed_deduplicated_and_context_bounded(self):
        text = json.dumps({'完整数量': 8765, '待审核': 3400, '已通过': 5365}, ensure_ascii=False)
        stat = source('stats:issues', '数据库统计', '完整统计', text, '')
        records = [stat, stat] + [source('issue:' + str(i), '巡检问题', '铅封', '铅封检查。' * 500, '') for i in range(100)]
        result = select_evidence('铅封', records)
        self.assertEqual(result[0]['text'], text)
        self.assertEqual(len([row for row in result if row['key'] == 'stats:issues']), 1)
        self.assertLessEqual(len(result), 24)
        self.assertLessEqual(sum(len(row['text']) + len(row['title']) + 200 for row in result), 24000)

    def test_years_do_not_become_exact_issue_or_standard_id_boosts(self):
        records = [source('issue:2026', '巡检问题', '无关', '没有命中内容', ''),
                   source('workflow:1', '系统流程说明', '2026年铅封规定', '铅封规定', '')]
        result = ranked_chunks('2026年铅封有什么规定', records)
        self.assertEqual(result[0]['parent_key'], 'workflow:1')

    def test_normative_questions_do_not_get_unrelated_live_issue_totals(self):
        records = [source('stats:issues', '数据库统计', '问题总量', '9999条问题', ''),
                   source('external:1', '外部规范', '铅封核对规范', '卸油前核对铅封', '')]
        result = select_evidence('铅封核对有什么规范要求', records)
        self.assertFalse(any(row['key'] == 'stats:issues' for row in result))
        self.assertEqual(result[0]['parent_key'], 'external:1')

    def test_retrieval_scope_is_derived_from_current_question_not_old_context_terms(self):
        cur = MagicMock()
        cur.fetchall.return_value = [{'station_name': '国郃', 'region': '浦东管理片区'}, {'station_name': '金山第二', 'region': '松金管理片区'}]
        with patch('expert_knowledge.business_evidence', return_value=[]) as business, \
             patch('expert_knowledge.knowledge_evidence', return_value=([], [])):
            _, info = retrieve(SimpleNamespace(), cur, '松金片区问题\n浦东片区问题', infer_options('松金片区问题'), current_question='松金片区问题')
        self.assertEqual(info['options']['region'], '松金管理片区')
        self.assertEqual(business.call_args.args[-1]['region'], '松金管理片区')

    def test_exact_issue_lookup_is_bound_and_does_not_depend_on_newest_160_keyword_rows(self):
        cur = MagicMock()
        cur.fetchone.return_value = {'registered': 1}
        cur.fetchall.return_value = []
        business_evidence(SimpleNamespace(), cur, '问题ID 6597 的处理过程', infer_options('问题ID 6597 的处理过程'))
        exact = [call for call in cur.execute.call_args_list if 'WHERE i.id=ANY(%s) ORDER BY i.id' in call.args[0]]
        self.assertEqual(len(exact), 1)
        self.assertEqual(exact[0].args[1], [[6597]])


class ConversationTests(unittest.TestCase):
    def test_multiple_turns_are_owned_bounded_and_old_citations_not_reused(self):
        cur = MagicMock()
        a, b = 'a' * 32, 'b' * 32
        cur.fetchone.side_effect = [
            {'id': b, 'question': '那如何整改', 'options': {'parent_id': a, 'conversation_id': a},
             'result': {'answer': {'paragraphs': [{'text': '旧答案', 'sources': ['S99']}]} , 'retrieval': {'scope_version': 2, 'options': {'region': '浦东管理片区'}}}},
            {'id': a, 'question': '铅封有什么规定', 'options': {}, 'result': {'answer': {'paragraphs': [{'text': '核对铅封'}]}}},
        ]
        result = load_context(cur, 17, 'owned-session', b)
        self.assertEqual([turn['question'] for turn in result['turns']], ['铅封有什么规定', '那如何整改'])
        self.assertEqual(result['options']['region'], '浦东管理片区')
        self.assertNotIn('S99', json.dumps(result))
        for call in cur.execute.call_args_list:
            self.assertIn('user_id=%s AND session_key=%s', call.args[0])
            self.assertEqual(call.args[1][1:], [17, 'owned-session'])

    def test_foreign_or_corrupt_ancestry_never_falls_back_to_unowned_data(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        with self.assertRaises(ValueError):
            load_context(cur, 17, 'session', 'a' * 32)
        cur.fetchone.return_value = {'id': 'a' * 32, 'question': '历史', 'options': {'parent_id': 'a' * 32}, 'result': {}}
        with self.assertRaises(ValueError):
            load_context(cur, 17, 'session', 'a' * 32)

    def test_old_hidden_ui_filters_do_not_limit_new_follow_ups(self):
        cur = MagicMock()
        cur.fetchone.return_value = {'id': 'a' * 32, 'question': '规范有哪些要求',
            'options': {'date_from': '2020-01-01', 'date_to': '2020-01-31', 'region': '浦东管理片区'},
            'result': {'answer': {'paragraphs': []}, 'retrieval': {'options': {'region': '浦东管理片区'}}}}
        self.assertEqual(load_context(cur, 17, 'session', 'a' * 32)['options'], {'date_from': '', 'date_to': '', 'region': ''})

    def test_titles_and_follow_up_suggestions_are_plain_bounded_text(self):
        answer = normalize_answer({'paragraphs': [{'title': '结论', 'text': '有据结论', 'sources': ['S1']}],
            'follow_up_questions': ['如何处理？', '如何处理？', '<script>test</script>', {'invalid': 'value'}, 'a']}, [{'id': 'S1'}])
        self.assertEqual(answer['paragraphs'][0]['title'], '结论')
        self.assertEqual(answer['follow_up_questions'], ['如何处理？', '<script>test</script>'])
        self.assertEqual(parent_metadata({'id': 'a' * 32, 'options': {}}), 'a' * 32)
