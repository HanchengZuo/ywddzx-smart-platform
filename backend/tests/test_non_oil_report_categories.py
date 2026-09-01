import unittest

from app import (
    NON_OIL_KEY_ISSUE_EXCLUDED,
    NON_OIL_REPORT_CATEGORIES,
    NON_OIL_REPORT_GROUP_PURCHASE_TABLE,
    build_non_oil_key_issue_summary,
    build_non_oil_category_distribution,
    build_non_oil_project_matrix,
    normalize_non_oil_effective_category,
    local_non_oil_key_issue_fallback,
)


class NonOilReportCategoryTests(unittest.TestCase):
    def test_group_purchase_other_category_uses_business_fallback(self):
        category = normalize_non_oil_effective_category(
            "其他",
            {"table_name": NON_OIL_REPORT_GROUP_PURCHASE_TABLE},
        )

        self.assertEqual(category, "商品订单、入库、盘点等情况")

    def test_distribution_accepts_legacy_other_category(self):
        distribution = build_non_oil_category_distribution(
            [
                {
                    "category_name": "其他",
                    "table_name": NON_OIL_REPORT_GROUP_PURCHASE_TABLE,
                }
            ]
        )

        self.assertEqual(sum(item["count"] for item in distribution), 1)
        self.assertTrue(all(item["name"] in NON_OIL_REPORT_CATEGORIES for item in distribution))
        self.assertEqual(distribution[0]["name"], "商品订单、入库、盘点等情况")

    def test_project_matrix_accepts_unknown_legacy_category(self):
        matrix = build_non_oil_project_matrix(
            [
                {
                    "source_project": "其他",
                    "category_name": "其他",
                    "table_name": NON_OIL_REPORT_GROUP_PURCHASE_TABLE,
                }
            ]
        )

        self.assertEqual(matrix[0]["total_count"], 1)
        self.assertEqual(
            matrix[0]["category_counts"]["商品订单、入库、盘点等情况"],
            1,
        )

    def test_key_issue_fallback_is_selective(self):
        self.assertEqual(
            local_non_oil_key_issue_fallback({"description": "现场抽盘软中华盘亏10包"}),
            "重点商品",
        )
        self.assertEqual(
            local_non_oil_key_issue_fallback({"description": "便利店地面存在污渍"}),
            NON_OIL_KEY_ISSUE_EXCLUDED,
        )

    def test_key_issue_summary_only_counts_selected_categories(self):
        summary = build_non_oil_key_issue_summary(
            [
                {
                    "issue_id": 1,
                    "key_issue_category": "重点商品",
                    "category_name": "商品订单、入库、盘点等情况",
                    "issue_photo": "",
                },
                {
                    "issue_id": 2,
                    "key_issue_category": NON_OIL_KEY_ISSUE_EXCLUDED,
                    "category_name": "便利店卫生情况",
                    "issue_photo": "",
                },
            ]
        )

        self.assertEqual(summary["selected_count"], 1)
        self.assertEqual(summary["excluded_count"], 1)
        self.assertEqual(summary["distribution"][0]["count"], 1)


if __name__ == "__main__":
    unittest.main()
