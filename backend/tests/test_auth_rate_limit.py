import unittest
from datetime import datetime, timezone

from auth_rate_limit import AuthenticationRateLimitExceeded, build_rate_limit_key


class AuthenticationRateLimitUnitTests(unittest.TestCase):
    def test_scope_key_is_stable_but_does_not_expose_identity(self):
        first = build_rate_limit_key("test-secret", "login_pair", "127.0.0.1\x00root")
        second = build_rate_limit_key("test-secret", "login_pair", "127.0.0.1\x00root")

        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)
        self.assertNotIn("root", first)
        self.assertNotIn("127.0.0.1", first)

    def test_scope_keys_are_separated_by_type(self):
        pair_key = build_rate_limit_key("test-secret", "login_pair", "same")
        ip_key = build_rate_limit_key("test-secret", "login_ip", "same")
        self.assertNotEqual(pair_key, ip_key)

    def test_rate_limit_error_exposes_only_retry_delay(self):
        error = AuthenticationRateLimitExceeded(12.2)
        self.assertEqual(error.retry_after, 12)
        self.assertEqual(str(error), "请求过于频繁，请稍后再试。")

    def test_datetime_fixture_is_timezone_aware(self):
        self.assertIsNotNone(datetime.now(timezone.utc).tzinfo)


if __name__ == "__main__":
    unittest.main()
