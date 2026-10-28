import unittest
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from io import BytesIO
from unittest.mock import MagicMock, patch
import psycopg2
from psycopg2.extras import RealDictCursor

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
        for result, station in [('整改不通过', '站经无法整改'), ('通过站级无法整改', '已整改'), ('驳回站级无法整改', '已整改'), ('整改通过', '')]:
            with self.subTest(result=result, station=station), self.assertRaises(ValueError):
                resolve_issue_review_transition(result, station)

    def test_unable_application_can_be_approved_as_rectified_without_changing_the_station_submission(self):
        for station in ('站经无法整改', '站级无法整改', '站经理无法整改'):
            with self.subTest(station=station):
                transition = resolve_issue_review_transition('整改通过', station)
                self.assertEqual(transition, dict(review_result='整改通过', new_status='已闭环',
                    photo_required=True, photo_allowed=True, returns_to_station=False))

    def test_legacy_ordinary_approval_is_compatible(self):
        self.assertEqual(resolve_issue_review_transition('已整改', '已整改')['review_result'], '整改通过')

    def test_rectified_review_closes_issue_and_requires_photo(self):
        transition = resolve_issue_review_transition("已整改")

        self.assertEqual(transition["new_status"], "已闭环")
        self.assertTrue(transition["photo_required"])
        self.assertTrue(transition["photo_allowed"])
        self.assertFalse(transition["returns_to_station"])

    def test_video_approval_photo_is_optional_without_changing_closure_or_other_branches(self):
        for station in ('已整改', '站经无法整改'):
            transition = resolve_issue_review_transition('整改通过', station, 'online')
            self.assertFalse(transition['photo_required'])
            self.assertTrue(transition['photo_allowed'])
            self.assertEqual(transition['new_status'], '已闭环')
        for mode in ('offline', None, '', 'invalid'):
            self.assertTrue(resolve_issue_review_transition('整改通过', '已整改', mode)['photo_required'])

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
               status='待复核', role='supervisor', audit='approved', user_id=17,
               checklist_mode='offline', posted_mode=None):
        conn, cur = MagicMock(), MagicMock()
        conn.cursor.return_value = cur
        user = dict(id=17, username='reviewer', real_name='复核人员', role=role)
        cur.fetchone.side_effect = [user, dict(id=42, status=status,
            rectification_result=station_result, audit_status=audit, checklist_mode=checklist_mode)]
        data = dict(user_id='17', review_result=result, review_note='')
        if posted_mode is not None:
            data['checklist_mode'] = posted_mode
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

    def test_both_supervisor_roles_can_review_without_expanding_other_roles(self):
        for role in ('supervisor_manager', 'supervisor'):
            body, code, _, conn, _, event = self.submit(role=role)
            self.assertEqual((code, body['status']), (200, '待整改'))
            conn.commit.assert_called_once()
            event.assert_called_once()

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

    def test_unable_application_rectified_approval_closes_and_records_current_round_photo(self):
        for role in ('supervisor', 'supervisor_manager'):
            with self.subTest(role=role):
                body, code, cur, conn, saved, event = self.submit(result='整改通过', station_result='站经无法整改', photo=True, role=role)
                self.assertEqual(code, 200)
                self.assertEqual(body['status'], '已闭环')
                self.assertFalse(body['returned_to_station'])
                self.assertEqual(cur.execute.call_args.args[1], ('整改通过', '', 'rectifications/review.jpg', '已闭环', 42))
                self.assertEqual(event.call_args.args[3:], ('review_submitted', '待复核', '已闭环', '整改通过', '', 'rectifications/review.jpg'))
                saved.assert_called_once()
                conn.commit.assert_called_once()

    def test_unable_rectified_approval_still_requires_photo_and_uses_existing_authorization_and_state_guards(self):
        for args, expected in [({}, 400), ({'photo':True, 'role':'station_manager'}, 403),
                               ({'photo':True, 'audit':'pending'}, 409), ({'photo':True, 'status':'已闭环'}, 400)]:
            with self.subTest(args=args):
                _, code, _, conn, saved, event = self.submit(result='整改通过', station_result='站经无法整改', **args)
                self.assertEqual(code, expected)
                saved.assert_not_called(); event.assert_not_called(); conn.commit.assert_not_called()

    def test_video_approval_accepts_no_photo_or_saves_optional_photo_for_both_rectification_branches(self):
        for station in ('已整改', '站经无法整改'):
            for photo in (False, True):
                with self.subTest(station=station, photo=photo):
                    body, code, cur, conn, saved, event = self.submit(result='整改通过', station_result=station,
                        checklist_mode='online', photo=photo)
                    self.assertEqual((code,body['status'],body['returned_to_station']),(200,'已闭环',False))
                    path = 'rectifications/review.jpg' if photo else None
                    self.assertEqual(cur.execute.call_args.args[1],('整改通过','',path,'已闭环',42))
                    self.assertEqual(event.call_args.args[-1],path)
                    self.assertEqual(saved.call_count,int(photo))
                    conn.commit.assert_called_once()

    def test_client_cannot_waive_offline_photo_or_bypass_review_guards_by_claiming_video(self):
        for args, code in [({'checklist_mode':'offline','posted_mode':'online'},400),
                           ({'checklist_mode':None,'posted_mode':'online'},400),
                           ({'checklist_mode':'online','role':'station_manager'},403),
                           ({'checklist_mode':'online','audit':'pending'},409),
                           ({'checklist_mode':'online','status':'已闭环'},400)]:
            with self.subTest(args=args):
                _, status, _, conn, saved, event = self.submit(result='整改通过', **args)
                self.assertEqual(status,code)
                saved.assert_not_called(); event.assert_not_called(); conn.commit.assert_not_called()

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


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST') == '1', 'isolated database opt-in')
class UnableClosureDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.config = core_app.get_db_config()
        if not self.config['dbname'].startswith('test_schedule_'):
            raise RuntimeError('Refusing non-test database')
        self.schema = 'review_' + uuid.uuid4().hex
        self.admin = psycopg2.connect(**self.config, cursor_factory=RealDictCursor)
        self.cur = self.admin.cursor()
        self.cur.execute(f'CREATE SCHEMA {self.schema}; SET search_path TO {self.schema}')
        self.cur.execute('''CREATE TABLE users(id int PRIMARY KEY,username text,real_name text,role text);
          INSERT INTO users VALUES(17,'reviewer','复核人员','supervisor');
          CREATE TABLE inspection_tables(id int PRIMARY KEY,table_name text,checklist_mode text);
          INSERT INTO inspection_tables VALUES(1,'名字含视频但属性为现场','offline');
          CREATE TABLE issues(id int PRIMARY KEY,inspection_table_id int REFERENCES inspection_tables(id),status text,rectification_result text,audit_status text,
            review_result text,review_note text,review_at timestamp,review_photo_path text);
          INSERT INTO issues(id,inspection_table_id,status,rectification_result,audit_status) VALUES(42,1,'待复核','站经无法整改','approved');
          CREATE TABLE inspection_issue_flow_history(id serial PRIMARY KEY,issue_id int REFERENCES issues(id),round_no int,
            action_type text,from_status text,to_status text,result text,note text,photo_path text,
            actor_user_id int REFERENCES users(id),actor_username text,actor_name text,actor_role text);
          INSERT INTO inspection_issue_flow_history(issue_id,round_no,action_type,from_status,to_status,result)
            VALUES(42,1,'rectification_submitted','待整改','待复核','站经无法整改');''')
        self.admin.commit()

    def tearDown(self):
        self.admin.rollback()
        self.cur.execute(f'DROP SCHEMA {self.schema} CASCADE'); self.admin.commit()
        self.cur.close(); self.admin.close()

    def connect(self):
        return psycopg2.connect(**self.config, cursor_factory=RealDictCursor, options=f'-c search_path={self.schema}')

    def submit(self, *, photo=True, claimed_mode=None):
        data = dict(review_result='整改通过',review_note='',checklist_mode=claimed_mode or '')
        if photo: data['review_photo'] = (BytesIO(b'fixture-only'),'review.png')
        with core_app.app.test_request_context('/api/issues/42/review',method='POST',data=data):
            value = core_app.submit_review(42)
            response, code = value if isinstance(value,tuple) else (value,200)
            return response.get_json(), code

    def dependencies(self):
        stack = ExitStack()
        stack.enter_context(patch.object(core_app,'get_authenticated_request_user_id',return_value=17))
        stack.enter_context(patch.object(core_app,'get_db_connection',side_effect=self.connect))
        stack.enter_context(patch.object(core_app,'ensure_issue_inspector_schema'))
        # No real upload or business file is created during database verification.
        stack.enter_context(patch.object(core_app,'save_uploaded_file',return_value='rectifications/fixture.jpg'))
        return stack

    def test_closure_commits_canonical_result_and_audit_without_rewriting_station_request(self):
        with self.dependencies():
            body, code = self.submit()
        self.assertEqual((code,body['status'],body['returned_to_station']),(200,'已闭环',False))
        self.cur.execute('SELECT status,rectification_result,review_result,review_note,review_photo_path FROM issues WHERE id=42')
        self.assertEqual(dict(self.cur.fetchone()),dict(status='已闭环',rectification_result='站经无法整改',review_result='整改通过',review_note='',review_photo_path='rectifications/fixture.jpg'))
        self.cur.execute("SELECT round_no,from_status,to_status,result,photo_path,actor_user_id FROM inspection_issue_flow_history WHERE action_type='review_submitted'")
        self.assertEqual(dict(self.cur.fetchone()),dict(round_no=1,from_status='待复核',to_status='已闭环',result='整改通过',photo_path='rectifications/fixture.jpg',actor_user_id=17))
        self.assertEqual(classify_non_oil_rectification(dict(status='已闭环',rectification_result='站经无法整改',review_result='整改通过')),'completed')

    def test_history_failure_rolls_back_status_and_review_fields(self):
        self.cur.execute("ALTER TABLE inspection_issue_flow_history ADD CHECK(action_type<>'review_submitted') NOT VALID")
        self.admin.commit()
        with self.dependencies():
            _, code = self.submit()
        self.assertEqual(code,500)
        self.cur.execute('SELECT status,review_result,review_at,review_photo_path FROM issues WHERE id=42')
        self.assertEqual(dict(self.cur.fetchone()),dict(status='待复核',review_result=None,review_at=None,review_photo_path=None))
        self.cur.execute('SELECT COUNT(*) n FROM inspection_issue_flow_history')
        self.assertEqual(self.cur.fetchone()['n'],1)

    def test_concurrent_reviews_close_once_without_duplicate_review_events(self):
        with self.dependencies(), ThreadPoolExecutor(max_workers=2) as pool:
            codes = sorted(code for _,code in pool.map(lambda _:self.submit(),range(2)))
        self.assertEqual(codes,[200,400])
        self.cur.execute("SELECT COUNT(*) n FROM inspection_issue_flow_history WHERE action_type='review_submitted'")
        self.assertEqual(self.cur.fetchone()['n'],1)

    def test_video_without_photo_closes_using_database_attribute_not_table_name(self):
        self.cur.execute("UPDATE inspection_tables SET checklist_mode='online',table_name='自定义检查表' WHERE id=1")
        self.admin.commit()
        with self.dependencies():
            body, code = self.submit(photo=False, claimed_mode='offline')
        self.assertEqual((code,body['status']),(200,'已闭环'))
        self.cur.execute('SELECT status,review_result,review_photo_path FROM issues WHERE id=42')
        self.assertEqual(dict(self.cur.fetchone()),dict(status='已闭环',review_result='整改通过',review_photo_path=None))
        self.cur.execute("SELECT photo_path,result,to_status FROM inspection_issue_flow_history WHERE action_type='review_submitted'")
        self.assertEqual(dict(self.cur.fetchone()),dict(photo_path=None,result='整改通过',to_status='已闭环'))

    def test_video_optional_photo_is_still_stored(self):
        self.cur.execute("UPDATE inspection_tables SET checklist_mode='online' WHERE id=1"); self.admin.commit()
        with self.dependencies():
            _, code = self.submit(photo=True)
        self.assertEqual(code,200)
        self.cur.execute("SELECT photo_path FROM inspection_issue_flow_history WHERE action_type='review_submitted'")
        self.assertEqual(self.cur.fetchone()['photo_path'],'rectifications/fixture.jpg')

    def test_offline_without_photo_cannot_be_overridden_by_video_form_field(self):
        with self.dependencies():
            body, code = self.submit(photo=False, claimed_mode='online')
        self.assertEqual(code,400); self.assertEqual(body['error'],'请上传复核照片。')
        self.cur.execute('SELECT status,review_result FROM issues WHERE id=42')
        self.assertEqual(dict(self.cur.fetchone()),dict(status='待复核',review_result=None))
        self.cur.execute('SELECT COUNT(*) n FROM inspection_issue_flow_history')
        self.assertEqual(self.cur.fetchone()['n'],1)


if __name__ == "__main__":
    unittest.main()
