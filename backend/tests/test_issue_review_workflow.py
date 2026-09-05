import unittest

from app import classify_non_oil_rectification, resolve_issue_review_transition


class IssueReviewWorkflowTests(unittest.TestCase):
    def test_unable_approval_and_rejection(self):
        approved = resolve_issue_review_transition('通过站级无法整改', '站经无法整改')
        rejected = resolve_issue_review_transition('驳回站级无法整改', '站级无法整改')
        self.assertEqual(approved['new_status'], '站级无法整改')
        self.assertEqual(rejected['new_status'], '待整改')
        self.assertFalse(approved['photo_required'])
        self.assertFalse(rejected['photo_required'])
        self.assertTrue(rejected['returns_to_station'])

    def test_cross_branch_reviews_are_rejected(self):
        for result, station in [('整改通过', '站经无法整改'), ('整改不通过', '站经无法整改'), ('通过站级无法整改', '已整改'), ('驳回站级无法整改', '已整改'), ('整改通过', '')]:
            with self.subTest(result=result, station=station), self.assertRaises(ValueError):
                resolve_issue_review_transition(result, station)

    def test_legacy_ordinary_approval_is_compatible(self):
        self.assertEqual(resolve_issue_review_transition('已整改', '已整改')['review_result'], '整改通过')

    def test_rectified_review_closes_issue_and_requires_photo(self):
        transition = resolve_issue_review_transition("已整改")

        self.assertEqual(transition["new_status"], "已闭环")
        self.assertTrue(transition["photo_required"])
        self.assertFalse(transition["returns_to_station"])

    def test_retired_unable_results_are_rejected(self):
        for value in ("站级无法整改", "站经无法整改", "站经理无法整改"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve_issue_review_transition(value)

    def test_rejected_rectification_returns_to_station_without_photo(self):
        transition = resolve_issue_review_transition("整改不通过")

        self.assertEqual(transition["new_status"], "待整改")
        self.assertFalse(transition["photo_required"])
        self.assertTrue(transition["returns_to_station"])

    def test_unknown_review_result_is_rejected(self):
        with self.assertRaises(ValueError):
            resolve_issue_review_transition("未整改")

    def test_rejected_review_is_pending_rectification_in_reports(self):
        result = classify_non_oil_rectification(
            {
                "status": "待整改",
                "rectification_result": "已整改",
                "review_result": "整改不通过",
            }
        )

        self.assertEqual(result, "pending_rectification")

    def test_accepted_review_is_completed_in_reports(self):
        result = classify_non_oil_rectification(
            {"status": "已闭环", "review_result": "已整改"}
        )

        self.assertEqual(result, "completed")


if __name__ == "__main__":
    unittest.main()
