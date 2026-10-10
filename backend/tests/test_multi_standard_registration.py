import json
import os
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from flask import Flask, g
from PIL import Image
import app as api
from inspection_registration import parse_standard_selections


class SelectionTests(unittest.TestCase):
    def test_legacy_and_cross_table_selections(self):
        self.assertEqual(parse_standard_selections({'standard_id': '001', 'inspection_table_id': '2'}), [{'standard_id': '1', 'inspection_table_id': '2'}])
        self.assertEqual(parse_standard_selections({'internal_standard_id': 'n1'}), [{'internal_standard_id': 'N1'}])
        rows = [{'standard_id': '1', 'inspection_table_id': '2'}, {'standard_id': '3', 'inspection_table_id': '4'}, {'standard_id': '1', 'inspection_table_id': '2'}]
        self.assertEqual(len(parse_standard_selections({'standards': json.dumps(rows)})), 2)

    def test_invalid_and_mixed_selection_shapes(self):
        for value in ('bad json', '{}', '[]', '[1]', '[{}]', '[{"standard_id":"abc"}]',
                      '[{"standard_id":"1","internal_standard_id":"N1"}]',
                      json.dumps([{'standard_id': str(i+1)} for i in range(101)]),
                      '[{"standard_id":"1","inspection_table_id":"2"},{"standard_id":"01","inspection_table_id":"3"}]'):
            with self.subTest(value=value[:80]), self.assertRaises(ValueError):
                parse_standard_selections({'standards': value})

    def test_resolution_is_authoritative_and_rejects_any_invalid_target(self):
        rows = {1: {'external_standard_id': 1, 'inspection_table_id': 2, 'standard_detail_text': '规范1'},
                3: {'external_standard_id': 3, 'inspection_table_id': 4, 'standard_detail_text': '规范3'}}
        with patch.object(api, 'fetch_external_standard_map', return_value=rows), \
             patch.object(api, 'fetch_internal_links_by_external_ids', return_value={}), \
             patch.object(api, 'require_active_standards') as active:
            selections = parse_standard_selections({'standards': '[{"standard_id":"1"},{"standard_id":"3"}]'})
            resolved = api.resolve_registration_standards(None, selections, 'external')
            self.assertEqual([row['inspection_table_id'] for row in resolved], [2, 4])
            active.assert_called_once_with(None, [1, 3])
            with self.assertRaisesRegex(ValueError, '不一致'):
                api.resolve_registration_standards(None, [{'standard_id': '1', 'inspection_table_id': '4'}], 'external')
            with self.assertRaisesRegex(ValueError, '不存在'):
                api.resolve_registration_standards(None, [{'standard_id': '9'}], 'external')
            with self.assertRaisesRegex(ValueError, '已变更'):
                api.resolve_registration_standards(None, selections, 'internal')
            active.side_effect = ValueError('规范已停用')
            with self.assertRaisesRegex(ValueError, '停用'):
                api.resolve_registration_standards(None, selections, 'external')

    def test_internal_expansion_deduplicates_and_preserves_snapshots(self):
        external = {1: {'external_standard_id': 1, 'inspection_table_id': 2, 'standard_detail_text': '外部'},
                    3: {'external_standard_id': 3, 'inspection_table_id': 4, 'standard_detail_text': '外部3'}}
        with patch.object(api, 'fetch_internal_standard_by_code', return_value=({'internal_standard_id': 'N1', 'content': '内部'}, [], [{'external_standard_id': 1}, {'external_standard_id': 3}, {'external_standard_id': 1}])), \
             patch.object(api, 'fetch_external_standard_map', return_value=external), \
             patch.object(api, 'require_active_standards'):
            resolved = api.resolve_registration_standards(None, [{'internal_standard_id': 'N1'}], 'internal')
            self.assertEqual(len(resolved), 2)
            self.assertEqual(resolved[0]['internal_standard_detail_text'], '内部')

    def test_lock_order_is_stable_and_finished_inspection_blocks_batch(self):
        entries = [{'external_standard_id': 3, 'inspection_table_id': 4}, {'external_standard_id': 1, 'inspection_table_id': 2}]
        with patch.object(api, 'get_inspection_completion_config', return_value={'record_uniqueness_period': 'monthly'}), \
             patch.object(api, 'lock_inspection_period_scope') as lock, \
             patch.object(api, 'get_inspection_table_record', return_value={'is_active': True, 'table_name': '现场'}), \
             patch.object(api, 'find_period_inspection', return_value={'id': 8, 'inspector_completion_status': api.INSPECTION_COMPLETION_DONE}):
            with self.assertRaisesRegex(ValueError, '不能继续登记'):
                api.prepare_issue_registration_targets(None, 1, 1, entries, 1, api.beijing_today())
            self.assertEqual([call.args[2] for call in lock.call_args_list], [2, 4])

    def test_unauthenticated_registration_is_rejected(self):
        with api.app.test_client() as client:
            self.assertEqual(client.post('/api/inspection-register', data={'station_id': '1'}).status_code, 401)


@unittest.skipUnless(os.getenv('ISSUE_LIFECYCLE_DB_TEST') == '1', 'local transaction-only database opt-in')
class RegistrationDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.conn = api.get_db_connection()
        self.cur = self.conn.cursor()
        self.cur.execute('''CREATE TEMP TABLE users(id integer, username text, role text, real_name text);
            CREATE TEMP TABLE stations(id integer, station_name text);
            CREATE TEMP TABLE inspections(id serial PRIMARY KEY, station_id integer, inspector_id integer,
              inspection_table_id integer, batch_id integer, inspection_date date, inspector_completion_status text, inspector_completed_at timestamp);
            CREATE TEMP TABLE issues(id serial PRIMARY KEY, inspection_id integer, inspector_id integer, station_id integer,
              inspection_table_id integer, standard_id bigint, standard_detail_text text, internal_standard_id text,
              internal_standard_detail_text text, description text, photo_path text, status text);
            SET LOCAL search_path TO pg_temp;
            INSERT INTO users VALUES(7,'inspector','supervisor','检查人');
            INSERT INTO stations VALUES(1,'测试站'); SAVEPOINT registration;''')
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.rows = {1: {'external_standard_id': 1, 'inspection_table_id': 2, 'standard_detail_text': '规范1'},
                     3: {'external_standard_id': 3, 'inspection_table_id': 4, 'standard_detail_text': '规范3'},
                     5: {'external_standard_id': 5, 'inspection_table_id': 2, 'standard_detail_text': '规范5'}}
        def create(cur, station, inspector, table, batch, today=None):
            cur.execute('INSERT INTO inspections(station_id,inspector_id,inspection_table_id,batch_id,inspection_date) VALUES(%s,%s,%s,%s,%s) RETURNING id', (station,inspector,table,batch,today or api.beijing_today()))
            return cur.fetchone()['id']
        self.permission = True
        self.patches = [patch.object(api, name) for name in ('ensure_inspection_checklist_management_schema', 'ensure_internal_standard_schema',
                        'ensure_issue_inspector_schema','ensure_inspection_completion_schema','auto_complete_overdue_inspections','close_db_resources')]
        self.patches += [
            patch.object(api, 'get_db_connection', return_value=SimpleNamespace(cursor=self.conn.cursor, commit=lambda: None, rollback=lambda: self.cur.execute('ROLLBACK TO SAVEPOINT registration'))),
            patch.object(api, 'has_permission', side_effect=lambda *args: self.permission),
            patch.object(api, 'get_inspection_standard_usage_mode', return_value={'mode': 'external'}),
            patch.object(api, 'get_or_create_inspection_batch', return_value=1),
            patch.object(api, 'get_inspection_completion_config', return_value={'record_uniqueness_period': 'monthly'}),
            patch.object(api, 'get_inspection_table_record', side_effect=lambda cur,table: {'is_active': True, 'table_name': '表'+str(table), 'table_code': 'test'}),
            patch.object(api, 'fetch_external_standard_map', return_value=self.rows),
            patch.object(api, 'fetch_internal_links_by_external_ids', return_value={}),
            patch.object(api, 'require_active_standards'),
            patch.object(api, 'create_inspection_record', side_effect=create),
            patch.object(api, 'mark_related_plan_items_completed'),
            patch.object(api, 'STORAGE_ROOT', self.folder.name),
            patch.object(api, 'ISSUES_STORAGE_DIR', os.path.join(self.folder.name, 'issues')),
        ]
        for item in self.patches: item.start()
        self.addCleanup(lambda: [item.stop() for item in reversed(self.patches)])
        app = Flask('registration_batch_test')
        @app.before_request
        def user(): g.current_user = {'id': 7, 'role': 'supervisor'}
        app.add_url_rule('/register', view_func=api.inspection_register, methods=['POST'])
        self.client = app.test_client()

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def post(self, selections=None, **kwargs):
        image = BytesIO(); Image.new('RGB', (60, 40), 'blue').save(image, format='PNG'); image.seek(0)
        data = {'station_id': '1', 'inspector_id': '999', 'description': '同一处现场问题', 'photo': (image, 'photo.png'), **kwargs}
        if selections is not None: data['standards'] = json.dumps(selections)
        return self.client.post('/register', data=data)

    def test_batch_creates_independent_issues_files_and_correct_inspections(self):
        response = self.post([{'standard_id': '1'}, {'standard_id': '3'}, {'standard_id': '5'}, {'standard_id': '1'}])
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['created_count'], 3)
        self.cur.execute('SELECT * FROM issues ORDER BY id'); rows = self.cur.fetchall()
        self.assertEqual([row['standard_id'] for row in rows], [1, 3, 5])
        self.assertEqual({row['inspector_id'] for row in rows}, {7})
        self.assertEqual({row['description'] for row in rows}, {'同一处现场问题'})
        self.assertEqual(rows[0]['inspection_id'], rows[2]['inspection_id'])
        self.assertNotEqual(rows[0]['inspection_id'], rows[1]['inspection_id'])
        paths = [api.resolve_storage_abs_path(row['photo_path']) for row in rows]
        self.assertEqual(len(set(paths)), 3)
        self.assertEqual(len({Path(path).read_bytes() for path in paths}), 1)
        api.remove_storage_file(rows[0]['photo_path'])
        self.assertTrue(Path(paths[1]).exists())
        self.assertTrue(Path(paths[2]).exists())

    def test_late_insert_failure_rolls_back_rows_and_all_photos(self):
        original = self.conn.cursor
        def cursor():
            cur = original()
            def execute(query, params=None):
                if 'INSERT INTO issues' in str(query) and params[4] == 3:
                    raise RuntimeError('private database failure')
                cur.execute(query, params)
            return SimpleNamespace(execute=execute, fetchone=cur.fetchone, fetchall=cur.fetchall)
        with patch.object(api, 'get_db_connection', return_value=SimpleNamespace(cursor=cursor, commit=lambda: None, rollback=lambda:self.cur.execute('ROLLBACK TO SAVEPOINT registration'))):
            response = self.post([{'standard_id': '1'}, {'standard_id': '3'}])
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('private database', response.json['error'])
        self.cur.execute('SELECT count(*) AS n FROM issues'); self.assertEqual(self.cur.fetchone()['n'], 0)
        self.cur.execute('SELECT count(*) AS n FROM inspections'); self.assertEqual(self.cur.fetchone()['n'], 0)
        self.assertEqual(list(Path(self.folder.name).rglob('*.jpg')), [])

    def test_legacy_single_submission_and_permission_denial(self):
        self.assertEqual(self.post(standard_id='1', inspection_table_id='2').status_code, 200)
        self.permission = False
        self.assertEqual(self.post([{'standard_id': '3'}]).status_code, 403)
        self.cur.execute('SELECT count(*) AS n FROM issues'); self.assertEqual(self.cur.fetchone()['n'], 1)

    def test_invalid_target_prevents_all_inserts(self):
        for selections in ([{'standard_id':'1'},{'standard_id':'999'}], [{'standard_id':'1','inspection_table_id':'4'}]):
            response = self.post(selections)
            self.assertEqual(response.status_code, 400, response.json)
        self.cur.execute('SELECT count(*) AS n FROM issues'); self.assertEqual(self.cur.fetchone()['n'], 0)
        self.assertEqual(list(Path(self.folder.name).rglob('*.jpg')), [])

    def test_completed_table_blocks_whole_batch(self):
        self.cur.execute('INSERT INTO inspections(station_id,inspection_table_id,inspection_date,inspector_completion_status) VALUES(1,4,%s,%s)', (api.beijing_today(), api.INSPECTION_COMPLETION_DONE))
        self.cur.execute('RELEASE SAVEPOINT registration; SAVEPOINT registration')
        response = self.post([{'standard_id': '1'}, {'standard_id': '3'}])
        self.assertEqual(response.status_code, 400)
        self.assertIn('不能继续登记', response.json['error'])
        self.cur.execute('SELECT count(*) AS n FROM issues'); self.assertEqual(self.cur.fetchone()['n'], 0)
        self.cur.execute('SELECT count(*) AS n FROM inspections'); self.assertEqual(self.cur.fetchone()['n'], 1)
        self.assertEqual(list(Path(self.folder.name).rglob('*.jpg')), [])

    def test_multiple_internal_choices_create_distinct_external_issues(self):
        def internal(cur, code):
            ids = [1, 5] if code == 'N1' else [3]
            return {'internal_standard_id': code, 'content': code+'内部详情'}, [], [{'external_standard_id': id} for id in ids]
        with patch.object(api, 'get_inspection_standard_usage_mode', return_value={'mode': 'internal'}), \
             patch.object(api, 'fetch_internal_standard_by_code', side_effect=internal):
            response = self.post([{'internal_standard_id': 'N1'}, {'internal_standard_id': 'N2'}])
        self.assertEqual(response.status_code, 200, response.json)
        self.cur.execute('SELECT standard_id,internal_standard_id,internal_standard_detail_text FROM issues ORDER BY standard_id')
        self.assertEqual([(row['standard_id'], row['internal_standard_id']) for row in self.cur.fetchall()], [(1, 'N1'), (3, 'N2'), (5, 'N1')])

    def test_no_issue_submission_does_not_generate_issues(self):
        with patch.object(api, 'get_physical_table_name_by_code', return_value='test'), \
             patch.object(api, 'checklist_physical_table_exists', return_value=True):
            response = self.post(has_issue='no', inspection_table_id='2')
        self.assertEqual(response.status_code, 200, response.json)
        self.assertIsNone(response.json['issue_id'])
        self.cur.execute('SELECT count(*) AS n FROM issues'); self.assertEqual(self.cur.fetchone()['n'], 0)
        self.assertEqual(list(Path(self.folder.name).rglob('*.jpg')), [])


if __name__ == '__main__': unittest.main()
