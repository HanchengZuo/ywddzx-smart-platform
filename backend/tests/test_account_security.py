import unittest

from openpyxl import load_workbook

from account_security import (
    PasswordPolicyError,
    assess_plaintext_password_risks,
    generate_strong_initial_password,
    get_risk_level,
    hash_password,
    validate_password_against_policy,
    verify_password,
)
from credential_exports import build_initial_credentials_workbook


POLICY = {
    "normal_min_length": 12,
    "privileged_min_length": 15,
    "max_length": 64,
    "require_uppercase": True,
    "require_lowercase": True,
    "require_number": True,
    "require_special": True,
    "weak_passwords": ["123456", "password", "admin"],
    "forbid_identity_similarity": True,
    "history_count": 5,
}


class AccountSecurityTests(unittest.TestCase):
    def test_scrypt_hashes_use_unique_salts(self):
        password = "Compliant passphrase 2026!"
        first = hash_password(password)
        second = hash_password(password)

        self.assertNotEqual(first, second)
        self.assertNotIn(password, first)
        self.assertTrue(verify_password(first, password))
        self.assertTrue(verify_password(second, password))
        self.assertFalse(verify_password(first, "wrong password"))

    def test_policy_rejects_weak_short_and_identity_related_passwords(self):
        user = {
            "role": "supervisor",
            "username": "securityadmin",
            "phone": "13800138000",
            "hos_station_code": "PQ04",
        }

        for password in ("123456", "short-pass", "securityadmin safe passphrase"):
            with self.subTest(password=password):
                with self.assertRaises(PasswordPolicyError):
                    validate_password_against_policy(password, user, POLICY)

    def test_policy_rejects_recent_password_reuse(self):
        user = {"role": "station_manager", "username": "stationtester"}
        old_password = "Old compliant phrase 2026!"
        history = [hash_password(old_password)]

        with self.assertRaises(PasswordPolicyError):
            validate_password_against_policy(old_password, user, POLICY, history)

    def test_policy_requires_character_categories_and_rejects_phone(self):
        user = {
            "role": "station_manager",
            "username": "stationtester",
            "phone": "13800138000",
        }
        invalid_passwords = (
            "lowercase only password!2",
            "UPPERCASE ONLY PASSWORD!2",
            "MissingNumberPassword!",
            "MissingSpecialPassword2",
            "Safe13800138000Ab!",
        )
        for password in invalid_passwords:
            with self.subTest(password=password):
                with self.assertRaises(PasswordPolicyError):
                    validate_password_against_policy(password, user, POLICY)

    def test_generated_initial_password_is_unique_and_policy_compliant(self):
        user = {
            "role": "supervisor",
            "username": "securityadmin",
            "phone": "13800138000",
            "hos_station_code": "PQ04",
        }
        passwords = {generate_strong_initial_password(user, POLICY) for _ in range(20)}

        self.assertEqual(len(passwords), 20)
        for password in passwords:
            self.assertGreaterEqual(len(password), 18)
            self.assertEqual(validate_password_against_policy(password, user, POLICY), password)

    def test_initial_credentials_workbook_contains_only_supplied_one_time_credentials(self):
        stream = build_initial_credentials_workbook(
            [
                {
                    "username": "station01",
                    "initial_password": "Abc!2345SafePassword",
                    "real_name": "测试用户",
                    "role_label": "站点账号",
                    "station_name": "测试站点",
                    "station_region": "测试片区",
                    "account_status_label": "正常",
                }
            ],
            "2026-08-04 12:00:00",
        )
        workbook = load_workbook(stream, data_only=False)
        sheet = workbook["初始登录凭据"]

        self.assertEqual(sheet["B7"].value, "station01")
        self.assertEqual(sheet["C7"].value, "Abc!2345SafePassword")
        self.assertEqual(sheet["C7"].data_type, "s")

    def test_plaintext_risk_assessment_precedes_hash_migration(self):
        user = {"role": "station_manager", "username": "stationtester"}
        flags = assess_plaintext_password_risks("123456", user, POLICY)

        self.assertIn("initial_password", flags)
        self.assertIn("too_short", flags)
        self.assertIn("policy_outdated", flags)
        self.assertEqual(get_risk_level("active", True, flags), "critical")
        self.assertEqual(get_risk_level("suspended", True, flags), "disabled")


if __name__ == "__main__":
    unittest.main()
