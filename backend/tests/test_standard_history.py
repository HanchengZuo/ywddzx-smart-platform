import json
import os
import unittest
from unittest.mock import MagicMock, patch

import ai_utils
import standard_recommendation_cache as response_cache
from standard_history import cached_history_index, fetch_standard_history, match_history, normalize_description
from standard_retrieval import retrieve_standards


DESCRIPTION = '二氧化碳灭火器未按规定进行称重登记'


def rule(identifier='1', detail=DESCRIPTION):
    return {'standard_id': identifier, 'detail_text': detail, 'inspection_table_name': '消防检查'}


def history(description=DESCRIPTION, identifier='1'):
    return tuple((i, identifier, normalize_description(description), i, i) for i in range(1, 4))


class HistoryTests(unittest.TestCase):
    def setUp(self):
        cached_history_index.cache_clear()
        response_cache._entries.clear()

    def test_exact_consensus_skips_ai_and_charges_nothing(self):
        with patch.object(ai_utils, 'get_deepseek_client') as client:
            result = ai_utils.generate_standard_recommendations(DESCRIPTION, [rule()], history=history())
        client.assert_not_called()
        self.assertEqual(result['recommendation_source'], 'approved_history')
        self.assertFalse(result['generated'])
        self.assertFalse(result['usage']['ai_called'])
        self.assertEqual(result['usage']['total_cost_est'], 0)
        self.assertEqual(result['recommendations'][0]['standard_id'], '1')

    def test_insufficient_or_same_station_support_does_not_bypass_ai(self):
        for rows in (history()[:1], history()[:2], tuple((i, '1', DESCRIPTION, 1, i) for i in range(3)),
                     tuple((i, '1', DESCRIPTION, i, 1) for i in range(3))):
            self.assertIsNone(match_history(DESCRIPTION, [rule()], rows)['fast_recommendation'])

    def test_conflicting_references_remain_candidates(self):
        rows = history() + ((4, '2', DESCRIPTION, 4, 4),)
        result = match_history(DESCRIPTION, [rule(), rule('2')], rows)
        self.assertTrue(result['exact_conflict'])
        self.assertIsNone(result['fast_recommendation'])
        self.assertEqual(set(result['ranked_ids']), {'1', '2'})

    def test_no_short_or_generic_or_uncorroborated_fast_result(self):
        for text, detail in [('地面脏', '地面脏'), (DESCRIPTION, '检查内容：其他\n' + DESCRIPTION),
                             (DESCRIPTION, '便利店商品摆放')]:
            self.assertIsNone(match_history(text, [rule(detail=detail)], history(text))['fast_recommendation'])

    def test_normalization_preserves_safety_distinctions(self):
        self.assertEqual(normalize_description(' ＡＢＣ １２３\n'), 'abc 123')
        self.assertNotEqual(normalize_description('1 2'), normalize_description('12'))
        self.assertNotEqual(normalize_description('未核对铅封'), normalize_description('已核对铅封'))
        self.assertNotEqual(normalize_description('误差1.2'), normalize_description('误差12'))
        self.assertNotEqual(normalize_description('偏差-1'), normalize_description('偏差1'))

    def test_duplicate_descriptions_do_not_inflate_similarity(self):
        query = '灭火器没有称重登记'
        a = match_history(query, [rule()], history()[:1])
        b = match_history(query, [rule()], history())
        self.assertEqual(a['top_similarity'], b['top_similarity'])

    def test_refresh_when_history_is_edited_removed_or_rescoped(self):
        match_history(DESCRIPTION, [rule()], history())
        match_history(DESCRIPTION, [rule()], tuple(reversed(history())))
        self.assertEqual(cached_history_index.cache_info().hits, 1)
        changed = history()[:2] + ((3, '2', DESCRIPTION, 3, 3),)
        self.assertIsNone(match_history(DESCRIPTION, [rule(), rule('2')], changed)['fast_recommendation'])
        self.assertIsNone(match_history(DESCRIPTION, [rule()], history()[:1])['fast_recommendation'])
        self.assertFalse(match_history(DESCRIPTION, [rule('9')], history())['ranked_ids'])
        self.assertIsNone(match_history(DESCRIPTION, [rule(detail='商品库存管理')], history())['fast_recommendation'])

    def test_history_retrieves_rule_without_lexical_overlap(self):
        catalog = [rule('1', '油品外观密度检测'), rule('2', '消防器材')]
        experience = match_history('员工收油没有摇晃样品瓶', catalog, history('员工收油没有摇晃样品瓶'))
        candidates, meta = retrieve_standards('员工收油没有摇晃样品瓶', catalog, history_ids=experience['ranked_ids'])
        self.assertEqual(candidates[0]['standard_id'], '1')
        self.assertEqual(meta['method'], 'history-rrf-v1')

    def test_history_text_not_sent_to_ai(self):
        secret = '秘密站点二氧化碳灭火器缺少称重原始记录'
        with patch.object(ai_utils, '_generate_retrieved_standard_recommendations', return_value={'generated': True}) as generate:
            result = ai_utils.generate_standard_recommendations('灭火器缺少称重记录', [rule()], history=history(secret))
        self.assertNotIn('秘密站点', json.dumps(generate.call_args.args, ensure_ascii=False))
        self.assertNotIn('秘密站点', json.dumps(result, ensure_ascii=False))

    def test_completed_ai_response_reused_without_usage_and_invalidated_by_evidence(self):
        answer = {'generated': True, 'recommendations': [{'standard_id': '1'}]}
        with patch.object(ai_utils, '_generate_retrieved_standard_recommendations', return_value=answer.copy()) as generate:
            first = ai_utils.generate_standard_recommendations(DESCRIPTION, [rule()], history=history()[:1])
            second = ai_utils.generate_standard_recommendations(DESCRIPTION, [rule()], history=history()[:1])
            self.assertEqual(generate.call_count, 1)
            self.assertTrue(first['generated'])
            self.assertFalse(second['usage']['ai_called'])
            self.assertEqual(second['usage']['total_cost_est'], 0)
            self.assertEqual(second['recommendation_source'], 'ai_cache')
            ai_utils.generate_standard_recommendations(DESCRIPTION, [rule(detail=DESCRIPTION+'新规')], history=history()[:1])
            ai_utils.generate_standard_recommendations(DESCRIPTION, [rule()], history=history()[:2])
            self.assertEqual(generate.call_count, 3)

    def test_failures_not_cached_and_cache_bounded_expiring(self):
        response_cache.remember_recommendation('failed', {'generated': False})
        self.assertIsNone(response_cache.get_recommendation('failed'))
        with patch.object(response_cache, 'TTL_SECONDS', 0):
            response_cache.remember_recommendation('expired', {'generated': True})
        self.assertIsNone(response_cache.get_recommendation('expired'))
        with patch.object(response_cache, 'MAX_ENTRIES', 1):
            response_cache.remember_recommendation('a', {'generated': True, 'items': []})
            response_cache.remember_recommendation('b', {'generated': True, 'items': []})
        self.assertIsNone(response_cache.get_recommendation('a'))
        copy = response_cache.get_recommendation('b')
        copy['items'].append('mutated')
        self.assertEqual(response_cache.get_recommendation('b')['items'], [])

    def test_loader_uses_scope_current_ids_and_correct_mode(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [dict(id=1, reference_id='in1', description=DESCRIPTION, station_id=2, inspection_id=3),
                                       dict(id=2, reference_id='in2', description=DESCRIPTION, station_id=2, inspection_id=3)]
        scope = MagicMock(return_value=(['i.station_id=%s'], [2]))
        user = {'id': 8}
        result = fetch_standard_history(cursor, user, 'internal', [rule('IN1')], scope)
        scope.assert_called_once_with(cursor, user)
        sql, params = cursor.execute.call_args.args
        self.assertIn('i.internal_standard_id AS reference_id', sql)
        self.assertIn("i.audit_status='approved'", sql)
        self.assertIn("('已销毁','申诉中')", sql)
        self.assertEqual(params, [2])
        self.assertEqual([row[1] for row in result], ['IN1'])


@unittest.skipUnless(os.getenv('ISSUE_LIFECYCLE_DB_TEST') == '1', 'local database opt-in')
class HistoryDatabaseTests(unittest.TestCase):
    def setUp(self):
        import app
        self.conn = app.get_db_connection()
        self.cur = self.conn.cursor()
        self.cur.execute('''CREATE TEMP TABLE issues (id int, standard_id int, internal_standard_id text,
            description text, station_id int, inspection_id int, audit_status text, status text);
            CREATE TEMP TABLE inspections (id int); CREATE TEMP TABLE stations (id int);
            SET LOCAL search_path TO pg_temp;
            INSERT INTO stations VALUES(1),(2); INSERT INTO inspections VALUES(1);''')
        rows = [(1, 1, 'IN1', DESCRIPTION, 1, 1, 'approved', '待整改'),
                (2, 1, 'IN1', DESCRIPTION, 1, 1, 'pending', '待整改'),
                (3, 1, 'IN1', DESCRIPTION, 1, 1, 'rejected', '已销毁'),
                (4, 1, 'IN1', DESCRIPTION, 1, 1, 'approved', '申诉中'),
                (5, 1, 'IN1', DESCRIPTION, 1, 1, 'approved', '已销毁'),
                (6, 2, 'IN2', DESCRIPTION, 1, 1, 'approved', '已闭环'),
                (7, 1, 'IN1', DESCRIPTION, 2, 1, 'approved', '待整改')]
        self.cur.executemany('INSERT INTO issues VALUES(%s,%s,%s,%s,%s,%s,%s,%s)', rows)

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def test_status_and_scope_and_disabled_filtering_in_postgres(self):
        scope = lambda cur, user: (['i.station_id=%s'], [user['station_id']])
        for mode, identifier in [('external', '1'), ('internal', 'IN1')]:
            result = fetch_standard_history(self.cur, {'station_id': 1}, mode, [rule(identifier)], scope)
            self.assertEqual([row[0] for row in result], [1])
            result = fetch_standard_history(self.cur, {'station_id': 2}, mode, [rule(identifier)], scope)
            self.assertEqual([row[0] for row in result], [7])
