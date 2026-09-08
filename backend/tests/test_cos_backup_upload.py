import unittest
from unittest.mock import MagicMock, patch

import app as api


class CosBackupUploadTests(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.config = dict(configured=True, sdk_available=True, bucket='test', region='test', prefix='backups/')
        self.size = 6 * 1024 ** 3
        self.key = 'backups/ywddzx_full_backup_new.zip'
        self.rows = [dict(key=self.key, size=self.size), dict(key='backups/ywddzx_full_backup_old.zip', size=10)]
        for target, value in [('get_cos_env_config', self.config), ('get_cos_client', (self.client, self.config)),
                              ('list_cos_backup_objects', self.rows), ('os.path.getsize', self.size)]:
            patcher = patch('app.' + target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client.head_object.return_value = {'Content-Length': str(self.size)}

    def upload(self):
        return api.upload_backup_archive_to_cos('/tmp/backup.zip', self.key.split('/')[-1])

    def test_large_archive_uses_bounded_multipart_and_keeps_one(self):
        result = self.upload()
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['retained_count'], 1)
        self.client.upload_file.assert_called_once_with(Bucket='test', Key=self.key,
            LocalFilePath='/tmp/backup.zip', PartSize=16, MAXThread=2, EnableMD5=True)
        self.client.put_object_from_local_file.assert_not_called()
        self.client.delete_object.assert_called_once_with(Bucket='test', Key=self.rows[1]['key'])
        calls = [call[0] for call in self.client.mock_calls]
        self.assertLess(calls.index('head_object'), calls.index('delete_object'))

    def test_failed_upload_preserves_old_backups(self):
        self.client.upload_file.side_effect = RuntimeError('network failure')
        self.assertEqual(self.upload()['status'], 'error')
        self.client.delete_object.assert_not_called()

    def test_size_mismatch_preserves_old_backups(self):
        self.client.head_object.return_value = {'Content-Length': '1'}
        self.assertEqual(self.upload()['status'], 'error')
        self.client.delete_object.assert_not_called()

    def test_missing_uploaded_object_preserves_old_backups(self):
        with patch('app.list_cos_backup_objects', return_value=self.rows[1:]):
            self.assertEqual(self.upload()['status'], 'error')
        self.client.delete_object.assert_not_called()

    def test_unconfigured_does_not_upload_or_delete(self):
        with patch('app.get_cos_env_config', return_value={'configured': False}):
            self.assertEqual(self.upload()['status'], 'not_configured')
        self.client.upload_file.assert_not_called()
        self.client.delete_object.assert_not_called()


if __name__ == '__main__':
    unittest.main()
