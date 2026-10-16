import importlib.util
import os
import unittest
import uuid
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

import app as core_app


class IssueExportAccessTests(unittest.TestCase):
    def test_retired_permission_is_not_exposed_or_accepted_from_old_backups(self):
        key = 'export_issue_photos'
        self.assertNotIn(key, core_app.PERMISSION_KEYS)
        self.assertNotIn(key, core_app.PERMISSION_ANY_DEPENDENCIES)
        self.assertFalse(hasattr(core_app, 'can_export_issue_photos'))
        self.assertFalse(hasattr(core_app, 'issue_export_includes_photos'))
        self.assertEqual(core_app.normalize_permission_updates({key: False, 'view_own_inspection_issues': True}),
                         {'view_own_inspection_issues': True})

    def create(self, role='station_manager', visible_ids=(11, 12), filtered=False, photos=True):
        user = dict(id=17, username='test-account', role=role, station_id=3)
        conn, cur = MagicMock(), MagicMock()
        conn.cursor.return_value = cur
        cur.fetchone.return_value = dict(task_id='test-task', created_by=17, status='pending', selected_count=2)
        data = dict(issue_ids=[11, 12], export_options={
            'include_fields': dict(id=True, issue_photo=photos, rectification_photo=photos, review_photo=photos),
            'include_photos': dict.fromkeys(core_app.ISSUE_EXPORT_PHOTO_KEYS, photos),
        })
        if filtered:
            data['filter_query'] = {'region': '浦东'}
        with ExitStack() as stack:
            stack.enter_context(core_app.app.test_request_context('/api/issues/export-tasks', method='POST', json=data))
            stack.enter_context(patch.object(core_app, 'get_authenticated_request_user_id', return_value=17))
            stack.enter_context(patch.object(core_app, 'get_db_connection', return_value=conn))
            stack.enter_context(patch.object(core_app, 'close_db_resources'))
            stack.enter_context(patch.object(core_app, 'ensure_issue_export_schema'))
            stack.enter_context(patch.object(core_app, 'cleanup_expired_issue_exports'))
            stack.enter_context(patch.object(core_app, 'get_user_by_id', return_value=user))
            # Even an account whose old configuration explicitly denied photo exports is allowed.
            stack.enter_context(patch.object(core_app, 'get_permission_overrides', return_value={'export_issue_photos': False}))
            permission = stack.enter_context(patch.object(core_app, 'has_permission', return_value=False))
            ids = stack.enter_context(patch.object(core_app, 'fetch_issue_list_ids', return_value=[11, 12]))
            rows = stack.enter_context(patch.object(core_app, 'fetch_issue_export_rows', return_value=[{'id': i} for i in visible_ids]))
            start = stack.enter_context(patch.object(core_app, 'start_issue_export_task'))
            value = core_app.create_issue_export_task()
            response, status = value if isinstance(value, tuple) else (value, 200)
            return response.get_json(), status, conn, cur, start, rows, ids, user, permission

    def test_all_roles_can_export_all_three_photo_types_without_extra_grant(self):
        for role in core_app.ROLE_OPTIONS:
            with self.subTest(role=role):
                body, status, conn, cur, start, rows, _, user, permission = self.create(role=role)
                self.assertEqual(status, 200)
                self.assertTrue(body['success'])
                permission.assert_not_called()
                rows.assert_called_once_with(cur, user, [11, 12])
                start.assert_called_once()
                options = start.call_args.args[3]
                self.assertTrue(all(options['include_photos'][key] for key in core_app.ISSUE_EXPORT_PHOTO_KEYS))
                self.assertEqual(options['photo_mode'], 'compatible')
                conn.commit.assert_called_once()

    def test_text_only_remains_a_user_choice_not_a_permission(self):
        _, status, _, _, start, *_ = self.create(photos=False)
        self.assertEqual(status, 200)
        self.assertFalse(any(start.call_args.args[3]['include_photos'].values()))

    def test_filter_selection_and_explicit_ids_still_require_every_row_to_be_visible(self):
        for filtered in (False, True):
            with self.subTest(filtered=filtered):
                body, status, conn, cur, start, rows, ids, user, _ = self.create(visible_ids=(11,), filtered=filtered)
                self.assertEqual(status, 403)
                self.assertIn('无权查看', body['error'])
                rows.assert_called_once_with(cur, user, [11, 12])
                if filtered:
                    ids.assert_called_once_with(cur, user, {'region': '浦东'})
                else:
                    ids.assert_not_called()
                start.assert_not_called()
                conn.commit.assert_not_called()
                conn.rollback.assert_called_once()

    def test_export_rows_keep_station_table_region_pending_and_contact_restrictions(self):
        user = dict(id=17, role='station_manager', station_id=3)
        cur = MagicMock()
        cur.fetchall.return_value = [dict(id=11, inspector='不应导出的姓名', inspector_phone='123', issue_photo='/issue.jpg')]

        def table_scope(_cur, _user, where, params, column, key):
            self.assertEqual((column, key), ('i.inspection_table_id', 'limit_issue_inspection_table_scope'))
            where.append(column + '=%s'); params.append(7)
            return True

        def region_scope(_cur, _user, where, params, column, key):
            self.assertEqual((column, key), ('s.region', 'limit_issue_station_region_scope'))
            where.append(column + '=%s'); params.append('浦东')
            return True

        with ExitStack() as stack:
            for name, result in [('can_view_all_inspection_issues', False), ('can_view_region_inspection_issues', False),
                                 ('can_view_own_inspection_issues', True), ('should_hide_inspector_contact_info', True)]:
                stack.enter_context(patch.object(core_app, name, return_value=result))
            stack.enter_context(patch.object(core_app, 'append_inspection_table_scope_filter', side_effect=table_scope))
            stack.enter_context(patch.object(core_app, 'append_station_region_scope_filter', side_effect=region_scope))
            pending = stack.enter_context(patch.object(core_app, 'append_pending_audit_issue_visibility_filter',
                side_effect=lambda _user, where: where.append("COALESCE(i.audit_status,'pending')<>'pending'")))
            stack.enter_context(patch.object(core_app, 'attach_internal_standard_tags_to_issue_rows'))
            rows = core_app.fetch_issue_export_rows(cur, user, [11])
        pending.assert_called_once()
        query, params = cur.execute.call_args.args
        self.assertIn('i.station_id = %s OR COALESCE(i.inspector_id, ins.inspector_id) = %s', str(query))
        self.assertIn("COALESCE(i.audit_status,'pending')<>'pending'", str(query))
        self.assertEqual(params, [[11], 3, 17, 7, '浦东'])
        self.assertEqual(rows[0]['inspector'], '')
        self.assertEqual(rows[0]['inspector_phone'], '')
        self.assertEqual(rows[0]['issue_photo'], '/issue.jpg')

    def test_other_users_cannot_read_or_download_export_tasks(self):
        cur = MagicMock()
        cur.fetchone.return_value = dict(task_id='test-task', created_by=18, status='completed')
        with self.assertRaises(PermissionError):
            core_app.get_issue_export_task_for_user(cur, 'test-task', dict(id=17, role='station_manager'))
        self.assertEqual(core_app.app.test_client().post('/api/issues/export-tasks', json={}).status_code, 401)


@unittest.skipUnless(os.getenv('ISSUE_EXPORT_DB_TEST') == '1', 'isolated migration test opt-in')
class PhotoExportPermissionMigrationTests(unittest.TestCase):
    def test_cleanup_is_idempotent_and_preserves_other_grants_and_denials(self):
        conn = core_app.get_db_connection()
        cur = conn.cursor()
        try:
            schema = 'test_photo_permission_' + uuid.uuid4().hex
            cur.execute(f'CREATE SCHEMA {schema}; SET LOCAL search_path TO {schema}')
            cur.execute('''CREATE TABLE user_permissions(user_id int, permission_key text, is_allowed bool);
                CREATE TABLE role_permissions(role text, permission_key text, is_allowed bool);
                INSERT INTO user_permissions VALUES (1,'export_issue_photos',TRUE),(2,'export_issue_photos',FALSE),
                    (1,'view_all_inspection_issues',TRUE),(2,'hide_inspector_contact_info',FALSE);
                INSERT INTO role_permissions VALUES ('supervisor','export_issue_photos',FALSE),
                    ('finance','export_issue_photos',TRUE),('supervisor','view_all_inspection_issues',TRUE),
                    ('finance','view_all_inspection_issues',FALSE)''')
            path = Path(__file__).parents[1] / 'migrations/versions/20261016_001_remove_issue_photo_export_permission.py'
            spec = importlib.util.spec_from_file_location('remove_photo_permission', path)
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            with patch.object(migration.op, 'execute', side_effect=cur.execute):
                migration.upgrade(); migration.upgrade()
                migration.downgrade()
            cur.execute('SELECT * FROM user_permissions ORDER BY user_id')
            self.assertEqual([dict(row) for row in cur.fetchall()], [
                dict(user_id=1, permission_key='view_all_inspection_issues', is_allowed=True),
                dict(user_id=2, permission_key='hide_inspector_contact_info', is_allowed=False)])
            cur.execute('SELECT * FROM role_permissions ORDER BY role')
            self.assertEqual([dict(row) for row in cur.fetchall()], [
                dict(role='finance', permission_key='view_all_inspection_issues', is_allowed=False),
                dict(role='supervisor', permission_key='view_all_inspection_issues', is_allowed=True)])
        finally:
            conn.rollback()
            cur.close()
            conn.close()
