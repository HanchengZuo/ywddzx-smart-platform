import unittest
from contextlib import ExitStack
from io import BytesIO
from unittest.mock import MagicMock, patch

import app as core_app
from app import classify_non_oil_rectification, resolve_issue_review_transition


class IssueReviewWorkflowTests(unittest.TestCase):
    def test_unable_approval_and_rejection(self):
        approved = resolve_issue_review_transition('通过站级无法整改', '站经无法整改')
        rejected = resolve_issue_review_transition('驳回站级无法整改', '站级无法整改')
        self.assertEqual(approved['new_status'], '站级无法整改')
        self.assertEqual(rejected['new_status'], '待整改')
        self.assertFalse(approved['photo_required'])
        self.assertFalse(rejected['photo_required'])
        self.assertFalse(approved['photo_allowed'])
        self.assertFalse(rejected['photo_allowed'])
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
        self.assertTrue(transition["photo_allowed"])
        self.assertFalse(transition["returns_to_station"])

    def test_retired_unable_results_are_rejected(self):
        for value in ("站级无法整改", "站经无法整改", "站经理无法整改"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve_issue_review_transition(value)

    def test_rejected_rectification_returns_to_station_with_optional_photo(self):
        transition = resolve_issue_review_transition("整改不通过")

        self.assertEqual(transition["new_status"], "待整改")
        self.assertFalse(transition["photo_required"])
        self.assertTrue(transition["photo_allowed"])
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


class ReviewSubmissionTests(unittest.TestCase):
    def submit(self, result='整改不通过', photo=False, station_result='已整改',
               status='待复核', role='supervisor', audit='approved', user_id=17):
        conn, cur = MagicMock(), MagicMock()
        conn.cursor.return_value = cur
        user = dict(id=17, username='reviewer', real_name='复核人员', role=role)
        cur.fetchone.side_effect = [user, dict(id=42, status=status,
            rectification_result=station_result, audit_status=audit)]
        data = dict(user_id='17', review_result=result, review_note='')
        if photo:
            data['review_photo'] = (BytesIO(b'image-data'), 'review.png')
        with ExitStack() as stack:
            stack.enter_context(core_app.app.test_request_context('/api/issues/42/review', method='POST', data=data))
            stack.enter_context(patch.object(core_app, 'get_authenticated_request_user_id', return_value=user_id))
            stack.enter_context(patch.object(core_app, 'get_db_connection', return_value=conn))
            stack.enter_context(patch.object(core_app, 'ensure_issue_inspector_schema'))
            stack.enter_context(patch.object(core_app, 'close_db_resources'))
            saved = stack.enter_context(patch.object(core_app, 'save_uploaded_file', return_value='rectifications/review.jpg'))
            event = stack.enter_context(patch.object(core_app, 'record_issue_workflow_event'))
            value = core_app.submit_review(42)
            response, code = value if isinstance(value, tuple) else (value, 200)
            return response.get_json(), code, cur, conn, saved, event

    def test_rejection_without_photo_and_note_is_still_valid(self):
        body, code, cur, conn, saved, event = self.submit()
        self.assertEqual(code, 200)
        self.assertEqual(body['status'], '待整改')
        self.assertTrue(body['returned_to_station'])
        self.assertEqual(cur.execute.call_args.args[1], ('整改不通过', '', None, '待整改', 42))
        self.assertEqual(event.call_args.args[3:], ('review_submitted', '待复核', '待整改', '整改不通过', '', None))
        saved.assert_not_called()
        conn.commit.assert_called_once()

    def test_optional_rejection_photo_is_saved_in_current_issue_and_workflow_event(self):
        body, code, cur, conn, saved, event = self.submit(photo=True)
        self.assertEqual(code, 200)
        self.assertTrue(body['returned_to_station'])
        saved.assert_called_once()
        self.assertEqual(saved.call_args.args[0].filename, 'review.png')
        self.assertEqual(saved.call_args.args[1], 'rectifications')
        self.assertEqual(cur.execute.call_args.args[1], ('整改不通过', '', 'rectifications/review.jpg', '待整改', 42))
        self.assertEqual(event.call_args.args[-1], 'rectifications/review.jpg')
        conn.commit.assert_called_once()

    def test_approval_remains_mandatory_and_legacy_result_still_saves_photo(self):
        for result in ('整改通过', '已整改'):
            with self.subTest(result=result):
                _, code, _, conn, saved, event = self.submit(result=result)
                self.assertEqual(code, 400)
                saved.assert_not_called()
                event.assert_not_called()
                conn.commit.assert_not_called()
                body, code, _, _, saved, event = self.submit(result=result, photo=True)
                self.assertEqual(code, 200)
                self.assertEqual(body['status'], '已闭环')
                self.assertFalse(body['returned_to_station'])
                saved.assert_called_once()
                self.assertEqual(event.call_args.args[-1], 'rectifications/review.jpg')

    def test_unable_application_reviews_do_not_start_accepting_photos(self):
        for result in ('通过站级无法整改', '驳回站级无法整改'):
            with self.subTest(result=result):
                body, code, _, _, saved, event = self.submit(result=result, station_result='站经无法整改', photo=True)
                self.assertEqual(code, 200)
                self.assertEqual(body['status'], '站级无法整改' if result.startswith('通过') else '待整改')
                saved.assert_not_called()
                self.assertIsNone(event.call_args.args[-1])

    def test_invalid_state_branch_or_permission_does_not_save_optional_photo(self):
        for args, expected in [({'status':'待整改'}, 400), ({'station_result':'站经无法整改'}, 400),
                               ({'audit':'pending'}, 409), ({'audit':'rejected'}, 400),
                               ({'role':'station_manager'}, 403), ({'user_id':None}, 400)]:
            with self.subTest(args=args):
                _, code, _, conn, saved, event = self.submit(photo=True, **args)
                self.assertEqual(code, expected)
                saved.assert_not_called()
                event.assert_not_called()
                conn.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
