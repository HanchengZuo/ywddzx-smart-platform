import os
import unittest
from unittest.mock import patch

from passkey_service import (
    PasskeyConfigurationError,
    get_passkey_settings,
    normalize_credential_name,
    serialize_passkey,
    stable_passkey_user_id,
)


class PasskeyServiceTests(unittest.TestCase):
    def test_localhost_is_allowed_for_local_development(self):
        with patch.dict(
            os.environ,
            {"WEBAUTHN_ORIGIN": "http://localhost:5173", "WEBAUTHN_RP_ID": "localhost"},
            clear=False,
        ):
            settings = get_passkey_settings("http://localhost:5173")

        self.assertEqual(settings["origin"], "http://localhost:5173")
        self.assertEqual(settings["rp_id"], "localhost")

    def test_insecure_remote_origin_is_rejected(self):
        with patch.dict(
            os.environ,
            {"WEBAUTHN_ORIGIN": "http://example.com", "WEBAUTHN_RP_ID": "example.com"},
            clear=False,
        ):
            with self.assertRaises(PasskeyConfigurationError):
                get_passkey_settings("http://example.com")

    def test_configured_origin_must_match_request_origin(self):
        with patch.dict(
            os.environ,
            {"WEBAUTHN_ORIGIN": "https://example.com", "WEBAUTHN_RP_ID": "example.com"},
            clear=False,
        ):
            with self.assertRaises(PasskeyConfigurationError):
                get_passkey_settings("https://admin.example.com")

    def test_user_handle_is_stable_and_unique(self):
        self.assertEqual(stable_passkey_user_id(12), stable_passkey_user_id(12))
        self.assertNotEqual(stable_passkey_user_id(12), stable_passkey_user_id(13))
        self.assertEqual(len(stable_passkey_user_id(12)), 32)

    def test_public_serializer_does_not_return_credential_material(self):
        item = serialize_passkey(
            {
                "id": 8,
                "credential_name": "办公电脑",
                "transports": ["internal"],
                "device_type": "multi_device",
                "backed_up": True,
                "created_at": "2026-08-04 10:00",
                "last_used_at": None,
                "credential_id": b"secret-id",
                "credential_public_key": b"public-key",
            }
        )

        self.assertEqual(item["credential_name"], "办公电脑")
        self.assertNotIn("credential_id", item)
        self.assertNotIn("credential_public_key", item)

    def test_credential_name_is_trimmed_and_bounded(self):
        self.assertEqual(normalize_credential_name("  我的   手机  "), "我的 手机")
        self.assertEqual(len(normalize_credential_name("x" * 100)), 80)


if __name__ == "__main__":
    unittest.main()
