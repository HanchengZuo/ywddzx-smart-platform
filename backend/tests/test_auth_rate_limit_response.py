import unittest

from app import app, authentication_rate_limit_response
from auth_rate_limit import AuthenticationRateLimitExceeded


class AuthenticationRateLimitResponseTests(unittest.TestCase):
    def test_response_contains_human_readable_and_machine_readable_retry_delay(self):
        with app.test_request_context("/api/login", method="POST"):
            response = authentication_rate_limit_response(
                AuthenticationRateLimitExceeded(125, "login_pair")
            )

        payload = response.get_json()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], "125")
        self.assertEqual(payload["retry_after"], 125)
        self.assertEqual(payload["limit_scope"], "login_pair")
        self.assertIn("2分5秒", payload["error"])


if __name__ == "__main__":
    unittest.main()
