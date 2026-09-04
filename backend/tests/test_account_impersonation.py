import unittest

from flask import g

from app import (
    app,
    create_impersonation_token,
    get_auth_serializer,
    get_root_impersonation_actor,
    serialize_impersonation_account,
)


class AccountImpersonationTests(unittest.TestCase):
    def setUp(self):
        self.root = {
            "id": 1,
            "username": "root",
            "role": "root",
            "auth_version": 7,
            "account_status": "active",
        }
        self.target = {
            "id": 18,
            "username": "station-user",
            "role": "station_manager",
            "auth_version": 3,
            "account_status": "active",
        }

    def test_impersonation_token_binds_target_and_root_security_versions(self):
        token = create_impersonation_token(self.target, self.root)
        payload = get_auth_serializer().loads(token)

        self.assertEqual(payload["uid"], self.target["id"])
        self.assertEqual(payload["role"], self.target["role"])
        self.assertEqual(payload["av"], self.target["auth_version"])
        self.assertEqual(payload["imp_uid"], self.root["id"])
        self.assertEqual(payload["imp_av"], self.root["auth_version"])
        self.assertEqual(payload["amr"], "impersonation")
        self.assertNotIn("password", payload)
        self.assertNotIn("password_hash", payload)

    def test_only_root_or_existing_root_impersonation_can_switch_accounts(self):
        with app.test_request_context("/api/auth/impersonation/accounts"):
            g.current_user = self.root
            g.auth_payload = {"amr": "passkey"}
            self.assertEqual(get_root_impersonation_actor()["id"], self.root["id"])

        with app.test_request_context("/api/auth/impersonation/accounts"):
            g.current_user = self.target
            g.impersonator = self.root
            self.assertEqual(get_root_impersonation_actor()["id"], self.root["id"])

        with app.test_request_context("/api/auth/impersonation/accounts"):
            g.current_user = self.target
            g.impersonator = None
            with self.assertRaises(PermissionError):
                get_root_impersonation_actor()

        with app.test_request_context("/api/auth/impersonation/accounts"):
            g.current_user = self.root
            g.auth_payload = {"amr": "password"}
            with self.assertRaises(PermissionError):
                get_root_impersonation_actor()

    def test_account_directory_payload_excludes_sensitive_fields(self):
        payload = serialize_impersonation_account(
            {
                **self.target,
                "real_name": "测试站经理",
                "station_id": 9,
                "station_name": "测试站",
                "region": "浦东",
                "phone": "13800000000",
                "password_hash": "secret",
            }
        )

        self.assertEqual(payload["display_name"], "测试站经理")
        self.assertNotIn("phone", payload)
        self.assertNotIn("password_hash", payload)


if __name__ == "__main__":
    unittest.main()
