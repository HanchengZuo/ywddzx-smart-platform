import unittest

from app import normalize_auto_audit_rule_payload


class AutoAuditRuleTests(unittest.TestCase):
    def test_rule_accepts_only_a_complete_external_standard_id(self):
        rule = normalize_auto_audit_rule_payload(
            {
                "rule_name": "规范自动通过",
                "external_standard_id": "12001",
                "decision": "approved",
                "is_enabled": True,
            }
        )

        self.assertEqual(rule["external_standard_id"], 12001)
        self.assertNotIn("match_type", rule)
        self.assertNotIn("priority", rule)

    def test_legacy_keyword_rule_payload_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "自动审核规则只支持外部规范ID"):
            normalize_auto_audit_rule_payload(
                {
                    "rule_name": "旧关键词规则",
                    "match_type": "description_keyword",
                    "match_value": "12001",
                    "decision": "rejected",
                }
            )

    def test_non_positive_external_standard_id_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "外部规范ID必须大于 0"):
            normalize_auto_audit_rule_payload(
                {
                    "rule_name": "无效规范规则",
                    "external_standard_id": 0,
                    "decision": "approved",
                }
            )

    def test_external_standard_id_is_canonicalized_for_unique_matching(self):
        rule = normalize_auto_audit_rule_payload(
            {
                "rule_name": "规范ID归一化",
                "external_standard_id": "0012001",
                "decision": "approved",
            }
        )

        self.assertEqual(rule["external_standard_id"], 12001)


if __name__ == "__main__":
    unittest.main()
