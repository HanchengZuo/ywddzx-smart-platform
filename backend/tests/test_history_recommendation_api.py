import unittest
from unittest.mock import MagicMock, patch
import app as api
from standard_history import recommend_from_history


class HistoryRecommendationTests(unittest.TestCase):
    def test_high_similarity_only_and_result_cap(self):
        description = '二氧化碳灭火器没有称重记录'
        catalog = [dict(standard_id=str(i), detail_text=description) for i in range(9)]
        history = tuple((i, str(i), description, i, i) for i in range(9))
        result = recommend_from_history(description, catalog, history)
        self.assertEqual(len(result['recommendations']), 6)
        self.assertFalse(result['generated'])
        self.assertFalse(recommend_from_history('便利店商品价格标签缺失', catalog, history)['recommendations'])
        self.assertFalse(recommend_from_history(description, [], history)['recommendations'])
        self.assertFalse(recommend_from_history(description, catalog, ())['recommendations'])

    def test_visible_field_projection_preserves_empty(self):
        fields = [dict(field_key='show', field_label='检查项目', is_register_visible=True),
                  dict(field_key='hide', field_label='检查内容', is_register_visible=False)]
        row = dict(standard_id=1, show='可显示', hide='隐藏字段')
        result = api.serialize_standard_row([(f['field_key'], f['field_label']) for f in fields], row,
                                            api.build_register_display_field_meta(fields))
        self.assertEqual(result['register_display_text'], '检查项目：可显示')
        self.assertEqual(api.serialize_standard_row([], row, [])['register_display_text'], '')

    def test_api_uses_current_user_and_never_calls_ai(self):
        user = {'id': 12, 'role': 'station', 'station_id': 3}
        standard = dict(standard_id='1', inspection_table_name='检查表', register_display_text='项目：显示字段')
        conn = MagicMock()
        with patch.object(api, 'get_current_request_user', return_value=user), \
             patch.object(api, 'get_db_connection', return_value=conn), \
             patch.object(api, 'ensure_inspection_checklist_management_schema'), \
             patch.object(api, 'ensure_internal_standard_schema'), \
             patch.object(api, 'has_permission', return_value=True) as permission, \
             patch.object(api, 'get_inspection_standard_usage_mode', return_value={'mode': 'external'}), \
             patch.object(api, 'build_inspection_standard_ai_catalog', return_value=([standard], [standard])), \
             patch.object(api, 'fetch_standard_history', return_value=((1, '1', '灭火器没有称重记录', 3, 1),)) as fetch, \
             patch.object(api, 'generate_standard_recommendations') as ai, \
             patch.object(api, 'record_ai_usage_log') as log:
            with api.app.test_request_context('/api/inspection-standards/history-recommend', method='POST',
                    json={'description': '灭火器没有称重记录', 'user_id': 999, 'standard_source_mode': 'internal'}):
                response = api.recommend_inspection_standard_by_history()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['items'][0]['register_display_text'], '项目：显示字段')
            self.assertEqual(fetch.call_args.args[1:3], (user, 'external'))
            ai.assert_not_called()
            log.assert_not_called()
            permission.return_value = False
            with api.app.test_request_context(json={'description': '灭火器没有称重记录'}):
                self.assertEqual(api.recommend_inspection_standard_by_history()[1], 403)
            self.assertEqual(fetch.call_count, 1)

    def test_api_requires_login_and_valid_description(self):
        with api.app.test_client() as client:
            self.assertEqual(client.post('/api/inspection-standards/history-recommend', json={'description': '灭火器没有称重记录'}).status_code, 401)
        for description in ('短', '长'*10001):
            with api.app.test_request_context(json={'description': description}):
                self.assertEqual(api.recommend_inspection_standard_by_history()[1], 400)
