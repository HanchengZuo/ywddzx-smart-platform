import unittest

from app import (
    NON_OIL_REPORT_CATEGORIES,
    NON_OIL_REPORT_GROUP_PURCHASE_TABLE,
    build_non_oil_category_distribution,
    build_non_oil_project_matrix,
    normalize_non_oil_effective_category,
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


if __name__ == "__main__":
    unittest.main()
