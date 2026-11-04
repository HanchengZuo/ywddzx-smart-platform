"""Independent queue permissions and fixed departmental boundaries."""
import os
import unittest
from contextlib import ExitStack
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from unittest.mock import MagicMock, patch

import app as api
from tests import test_issue_review_workflow as review_tests


class QueuePermissionTests(unittest.TestCase):
    def test_independent_endpoints_require_login(self):
        client=api.app.test_client()
        for path in ('/api/my-rectification-issues','/api/my-review-issues','/api/my-review-issues/filter-options'):
            self.assertEqual(client.get(path).status_code,401)

    def test_default_access_preserves_existing_roles_and_opens_department_review_only(self):
        for role in api.ROLE_OPTIONS:
            with self.subTest(role=role):
                review = role in {'root','supervisor','supervisor_manager',*api.ROLE_DEFAULT_CHECKLIST_SCOPES}
                rectify = role in {'root','station_manager'}
                for key in ('view_my_review_issues','submit_my_issue_reviews'):
                    self.assertEqual(api.role_default_permission(role,key), review)
                for key in ('view_my_rectification_issues','submit_my_rectification'):
                    self.assertEqual(api.role_default_permission(role,key), rectify)
        permissions=api.enforce_exclusive_permissions(dict(view_my_review_issues=False,submit_my_issue_reviews=True), 'finance')
        self.assertFalse(permissions['submit_my_issue_reviews'])
        permissions=api.enforce_exclusive_permissions(dict(view_my_rectification_issues=False,submit_my_rectification=True), 'station_manager')
        self.assertFalse(permissions['submit_my_rectification'])

    def test_switches_can_deny_legacy_roles_and_do_not_grant_unsupported_role_scope(self):
        with patch.object(api,'has_permission',return_value=False):
            self.assertFalse(api.can_view_review_queue(MagicMock(),dict(id=1,role='supervisor')))
            self.assertFalse(api.can_view_rectification_queue(MagicMock(),dict(id=2,role='station_manager')))
        with patch.object(api,'has_permission',return_value=True):
            self.assertFalse(api.can_view_review_queue(MagicMock(),dict(id=1,role='station_manager')))
            self.assertFalse(api.can_view_review_queue(MagicMock(),dict(id=2,role='area_account')))
            self.assertFalse(api.can_view_rectification_queue(MagicMock(),dict(id=3,role='finance')))

    def test_saved_role_and_personal_switches_keep_existing_precedence(self):
        user=dict(id=17,role='finance')
        with patch.object(api,'get_role_permission_overrides',return_value={'submit_my_issue_reviews':False}), \
             patch.object(api,'get_permission_overrides',return_value={'submit_my_issue_reviews':True}):
            self.assertTrue(api.has_permission(MagicMock(),user,'submit_my_issue_reviews'))
        with patch.object(api,'get_role_permission_overrides',return_value={'view_my_review_issues':False}), \
             patch.object(api,'get_permission_overrides',return_value={'submit_my_issue_reviews':True}):
            self.assertFalse(api.has_permission(MagicMock(),user,'view_my_review_issues'))
            self.assertFalse(api.has_permission(MagicMock(),user,'submit_my_issue_reviews'))
        with patch.object(api,'get_role_permission_overrides',return_value={}), \
             patch.object(api,'get_permission_overrides',return_value={'view_my_rectification_issues':False}):
            self.assertFalse(api.has_permission(MagicMock(),dict(id=18,role='station_manager'),'submit_my_rectification'))

    def test_legacy_hidden_page_is_inherited_without_preventing_independent_visibility(self):
        cur=MagicMock()
        cur.fetchall.return_value=[dict(page_key='/inspection/my-issues',is_visible=False),
            dict(page_key='/inspection/my-reviews',is_visible=True)]
        with patch.object(api,'ensure_system_page_visibility_schema'):
            settings=api.fetch_page_visibility_settings(cur)
        self.assertFalse(settings['/inspection/my-rectifications'])
        self.assertTrue(settings['/inspection/my-reviews'])


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST')=='1', 'isolated database opt-in')
class QueueScopeDatabaseTests(unittest.TestCase):
    connect=review_tests.UnableClosureDatabaseTests.connect
    tearDown=review_tests.UnableClosureDatabaseTests.tearDown

    def setUp(self):
        review_tests.UnableClosureDatabaseTests.setUp(self)
        self.user=dict(id=17,username='reviewer',real_name='复核人员',role='quality_safety',station_id=1)
        self.overrides={}
        self.cur.execute("""
          ALTER TABLE users ADD COLUMN station_id int DEFAULT 1;
          ALTER TABLE inspection_tables ADD COLUMN is_active boolean DEFAULT true;
          UPDATE inspection_tables SET table_name='质量安全环保检查表（现场）' WHERE id=1;
          INSERT INTO inspection_tables VALUES(2,'质量安全环保检查表（视频）','online',false),
            (3,'财务检查表（现场）','offline',true),(4,'设备设施检查表（现场）','offline',true),
            (5,'现场检查明细表（视频）','online',true),(6,'非油检查表（现场）','offline',true);
          CREATE TABLE stations(id int PRIMARY KEY,region text,station_name text,station_manager_name text,
            longitude numeric,latitude numeric);
          INSERT INTO stations VALUES(1,'片区甲','甲站','经理甲',121.5,31.2),(2,'片区乙','乙站','经理乙',121.4,31.3);
          CREATE TABLE inspections(id int PRIMARY KEY,inspector_id int,sign_status text,
            inspector_completion_status text);
          INSERT INTO inspections VALUES(1,17,'已签名确认','已确认完成');
          ALTER TABLE issues ADD COLUMN station_id int DEFAULT 1;
          ALTER TABLE issues ADD COLUMN inspection_id int DEFAULT 1;
          ALTER TABLE issues ADD COLUMN inspector_id int DEFAULT 17;
          ALTER TABLE issues ADD COLUMN created_at timestamp DEFAULT CURRENT_TIMESTAMP;
          ALTER TABLE issues ADD COLUMN standard_id text;
          ALTER TABLE issues ADD COLUMN standard_detail_text text;
          ALTER TABLE issues ADD COLUMN internal_standard_id text;
          ALTER TABLE issues ADD COLUMN internal_standard_detail_text text;
          ALTER TABLE issues ADD COLUMN description text;
          ALTER TABLE issues ADD COLUMN photo_path text;
          ALTER TABLE issues ADD COLUMN rectification_note text;
          ALTER TABLE issues ADD COLUMN rectification_at timestamp;
          ALTER TABLE issues ADD COLUMN rectification_photo_path text;
          ALTER TABLE issues ADD COLUMN is_excellent boolean DEFAULT false;
          ALTER TABLE issues ADD COLUMN audited_by int;
          ALTER TABLE issues ADD COLUMN audited_at timestamp;
          INSERT INTO issues(id,inspection_table_id,status,rectification_result,audit_status,description,station_id)
            SELECT 42+n,n,'待复核','已整改','approved','问题描述'||n,CASE WHEN n=2 THEN 2 ELSE 1 END
            FROM generate_series(2,6) n;
        """)
        self.admin.commit()
        self.stack=ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(api,'get_db_connection',side_effect=self.connect))
        self.stack.enter_context(patch.object(api,'get_authenticated_request_user_id',return_value=17))
        self.stack.enter_context(patch.object(api,'get_current_request_user',side_effect=lambda:self.user))
        self.stack.enter_context(patch.object(api,'has_permission',
            side_effect=lambda _,user,key:self.overrides.get(key,api.role_default_permission(user['role'],key))))
        for name in ('ensure_issue_inspector_schema','ensure_inspection_completion_schema',
                     'attach_internal_standard_tags_to_issue_rows'):
            self.stack.enter_context(patch.object(api,name))
        self.stack.enter_context(patch.object(api,'fetch_internal_standard_tags_by_codes',return_value={}))
        for name in ('can_edit_inspection_issues','can_delete_inspection_issues','can_change_issue_inspector'):
            self.stack.enter_context(patch.object(api,name,return_value=False))
        self.stack.enter_context(patch.object(api,'normalize_issue_row_for_response',side_effect=lambda row,*_:dict(row)))
        self.saved=self.stack.enter_context(patch.object(api,'save_uploaded_file',return_value='rectifications/test.jpg'))

    def role(self,role):
        self.user['role']=role
        self.cur.execute('UPDATE users SET role=%s WHERE id=17',(role,))
        self.admin.commit()

    def call(self,path,fn,*,method='GET',data=None):
        with api.app.test_request_context(path,method=method,data=data):
            result=fn()
            response,status=result if isinstance(result,tuple) else (result,200)
            return response.get_json(),status

    def test_all_departments_get_only_their_tables_in_list_filters_and_badges(self):
        for role,ids in [('quality_safety',{42,44}),('finance',{45}),('development_plan',{46}),
                         ('oil_gas',{47}),('non_oil',{48}),('supervisor',{42,44,45,46,47,48}),
                         ('supervisor_manager',{42,44,45,46,47,48})]:
            with self.subTest(role=role):
                self.role(role)
                body,status=self.call('/api/my-review-issues',api.get_my_issues)
                self.assertEqual(status,200,body)
                self.assertEqual({r['id'] for r in body['items']},ids)
                self.assertEqual(body['total'],len(ids))
                facets,status=self.call('/api/my-review-issues/filter-options',api.get_pending_review_filter_options)
                self.assertEqual(status,200)
                self.assertEqual(set(facets['filter_options']['inspection_tables']),
                                 {r['inspection_table_name'] for r in body['items']})
                self.assertEqual(api.get_my_pending_review_count_for_user(self.cur,self.user),len(ids))
        self.role('quality_safety')
        body,status=self.call('/api/my-review-issues?issue_id=45&inspection_tables=["财务检查表（现场）"]',
                              api.get_my_issues)
        self.assertEqual((status,body['total']),(200,0))

    def test_cross_department_submit_cannot_save_files_update_issue_or_write_history(self):
        self.role('quality_safety')
        body,status=self.call('/api/issues/45/review',lambda:api.submit_review(45),method='POST',
            data={'review_result':'整改通过','review_photo':(BytesIO(b'not-a-real-photo'),'x.png')})
        self.assertEqual(status,403,body)
        self.saved.assert_not_called()
        self.cur.execute('SELECT status FROM issues WHERE id=45')
        self.assertEqual(self.cur.fetchone()['status'],'待复核')
        self.cur.execute("SELECT count(*) AS n FROM inspection_issue_flow_history WHERE issue_id=45")
        self.assertEqual(self.cur.fetchone()['n'],0)

    def test_rectification_filters_keep_department_scope_and_ignore_removed_tags(self):
        self.role('quality_safety')
        self.cur.execute("UPDATE issues SET rectification_result='站级无法整改' WHERE id=44")
        self.admin.commit()
        for result, expected in [('已整改',set()), ('站级无法整改',{42,44})]:
            body,status=self.call('/api/my-review-issues?rectification_result='+result+'&standard_tags=["无关旧标签"]',api.get_my_issues)
            self.assertEqual(status,200,body)
            self.assertEqual({r['id'] for r in body['items']},expected)
            self.assertEqual(body['total'],len(expected))

    def test_read_only_and_denied_switches_apply_to_api_not_just_buttons(self):
        self.overrides['submit_my_issue_reviews']=False
        self.assertEqual(self.call('/api/my-review-issues',api.get_my_issues)[1],200)
        self.assertEqual(self.call('/api/issues/42/review',lambda:api.submit_review(42),method='POST',
            data={'review_result':'整改不通过'})[1],403)
        self.overrides['view_my_review_issues']=False
        self.assertEqual(self.call('/api/my-review-issues',api.get_my_issues)[1],403)
        self.assertEqual(self.call('/api/my-review-issues/filter-options',api.get_pending_review_filter_options)[1],403)
        self.assertEqual(api.get_my_pending_review_count_for_user(self.cur,self.user),0)
        self.role('station_manager')
        self.assertEqual(self.call('/api/my-review-issues',api.get_my_issues)[1],403)
        self.overrides['view_my_rectification_issues']=False
        self.assertEqual(self.call('/api/my-rectification-issues',api.get_my_issues)[1],403)
        self.assertEqual(api.get_my_pending_rectification_count_for_user(self.cur,self.user),0)

    def test_station_rectification_permission_still_restricts_station_and_preserves_workflow(self):
        self.role('station_manager')
        self.cur.execute("UPDATE issues SET status='待整改' WHERE id IN (42,44)")
        self.admin.commit()
        data=dict(rectification_result='站级无法整改',rectification_note='待上级处理')
        self.overrides['submit_my_rectification']=False
        self.assertEqual(self.call('/api/issues/42/rectification',lambda:api.submit_rectification(42),
                                  method='POST',data=data)[1],403)
        self.overrides.clear()
        self.assertEqual(api.get_my_pending_rectification_count_for_user(self.cur,self.user),1)
        self.assertEqual(self.call('/api/issues/44/rectification',lambda:api.submit_rectification(44),
                                  method='POST',data=data)[1],403)
        body,status=self.call('/api/issues/42/rectification',lambda:api.submit_rectification(42),
                              method='POST',data=data)
        self.assertEqual(status,200,body)
        self.cur.execute('SELECT status,rectification_result FROM issues WHERE id=42')
        self.assertEqual(dict(self.cur.fetchone()),dict(status='待复核',rectification_result='站经无法整改'))

    def test_department_can_review_historical_table_and_records_real_actor(self):
        self.role('quality_safety')
        body,status=self.call('/api/issues/44/review',lambda:api.submit_review(44),method='POST',
            data={'review_result':'整改通过'})
        self.assertEqual((status,body.get('status')),(200,'已闭环'))
        self.cur.execute('SELECT actor_user_id,actor_role,result FROM inspection_issue_flow_history WHERE issue_id=44')
        self.assertEqual(dict(self.cur.fetchone()),dict(actor_user_id=17,actor_role='quality_safety',result='整改通过'))
        self.assertTrue(api.can_user_view_issue_flow_history(self.cur,self.user,dict(inspection_table_id=2)))

    def test_audit_failure_rolls_back_department_review(self):
        self.cur.execute("ALTER TABLE inspection_issue_flow_history ADD CHECK(issue_id<>44) NOT VALID")
        self.admin.commit()
        body,status=self.call('/api/issues/44/review',lambda:api.submit_review(44),method='POST',
            data={'review_result':'整改通过'})
        self.assertEqual(status,500,body)
        self.cur.execute('SELECT status,review_result FROM issues WHERE id=44')
        self.assertEqual(dict(self.cur.fetchone()),dict(status='待复核',review_result=None))

    def test_concurrent_department_reviews_only_write_one_result_and_event(self):
        def submit(_):
            return self.call('/api/issues/44/review',lambda:api.submit_review(44),method='POST',
                             data={'review_result':'整改通过'})[1]
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses=list(pool.map(submit,range(2)))
        self.assertEqual(sorted(statuses),[200,400])
        self.cur.execute("SELECT count(*) AS n FROM inspection_issue_flow_history WHERE issue_id=44 AND action_type='review_submitted'")
        self.assertEqual(self.cur.fetchone()['n'],1)
