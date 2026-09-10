import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from flask import Flask
import app as api
from external_standard_status import disabled_standard_ids, require_active_standards


class AuthenticationTests(unittest.TestCase):
    def test_ai_candidates_exclude_disabled_without_changing_history_catalog(self):
        source = {100: {'external_standard_id': 100, 'standard_detail_text': '停用规范'},
                  101: {'external_standard_id': 101, 'standard_detail_text': '可用规范'}}
        with patch.object(api, 'fetch_external_standard_map', return_value=source), \
             patch.object(api, 'disabled_standard_ids', return_value={100}), \
             patch.object(api, 'fetch_internal_links_by_external_ids', return_value={}):
            catalog, _ = api.build_external_inspection_standard_ai_catalog(None)
        self.assertEqual([row['standard_id'] for row in catalog], ['101'])
        self.assertEqual(set(source), {100, 101})

    def test_login_required(self):
        with api.app.test_client() as client:
            self.assertEqual(client.put('/api/management/checklists/1/standards/100/status', json={'is_active': False}).status_code, 401)


@unittest.skipUnless(os.getenv('ISSUE_LIFECYCLE_DB_TEST') == '1', 'local database opt-in')
class AvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.conn = api.get_db_connection()
        self.cur = self.conn.cursor()
        self.cur.execute('CREATE TEMP TABLE external_standard_status (standard_id bigint PRIMARY KEY, is_active boolean NOT NULL DEFAULT true, updated_by integer, updated_at timestamptz DEFAULT CURRENT_TIMESTAMP); SET LOCAL search_path TO pg_temp')
        self.user = {'id': 12, 'role': 'root'}
        self.allowed = True
        self.patches = [
            patch.object(api, 'get_current_request_user', side_effect=lambda: self.user),
            patch.object(api, 'get_db_connection', return_value=SimpleNamespace(cursor=self.conn.cursor, commit=lambda: None, rollback=lambda: None)),
            patch.object(api, 'close_db_resources'),
            patch.object(api, 'has_permission', side_effect=lambda *args: self.allowed),
            patch.object(api, 'get_management_checklist_standard_context', return_value=({}, [], 'test_standards')),
            patch.object(api, 'fetch_standard_from_table', return_value={'standard_id': 100, 'description': 'original'}),
        ]
        for item in self.patches: item.start()
        app = Flask('availability_test')
        app.add_url_rule('/status/<int:inspection_table_id>/<int:standard_id>', view_func=api.set_external_standard_status, methods=['PUT'])
        self.client = app.test_client()

    def tearDown(self):
        for item in reversed(self.patches): item.stop()
        self.conn.rollback()
        self.conn.close()

    def test_disable_restore_and_current_actor(self):
        self.assertEqual(disabled_standard_ids(self.cur), set())
        require_active_standards(self.cur, [100])
        response = self.client.put('/status/1/100', json={'is_active': False, 'user_id': 999})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(disabled_standard_ids(self.cur), {100})
        self.cur.execute('SELECT updated_by FROM external_standard_status WHERE standard_id=100')
        self.assertEqual(self.cur.fetchone()['updated_by'], 12)
        with self.assertRaisesRegex(ValueError, '已停用'):
            require_active_standards(self.cur, [101, 100])
        self.assertEqual(self.client.put('/status/1/100', json={'is_active': True}).status_code, 200)
        require_active_standards(self.cur, [100])

    def test_permission_validation_and_missing_standard(self):
        self.allowed = False
        self.assertEqual(self.client.put('/status/1/100', json={'is_active': False}).status_code, 403)
        self.allowed = True
        self.assertEqual(self.client.put('/status/1/100', json={'is_active': 'false'}).status_code, 400)
        with patch.object(api, 'fetch_standard_from_table', return_value=None):
            self.assertEqual(self.client.put('/status/1/100', json={'is_active': False}).status_code, 404)
        self.assertEqual(disabled_standard_ids(self.cur), set())

    def test_migration_repeated_preserves_state(self):
        self.client.put('/status/1/100', json={'is_active': False})
        spec = importlib.util.spec_from_file_location('status_migration', Path(__file__).parents[1] / 'migrations/versions/20260910_001_external_standard_status.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.object(module.op, 'execute', side_effect=self.cur.execute):
            module.upgrade()
            module.upgrade()
        self.assertEqual(disabled_standard_ids(self.cur), {100})
