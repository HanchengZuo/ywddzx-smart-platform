import os
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor
import unittest
import uuid
from unittest.mock import MagicMock, patch

from flask import Flask, g, request
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from psycopg2.extensions import parse_dsn

import app as api
from help_document_http import register_help_documents
from help_documents import PERMISSION, EditConflict, normalize_content, change_document

SCHEMA = Path(__file__).resolve().parents[1] / 'db' / 'init' / '730_help_documents.sql'


def content(title='测试使用指南'):
    return dict(title=title, category='新手上手', summary='操作说明', tags=['登录'],
                body='## 操作步骤\n1. 打开菜单\n2. 按提示处理', attachments=['inspection-workflow'])


class HelpPermissionTests(unittest.TestCase):
    def test_only_root_has_default_edit_right_and_there_is_no_view_permission(self):
        self.assertIn(PERMISSION, api.PERMISSION_KEYS)
        for role in api.ROLE_OPTIONS:
            self.assertEqual(api.role_default_permission(role, PERMISSION), role == 'root')
        self.assertFalse(any(item['key'].startswith('view_help') for item in api.PERMISSION_CATALOG))

    def test_other_management_users_cannot_grant_editor_role_permission(self):
        cur = MagicMock()
        with patch.object(api, 'get_user_by_id', return_value={'id': 17, 'role': 'supervisor'}), \
             patch.object(api, 'build_role_effective_permissions', return_value={}):
            with self.assertRaisesRegex(PermissionError, '只有root.*帮助文档编辑权限'):
                api.apply_role_permission_updates(cur, 'supervisor', {PERMISSION: True}, 17)
        cur.execute.assert_not_called()

    def test_server_rejects_invalid_content_and_arbitrary_attachment_paths(self):
        for data in [None, {**content(), 'title': ''}, {**content(), 'body': 'x' * 20001},
                     {**content(), 'tags': 'x'}, {**content(), 'attachments': ['../../secret']},
                     {**content(), 'category': 'x\x00y'}]:
            with self.assertRaises(ValueError):
                normalize_content(data)
        normalized = normalize_content({**content(), 'title': '  测试指南  ', 'tags': ['登录', '登录'], 'actor_id': 999})
        self.assertEqual(normalized['title'], '测试指南')
        self.assertEqual(normalized['tags'], ['登录'])
        self.assertNotIn('actor_id', normalized)

    def test_real_application_auth_guard_protects_all_help_routes(self):
        with patch.object(api, 'start_backup_scheduler_once'), patch.object(api, 'get_db_connection', side_effect=AssertionError('No DB')):
            for method, path in [('get', '/api/help-documents'), ('post', '/api/help-documents'),
                                  ('put', '/api/help-documents/test'), ('get', '/api/help-documents/test/history')]:
                self.assertEqual(getattr(api.app.test_client(), method)(path).status_code, 401)


@unittest.skipUnless(os.environ.get('HELP_DOCUMENT_TEST_DSN'), 'requires disposable test PostgreSQL')
class HelpDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ['HELP_DOCUMENT_TEST_DSN']
        if not parse_dsn(cls.dsn).get('dbname', '').startswith('test_'):
            raise RuntimeError('Only disposable test databases are allowed')
        cls.schema = 'help_test_' + uuid.uuid4().hex
        with psycopg2.connect(cls.dsn) as conn, conn.cursor() as cur:
            cur.execute('CREATE SCHEMA ' + cls.schema)

    @classmethod
    def tearDownClass(cls):
        with psycopg2.connect(cls.dsn) as conn, conn.cursor() as cur:
            cur.execute('DROP SCHEMA ' + cls.schema + ' CASCADE')

    def connect(self):
        return psycopg2.connect(self.dsn, cursor_factory=RealDictCursor, options='-c search_path=' + self.schema)

    def setUp(self):
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute('DROP TABLE IF EXISTS help_document_events,help_documents CASCADE')
            cur.execute(SCHEMA.read_text())
        self.user = {'id': 17, 'username': 'editor', 'real_name': '维护人', 'role': 'root'}
        self.granted = False
        self.app = Flask(__name__)
        @self.app.before_request
        def login():
            if request.headers.get('Authorization'):
                g.current_user = dict(self.user)
        register_help_documents(self.app, connect=self.connect,
            has_permission=lambda cur, user, key: user['role'] == 'root' or self.granted)
        self.client = self.app.test_client()
        self.headers = {'Authorization': 'Bearer test-only'}

    def get(self, workspace=False):
        return self.client.get('/api/help-documents' + ('?workspace=1' if workspace else ''), headers=self.headers)

    def update(self, identifier='getting-started', revision=0, action='draft', body=None):
        return self.client.put('/api/help-documents/' + identifier, headers=self.headers,
            json={'revision': revision, 'action': action, 'content': body or content()})

    def test_readers_see_published_only_and_permissions_enforced_on_every_mutation(self):
        self.user['role'] = 'station_manager'
        self.assertEqual(self.get().status_code, 200)
        self.assertFalse(self.get().json['can_edit'])
        self.assertEqual(self.get(True).status_code, 403)
        self.assertEqual(self.update().status_code, 403)
        self.assertEqual(self.client.post('/api/help-documents', headers=self.headers, json={}).status_code, 403)
        self.assertEqual(self.client.get('/api/help-documents/getting-started/history', headers=self.headers).status_code, 403)
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute('SELECT count(*) AS count FROM help_document_events')
            self.assertEqual(cur.fetchone()['count'], 0)
        self.granted = True
        self.assertEqual(self.update().status_code, 200)
        self.granted = False
        self.assertEqual(self.update(revision=1).status_code, 403)

    def test_drafts_do_not_leak_and_publish_archive_restore_have_clear_effect(self):
        original = self.get().json['items'][0]['content']['title']
        saved = self.update(body=content('秘密草稿标题'))
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(self.get().json['items'][0]['content']['title'], original)
        self.assertNotIn('秘密草稿标题', self.get().get_data(as_text=True))
        self.assertEqual(self.get(True).json['items'][0]['content']['title'], '秘密草稿标题')
        self.assertEqual(self.update(revision=1, action='publish', body=content('发布新指南')).status_code, 200)
        self.assertEqual(self.get().json['items'][0]['content']['title'], '发布新指南')
        self.assertEqual(self.update(revision=2, action='archive').status_code, 200)
        self.assertNotIn('getting-started', [item['id'] for item in self.get().json['items']])
        self.assertEqual(self.update(revision=3, action='restore').status_code, 200)
        self.assertIn('getting-started', [item['id'] for item in self.get().json['items']])
        history = self.client.get('/api/help-documents/getting-started/history', headers=self.headers).json['items']
        self.assertEqual([row['action'] for row in history], ['restore', 'archive', 'publish', 'draft'])
        self.assertEqual(history[0]['actor']['id'], 17)

    def test_new_draft_is_not_public_and_repeated_seed_never_overwrites_edits(self):
        created = self.client.post('/api/help-documents', headers=self.headers, json={
            'revision': 0, 'action': 'draft', 'content': content('新增草稿指南')})
        self.assertEqual(created.status_code, 200)
        identifier = created.json['item']['id']
        self.assertNotIn(identifier, [item['id'] for item in self.get().json['items']])
        self.assertEqual(self.update(action='publish', body=content('维护后的指南')).status_code, 200)
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(SCHEMA.read_text())
        self.assertEqual(self.get().json['items'][0]['content']['title'], '维护后的指南')

    def test_audit_failure_rolls_back_content_and_revision(self):
        def fail_actor(value, *args, **kwargs):
            if isinstance(value, dict) and 'username' in value:
                raise RuntimeError('test audit failure')
            return Json(value, *args, **kwargs)
        with patch('help_documents.Json', side_effect=fail_actor):
            self.assertEqual(self.update(action='publish').status_code, 503)
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT revision,published->>'title' AS title FROM help_documents WHERE id='getting-started'")
            row = cur.fetchone()
            self.assertEqual(row['revision'], 0)
            self.assertEqual(row['title'], '第一次使用，从这里开始')

    def test_stale_updates_and_parallel_editors_cannot_overwrite_each_other(self):
        barrier = threading.Barrier(2)
        def edit(title):
            conn = self.connect()
            try:
                with conn.cursor() as cur:
                    barrier.wait(timeout=5)
                    change_document(cur, 'getting-started', {'revision': 0, 'action': 'publish', 'content': content(title)}, self.user)
                conn.commit()
                return 'saved'
            except EditConflict:
                conn.rollback()
                return 'conflict'
            finally:
                conn.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(edit, ['编辑者甲内容', '编辑者乙内容']))
        self.assertCountEqual(results, ['saved', 'conflict'])
        self.assertEqual(self.update(action='publish').status_code, 409)
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute('SELECT count(*) AS count FROM help_document_events')
            self.assertEqual(cur.fetchone()['count'], 1)


if __name__ == '__main__':
    unittest.main()
