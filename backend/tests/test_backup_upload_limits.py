from io import BytesIO
import unittest
from unittest.mock import patch, MagicMock
from flask import Flask, request
from upload_request import PlatformRequest
import app as api


class BackupUploadLimitTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask('upload_limit_test')
        self.app.request_class = PlatformRequest
        self.app.config['MAX_CONTENT_LENGTH'] = 1024
        self.app.add_url_rule('/backup', endpoint='import_management_full_backup', view_func=self.read_upload, methods=['POST', 'PUT'])
        self.app.add_url_rule('/other', view_func=self.read_upload, methods=['POST'])
        self.client = self.app.test_client()

    @staticmethod
    def read_upload():
        return {'size': len(request.files['file'].read())}

    def send(self, path, method='POST'):
        return self.client.open(path, method=method, data={'file': (BytesIO(b'x' * 4096), 'backup.zip')})

    def test_backup_can_exceed_global_limit(self):
        response = self.send('/backup')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['size'], 4096)
        self.assertEqual(self.app.config['MAX_CONTENT_LENGTH'], 1024)

    def test_other_uploads_and_methods_stay_limited(self):
        self.assertEqual(self.send('/other').status_code, 413)
        self.assertEqual(self.send('/backup', 'PUT').status_code, 413)

    def test_unauthenticated_backup_is_rejected(self):
        with api.app.test_client() as client:
            self.assertEqual(client.post('/api/management/backups/import').status_code, 401)

    def test_permission_checked_before_file_body(self):
        with api.app.test_request_context('/api/management/backups/import', method='POST'), \
             patch.object(api, 'get_db_connection', return_value=MagicMock()), \
             patch.object(api, 'close_db_resources'), \
             patch.object(api, 'require_management_user', side_effect=PermissionError('无权恢复')) as guard, \
             patch.object(api, 'restore_full_backup_archive') as restore:
            response, status = api.import_management_full_backup()
            self.assertEqual(status, 403)
            guard.assert_called_once()
            self.assertIsNone(guard.call_args.args[1])
            self.assertNotIn('files', request.__dict__)
            restore.assert_not_called()
