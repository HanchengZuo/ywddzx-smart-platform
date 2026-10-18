"""Public-to-accounts documentation, protected by the real application auth hooks."""
from contextlib import ExitStack
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app as api
import system_manual


class SystemManualTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.user = {'id': 17, 'username': 'reader', 'role': 'station_manager', 'permissions': {}}
        self.verify = self.stack.enter_context(patch.object(api, 'verify_auth_token', side_effect=lambda _: (dict(self.user), {})))
        self.stack.enter_context(patch.object(api, 'touch_online_user_presence'))
        self.stack.enter_context(patch.object(api, 'start_backup_scheduler_once'))
        self.database = self.stack.enter_context(patch.object(api, 'get_db_connection', side_effect=AssertionError('No business database access')))
        self.client = api.app.test_client()

    def get(self, path='', authenticated=True, **kwargs):
        return self.client.get('/api/system-manual/documents' + path,
                               headers={'Authorization': 'Bearer test-token'} if authenticated else {},
                               buffered=True, **kwargs)

    def test_authentication_required_for_catalog_preview_and_original(self):
        for path in ('', '/inspection-workflow/preview', '/inspection-workflow/original?download=1'):
            with self.subTest(path=path):
                response = self.get(path, authenticated=False)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json['error'], '请先登录。')
        self.verify.side_effect = PermissionError('会话已失效。')
        self.assertEqual(self.get().status_code, 401)
        self.database.assert_not_called()

    def test_all_roles_can_read_without_any_individual_page_permission(self):
        for role in api.ROLE_LABELS:
            with self.subTest(role=role):
                self.user['role'] = role
                response = self.get()
                self.assertEqual(response.status_code, 200)
                items = response.json['items']
                self.assertEqual([item['title'] for item in items], ['巡检流程设计图', '问题申诉流程说明'])
                self.assertTrue(all(item['file_size'] > 0 for item in items))
                self.assertNotIn(str(system_manual.ASSET_ROOT), response.get_data(as_text=True))
        self.database.assert_not_called()

    def test_forced_password_change_blocks_document_bytes_too(self):
        self.user['_password_change_enforced'] = True
        response = self.get('/inspection-workflow/preview')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json['code'], 'PASSWORD_CHANGE_REQUIRED')

    def test_original_bytes_match_supplied_documents_and_are_downloadable(self):
        expected = {
            'inspection-workflow': ('application/pdf', '99a9ede7e8a2c4823d815be2ee6dd139823a353fd704fdb24e125296ea88f1b3'),
            'issue-appeal-workflow': ('image/png', 'a4a0d8464ca4ef0f56cb1878532984a1acdf1730cbe10480c0fc32114de927d0'),
        }
        for document, (mimetype, digest) in expected.items():
            with self.subTest(document=document):
                response = self.get('/' + document + '/original?download=1')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.mimetype, mimetype)
                self.assertEqual(hashlib.sha256(response.data).hexdigest(), digest)
                self.assertIn('attachment;', response.headers['Content-Disposition'])
                self.assertIn('filename*=UTF-8', response.headers['Content-Disposition'])
                self.assertEqual(response.headers['Cache-Control'], 'private, no-store')
                self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
                response.close()

    def test_preview_is_a_full_size_image_and_original_supports_range(self):
        from PIL import Image
        from io import BytesIO
        for document in system_manual.DOCUMENTS:
            response = self.get('/' + document['id'] + '/preview')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, 'image/png')
            image = Image.open(BytesIO(response.data))
            self.assertGreaterEqual(image.height, 1500)
            self.assertGreaterEqual(image.width, 1000)
            response.close()
        response = self.client.get('/api/system-manual/documents/inspection-workflow/original',
            headers={'Authorization': 'Bearer test-token', 'Range': 'bytes=0-3'}, buffered=True)
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.data, b'%PDF')
        response.close()

    def test_unknown_assets_and_traversal_cannot_read_arbitrary_files(self):
        for path in ('/unknown/original', '/inspection-workflow/unknown', '/inspection-workflow/../../app.py',
                     '/inspection-workflow/original/extra', '/app.py/original'):
            with self.subTest(path=path):
                self.assertEqual(self.get(path).status_code, 404)
        response = self.get('/inspection-workflow/original?filename=../../app.py')
        self.assertEqual(response.data[:4], b'%PDF')
        response.close()
        self.assertEqual(self.client.post('/api/system-manual/documents',
            headers={'Authorization': 'Bearer test-token'}, json={}).status_code, 405)

    def test_missing_assets_return_safe_recoverable_error(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(system_manual, 'ASSET_ROOT', Path(directory)):
            for path in ('', '/inspection-workflow/original', '/inspection-workflow/preview'):
                response = self.get(path)
                self.assertEqual(response.status_code, 503)
                self.assertNotIn(directory, response.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
