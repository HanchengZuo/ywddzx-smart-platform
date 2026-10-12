"""Isolated Flask tests using real endpoint/middleware source; no database or running service."""
import ast
import logging
import os
from pathlib import Path
import unittest
from unittest.mock import MagicMock

from flask import Flask, g, jsonify, request


class PresentationSessionTests(unittest.TestCase):
    def setUp(self):
        source = Path(os.environ.get('PRESENTATION_APP_SOURCE', Path(__file__).resolve().parents[1] / 'app.py'))
        tree = ast.parse(source.read_text())
        nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in {'renew_presentation_session', 'require_signed_api_token'}]
        self.app = Flask(__name__)
        self.user = {'id': 2, 'role': 'supervisor'}
        self.payload = {'amr': 'passkey'}
        self.env = {
            'app': self.app, 'g': g, 'jsonify': jsonify, 'request': request, 'logging': logging,
            'is_public_api_path': lambda path: False,
            'extract_bearer_token': lambda: request.headers.get('Authorization', '').removeprefix('Bearer '),
            'verify_auth_token': MagicMock(side_effect=lambda token: (self.user, self.payload)),
            'touch_online_user_presence': MagicMock(), 'iter_request_identity_values': lambda: [],
            'normalize_identity_for_compare': str, 'IMPERSONATION_BLOCKED_PATH_PREFIXES': (),
            'FORCED_PASSWORD_CHANGE_ALLOWED_PATHS': {'/api/auth/me'},
            'get_db_connection': MagicMock(), 'has_permission': MagicMock(return_value=True),
            'get_auth_payload_expires_in': MagicMock(return_value=1200),
            'create_auth_token': MagicMock(return_value='new-token'),
            'create_impersonation_token': MagicMock(return_value='new-impersonation-token'),
            'get_auth_token_ttl_seconds': lambda user: 14400 if user['role'] == 'root' else 28800,
            'build_auth_user_payload': MagicMock(return_value={'id': 2}),
            'build_authenticated_response': lambda payload, token: jsonify(payload),
            'close_db_resources': MagicMock(),
        }
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), self.env)
        self.client = self.app.test_client()

    def renew(self, kind='cockpit', authenticated=True):
        return self.client.post('/api/auth/presentation/renew', json={'kind': kind},
                                headers={'Authorization': 'Bearer existing'} if authenticated else {})

    def test_valid_kinds_check_their_specific_permission(self):
        for kind, permission in [('cockpit', 'view_operations_overview'), ('map', 'view_station_map')]:
            response = self.renew(kind)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['token'], 'new-token')
            self.env['has_permission'].assert_called_with(unittest.mock.ANY, self.user, permission)
            self.env['create_auth_token'].assert_called_with(self.user, 'passkey')

    def test_invalid_kinds_and_missing_permission_are_rejected(self):
        for kind in ['issues', '', None, ['map']]:
            self.assertEqual(self.renew(kind).status_code, 400)
        response = self.client.post('/api/auth/presentation/renew', json=['map'],
                                    headers={'Authorization': 'Bearer existing'})
        self.assertEqual(response.status_code, 400)
        self.env['has_permission'].return_value = False
        self.assertEqual(self.renew().status_code, 403)
        self.env['create_auth_token'].assert_not_called()

    def test_fresh_token_is_not_rotated_on_every_poll(self):
        self.env['get_auth_payload_expires_in'].return_value = 3600
        self.assertEqual(self.renew().json['token'], 'existing')
        self.env['create_auth_token'].assert_not_called()

    def test_impersonation_keeps_root_identity_and_shorter_ttl(self):
        root = {'id': 1, 'role': 'root'}
        self.user['_impersonator'] = root
        response = self.renew('map')
        self.assertEqual(response.json['token'], 'new-impersonation-token')
        self.assertEqual(response.json['expires_in'], 14400)
        self.env['create_impersonation_token'].assert_called_once_with(self.user, root)
        self.env['create_auth_token'].assert_not_called()

    def test_expired_revoked_or_disabled_session_still_fails_middleware(self):
        for reason in ['expired', 'revoked', 'disabled']:
            self.env['verify_auth_token'].side_effect = PermissionError(reason)
            self.assertEqual(self.renew().status_code, 401)
        self.env['get_db_connection'].assert_not_called()

    def test_no_token_or_forced_password_change_cannot_renew(self):
        self.assertEqual(self.renew(authenticated=False).status_code, 401)
        self.user['_password_change_enforced'] = True
        self.assertEqual(self.renew().status_code, 403)
        self.env['get_db_connection'].assert_not_called()


if __name__ == '__main__':
    unittest.main()
