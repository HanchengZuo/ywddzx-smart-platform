"""Independent queue permissions and fixed departmental boundaries."""
import importlib
import os
import unittest
from contextlib import ExitStack
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from unittest.mock import MagicMock, patch

import psycopg2
import app as api
from tests import test_issue_review_workflow as review_tests


class QueuePermissionTests(unittest.TestCase):
    def test_independent_endpoints_require_login(self):
        client=api.app.test_client()
        for path in ('/api/my-rectification-issues','/api/my-review-issues','/api/my-review-issues/filter-options'):
            self.assertEqual(client.get(path).status_code,401)
        self.assertEqual(client.post('/api/issues/44/review-transfer',json={'reason':'fixture'}).status_code,401)
        self.assertEqual(client.post('/api/issues/48/non-oil-field-transfer',json={'reason':'fixture'}).status_code,401)

    def test_default_access_preserves_existing_roles_and_opens_non_oil_area_review(self):
        for role in api.ROLE_OPTIONS:
            with self.subTest(role=role):
                review = role in {'root','supervisor','supervisor_manager',*api.ROLE_DEFAULT_CHECKLIST_SCOPES,
                                  *api.non_oil_review.AREA_REVIEW_ROLES}
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
            self.assertTrue(api.can_view_review_queue(MagicMock(),dict(id=2,role='area_account')))
            self.assertFalse(api.can_view_review_queue(MagicMock(),dict(id=2,role='area_oil_gas')))
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
class OdorOwnershipMigrationTests(unittest.TestCase):
    tearDown=review_tests.UnableClosureDatabaseTests.tearDown

    def setUp(self):
        review_tests.UnableClosureDatabaseTests.setUp(self)
        self.migration=importlib.import_module('migrations.versions.20261105_001_review_perspectives')
        self.cur.execute("""
            INSERT INTO inspection_tables VALUES
                (7,'环境无异味管理检查表（现场）','offline'),
                (8,'环境无异味管理检查表','offline'),
                (9,'现场检查明细表（现场）','offline');
            CREATE TABLE role_inspection_table_scopes (
                role text,scope_key text,inspection_table_id integer,updated_by integer,
                created_at timestamp DEFAULT CURRENT_TIMESTAMP,updated_at timestamp DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(role,scope_key,inspection_table_id));
            INSERT INTO role_inspection_table_scopes(role,scope_key,inspection_table_id,updated_by) VALUES
                ('oil_gas','limit_issue_inspection_table_scope',7,17),
                ('oil_gas','limit_record_inspection_table_scope',8,17),
                ('oil_gas','limit_issue_inspection_table_scope',9,17),
                ('quality_safety','limit_issue_inspection_table_scope',7,17);
            CREATE TABLE user_inspection_table_scopes(user_id integer,inspection_table_id integer);
            INSERT INTO user_inspection_table_scopes VALUES(17,7);
            CREATE TABLE security_audit_logs(actor_username text,actor_role text,action_type text,
                action_result text,affected_count integer,details jsonb,created_at timestamp);
        """)
        self.admin.commit()

    def migrate(self):
        with patch.object(self.migration.op,'execute',side_effect=self.cur.execute):
            self.migration.upgrade()

    def test_targeted_correction_is_audited_and_idempotent(self):
        self.migrate()
        self.migrate()
        self.cur.execute('SELECT role,inspection_table_id FROM role_inspection_table_scopes ORDER BY role')
        self.assertEqual([(r['role'],r['inspection_table_id']) for r in self.cur.fetchall()],
                         [('oil_gas',9),('quality_safety',7)])
        self.cur.execute('SELECT * FROM user_inspection_table_scopes')
        self.assertEqual(self.cur.fetchall(),[dict(user_id=17,inspection_table_id=7)])
        self.cur.execute('SELECT * FROM security_audit_logs')
        logs=self.cur.fetchall()
        self.assertEqual(len(logs),1)
        self.assertEqual(logs[0]['affected_count'],2)
        self.assertEqual({r['inspection_table_id'] for r in logs[0]['details']['removed_scopes']},{7,8})
        self.assertTrue(all(r['updated_by']==17 and r['created_at'] for r in logs[0]['details']['removed_scopes']))

    def test_audit_failure_rolls_back_the_scope_removal(self):
        self.cur.execute("ALTER TABLE security_audit_logs ADD CONSTRAINT deny_test_audit CHECK(action_type <> 'oil_gas_odor_scope_migrated')")
        self.admin.commit()
        with self.assertRaises(psycopg2.IntegrityError):
            self.migrate()
        self.admin.rollback()
        self.cur.execute('SELECT count(*) AS n FROM role_inspection_table_scopes')
        self.assertEqual(self.cur.fetchone()['n'],4)
        self.cur.execute('SELECT count(*) AS n FROM security_audit_logs')
        self.assertEqual(self.cur.fetchone()['n'],0)


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST')=='1', 'isolated database opt-in')
class QueueScopeDatabaseTests(unittest.TestCase):
    connect=review_tests.UnableClosureDatabaseTests.connect
    tearDown=review_tests.UnableClosureDatabaseTests.tearDown

    def setUp(self):
        review_tests.UnableClosureDatabaseTests.setUp(self)
        self.user=dict(id=17,username='reviewer',real_name='复核人员',role='quality_safety',station_id=1)
        self.overrides={}
        self.regions={'片区甲'}
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
        self.stack.enter_context(patch.object(api,'non_oil_area_review_regions',side_effect=lambda *_:self.regions))
        self.stack.enter_context(patch.object(api,'has_permission',
            side_effect=lambda _,user,key:self.overrides.get(key,api.role_default_permission(user['role'],key))))
        for name in ('ensure_issue_inspector_schema','ensure_inspection_completion_schema',
                     'attach_internal_standard_tags_to_issue_rows'):
            self.stack.enter_context(patch.object(api,name))
        self.stack.enter_context(patch.object(api,'fetch_internal_standard_tags_by_codes',return_value={}))
        for name in ('can_edit_inspection_issues','can_delete_inspection_issues','can_change_issue_inspector'):
            self.stack.enter_context(patch.object(api,name,return_value=False))
        self.stack.enter_context(patch.object(api,'normalize_issue_row_for_response',side_effect=lambda row,*_,**kwargs:dict(row)))
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

    def transfer(self, issue_id=44, reason='需要质安部复核'):
        with api.app.test_request_context(f'/api/issues/{issue_id}/review-transfer', method='POST', json={'reason':reason}):
            value=api.transfer_review_to_quality(issue_id)
            response,status=value if isinstance(value,tuple) else (value,200)
            return response.get_json(),status

    def non_oil_review(self, token='0', result='整改通过'):
        return self.call('/api/issues/48/review', lambda:api.submit_review(48), method='POST',
                         data={'review_result':result, 'non_oil_review_token':token, 'review_note':'复核意见'})

    def transfer_to_field(self, token):
        with api.app.test_request_context('/api/issues/48/non-oil-field-transfer', method='POST',
                                          json={'reason':'请现场核对', 'non_oil_review_token':token}):
            result=api.transfer_non_oil_review_to_field(48)
            response,status=result if isinstance(result,tuple) else (result,200)
            return response.get_json(),status

    def non_oil_row(self):
        body,status=self.call('/api/my-review-issues?issue_id=48',api.get_my_issues)
        self.assertEqual(status,200,body)
        return next(iter(body['items']), None)

    def test_non_oil_handoff_preserves_pending_state_and_finalizes_only_after_field_review(self):
        self.role('non_oil')
        row=self.non_oil_row()
        self.assertEqual(row['non_oil_review_stage'],'area')
        self.assertFalse(row['review_can_act'])
        self.assertEqual(self.non_oil_review()[1],409)
        self.assertEqual(self.transfer_to_field('0')[1],409)
        for role in ('supervisor','supervisor_manager'):
            self.role(role)
            self.assertIsNone(self.non_oil_row())
            self.assertEqual(self.non_oil_review()[1],403)
        self.role('area_non_oil')
        self.regions={'片区乙'}
        self.assertIsNone(self.non_oil_row())
        self.assertEqual(self.non_oil_review()[1],403)
        self.regions={'片区甲'}
        self.assertTrue(self.non_oil_row()['review_can_act'])
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses=list(pool.map(lambda _:self.non_oil_review()[1], range(2)))
        self.assertEqual(sorted(statuses),[200,403])
        self.assertIsNone(self.non_oil_row())
        self.role('non_oil')
        row=self.non_oil_row()
        self.assertTrue(row['can_transfer_to_field'])
        self.assertEqual(api.get_my_pending_review_count_for_user(self.cur,self.user),1)
        first_department_token=row['non_oil_review_token']
        self.assertEqual(self.transfer_to_field(first_department_token)[1],200)
        self.assertEqual(self.transfer_to_field(first_department_token)[1],409)
        self.assertFalse(self.non_oil_row()['review_can_act'])
        self.role('supervisor')
        row=self.non_oil_row()
        self.assertEqual(row['non_oil_review_stage'],'field')
        self.assertTrue(row['review_can_act'])
        body,status=self.non_oil_review(row['non_oil_review_token'])
        self.assertEqual((status,body['status']),(200,'待复核'))
        self.cur.execute('SELECT review_result,review_at FROM issues WHERE id=48')
        self.assertEqual(self.cur.fetchone(),dict(review_result=None,review_at=None))
        self.role('non_oil')
        self.assertEqual(self.non_oil_review(first_department_token)[1],409)
        body,status=self.non_oil_review(self.non_oil_row()['non_oil_review_token'])
        self.assertEqual((status,body['status']),(200,'已闭环'))
        self.cur.execute('SELECT non_oil_review_stage,non_oil_review_event_id FROM issues WHERE id=48')
        self.assertEqual(self.cur.fetchone(),dict(non_oil_review_stage=None,non_oil_review_event_id=None))
        self.cur.execute('SELECT action_type,actor_role,round_no FROM inspection_issue_flow_history WHERE issue_id=48 ORDER BY id')
        self.assertEqual([(r['action_type'],r['actor_role'],r['round_no']) for r in self.cur.fetchall()],[
            ('non_oil_area_review_passed','area_non_oil',1), ('non_oil_field_review_requested','non_oil',1),
            ('non_oil_field_review_passed','supervisor',1), ('review_submitted','non_oil',1)])

    def test_non_oil_unable_passes_are_preliminary_and_all_rejections_return_to_station(self):
        for stage in ('area','department','field'):
            with self.subTest(stage=stage):
                self.cur.execute("UPDATE issues SET status='待整改' WHERE id=48")
                self.admin.commit()
                self.role('station_manager')
                path='/api/issues/48/rectification'
                submit=lambda:api.submit_rectification(48)
                for data,error in [
                    ({'rectification_result':'站级无法整改'},'请填写整改说明。'),
                    ({'rectification_result':'已整改','rectification_note':'修好了'},'请上传整改照片。'),
                ]:
                    body,status=self.call(path,submit,method='POST',data=data)
                    self.assertEqual((status,body['error']),(400,error))
                _,status=self.call(path,submit,method='POST',
                                  data={'rectification_result':'站级无法整改','rectification_note':'需上级处理'})
                self.assertEqual(status,200)
                self.role('area_account')
                token=self.non_oil_row()['non_oil_review_token']
                self.assertNotEqual(token,'0')
                if stage != 'area':
                    body,status=self.non_oil_review(token,'通过站级无法整改' if stage=='field' else '整改通过')
                    self.assertEqual((status,body['status']),(200,'待复核'))
                    self.role('non_oil')
                    token=self.non_oil_row()['non_oil_review_token']
                if stage == 'field':
                    self.assertEqual(self.transfer_to_field(token)[1],200)
                    self.role('supervisor_manager')
                    token=self.non_oil_row()['non_oil_review_token']
                body,status=self.non_oil_review(token,'驳回站级无法整改')
                self.assertEqual((status,body['status'],body['returned_to_station']),(200,'待整改',True))
                self.cur.execute('SELECT non_oil_review_stage,review_result FROM issues WHERE id=48')
                self.assertEqual(self.cur.fetchone(),dict(non_oil_review_stage=None,review_result='驳回站级无法整改'))

    def test_non_oil_history_and_stage_roll_back_together(self):
        self.role('area_account')
        with patch.object(api.non_oil_review,'advance',side_effect=RuntimeError('fixture failure')):
            self.assertEqual(self.non_oil_review()[1],500)
        self.cur.execute("SELECT count(*) AS n FROM inspection_issue_flow_history WHERE issue_id=48")
        self.assertEqual(self.cur.fetchone()['n'],0)
        self.assertEqual(self.non_oil_row()['non_oil_review_token'],'0')
        self.assertEqual(self.non_oil_review()[1],200)

    def prepare_handoff_outbox(self):
        self.role('supervisor_manager')
        self.cur.execute("""
            ALTER TABLE users ADD COLUMN account_status text DEFAULT 'active';
            ALTER TABLE inspections ADD COLUMN station_id int DEFAULT 1, ADD COLUMN inspection_table_id int DEFAULT 1;
            INSERT INTO users(id,username,real_name,role,account_status) VALUES
              (18,'quality','可办理','quality_safety','active'),
              (19,'quality_read_only','只读','quality_safety','active'),
              (20,'inactive','停用','quality_safety','disabled'),
              (21,'finance','财务','finance','active');
        """)
        for name in ('20261101_001_web_push','20261101_002_business_push'):
            migration=importlib.import_module('migrations.versions.'+name)
            with patch.object(migration.op,'execute',side_effect=self.cur.execute):
                migration.upgrade()
        self.cur.execute("""
            INSERT INTO web_push_devices(id,user_id,device_hash,subscription_cipher,revision,platform,browser,capability,permission,active)
            VALUES('00000000-0000-4000-8000-000000000001',18,'fixture','test-only',
                   '00000000-0000-4000-8000-000000000002','fixture','fixture','supported','granted',true)
        """)
        self.admin.commit()

    def test_handoff_moves_only_current_round_and_notifies_eligible_recipients_once(self):
        from web_push_business import delivery_allowed
        self.prepare_handoff_outbox()
        self.assertEqual(self.transfer(45)[1],403)
        self.assertEqual(self.transfer(reason='  ')[1],400)
        with patch.object(api,'has_permission',side_effect=lambda _,u,key: u['id']!=19 or key!='submit_my_issue_reviews'):
            with ThreadPoolExecutor(max_workers=2) as pool:
                statuses=list(pool.map(lambda _:self.transfer()[1],range(2)))
        self.assertEqual(sorted(statuses),[200,409])
        self.cur.execute("SELECT event_key,entity_id,source FROM web_push_messages")
        messages=self.cur.fetchall()
        self.assertEqual(len(messages),1)
        self.cur.execute("SELECT user_id FROM web_push_recipients")
        self.assertEqual([row['user_id'] for row in self.cur.fetchall()],[18])
        self.cur.execute("SELECT user_id,status FROM web_push_deliveries")
        self.assertEqual(self.cur.fetchall(),[dict(user_id=18,status='queued')])
        self.assertTrue(delivery_allowed(self.cur,messages[0],18,lambda *args:[18]))
        self.assertFalse(delivery_allowed(self.cur,messages[0],18,lambda *args:[]))
        self.assertEqual(api.get_my_pending_review_count_for_user(self.cur,self.user),1)
        self.assertEqual(self.call('/api/issues/44/review',lambda:api.submit_review(44),
                                  method='POST',data={'review_result':'整改通过'})[1],403)
        self.role('quality_safety')
        body,status=self.call('/api/my-review-issues',api.get_my_issues)
        self.assertEqual(status,200,body)
        self.assertEqual([r['id'] for r in body['items']],[44])
        self.assertEqual(body['items'][0]['quality_review_handoff_reason'],'需要质安部复核')
        self.assertEqual(api.get_my_pending_review_count_for_user(self.cur,self.user),1)
        self.assertEqual(self.call('/api/issues/42/review',lambda:api.submit_review(42),
                                  method='POST',data={'review_result':'整改通过'})[1],403)
        self.assertEqual(self.transfer(42)[1],403)
        body,status=self.call('/api/issues/44/review',lambda:api.submit_review(44),
                              method='POST',data={'review_result':'整改不通过'})
        self.assertEqual((status,body.get('status')),(200,'待整改'))
        self.assertFalse(delivery_allowed(self.cur,messages[0],18,lambda *args:[18]))
        self.cur.execute("UPDATE issues SET status='待复核',rectification_at=now() WHERE id=44")
        self.admin.commit()
        self.assertEqual(api.get_my_pending_review_count_for_user(self.cur,self.user),0)
        self.role('supervisor')
        self.assertEqual(api.get_my_pending_review_count_for_user(self.cur,self.user),2)
        self.cur.execute("SELECT action_type FROM inspection_issue_flow_history WHERE issue_id=44 ORDER BY id")
        self.assertEqual([r['action_type'] for r in self.cur.fetchall()],['review_transferred_to_quality','review_submitted'])

    def test_handoff_rejects_no_recipients_and_rolls_back_when_outbox_fails(self):
        self.prepare_handoff_outbox()
        self.overrides['submit_my_issue_reviews']=False
        self.assertEqual(self.transfer()[1],403)
        self.overrides.clear()
        self.cur.execute("UPDATE users SET account_status='disabled' WHERE role='quality_safety'")
        self.admin.commit()
        self.assertEqual(self.transfer()[1],409)
        self.cur.execute("UPDATE users SET account_status='active' WHERE id=18")
        self.cur.execute("ALTER TABLE web_push_messages ADD CHECK(source<>'quality_review_handoff')")
        self.admin.commit()
        self.assertEqual(self.transfer()[1],500)
        self.cur.execute("SELECT quality_review_handoff_id FROM issues WHERE id=44")
        self.assertIsNone(self.cur.fetchone()['quality_review_handoff_id'])
        self.cur.execute("SELECT count(*) AS n FROM inspection_issue_flow_history WHERE issue_id=44")
        self.assertEqual(self.cur.fetchone()['n'],0)

    def test_handoff_and_direct_review_cannot_both_win(self):
        self.prepare_handoff_outbox()
        with ThreadPoolExecutor(max_workers=2) as pool:
            transfer=pool.submit(self.transfer)
            review=pool.submit(self.call, '/api/issues/44/review', lambda:api.submit_review(44),
                               method='POST', data={'review_result':'整改通过'})
            statuses=(transfer.result()[1],review.result()[1])
        self.assertIn(statuses,[(200,403),(409,200)])
        self.cur.execute("SELECT count(*) AS n FROM inspection_issue_flow_history WHERE issue_id=44")
        self.assertEqual(self.cur.fetchone()['n'],1)
        self.cur.execute("SELECT count(*) AS n FROM web_push_messages")
        self.assertEqual(self.cur.fetchone()['n'],int(statuses[0]==200))

    def test_all_departments_get_only_their_tables_in_list_filters_and_badges(self):
        for role,ids in [('quality_safety',set()),('finance',{45}),('development_plan',{46}),
                         ('oil_gas',{47}),('non_oil',{48}),('supervisor',{42,44}),
                         ('supervisor_manager',{42,44}),('root',{42,44,45,46,47,48}),
                         ('area_account',{48}),('area_non_oil',{48})]:
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
                if role not in ('root', 'quality_safety'):
                    self.assertTrue({r['inspection_table_name'] for r in body['items']}.issubset(
                        {r['table_name'] for r in facets['scope_tables']}))
                self.assertEqual(api.get_my_pending_review_count_for_user(self.cur,self.user),
                                 0 if role == 'non_oil' else len(ids))
        self.role('quality_safety')
        body,status=self.call('/api/my-review-issues?issue_id=45&inspection_tables=["财务检查表（现场）"]',
                              api.get_my_issues)
        self.assertEqual((status,body['total']),(200,0))

    def test_supervisor_cannot_filter_or_review_delegated_departments_including_inactive_tables(self):
        self.cur.execute("UPDATE inspection_tables SET is_active=false WHERE id IN (3,4,5)")
        self.admin.commit()
        for role in ('supervisor','supervisor_manager'):
            self.role(role)
            for issue_id in (45,46,47):
                body,status=self.call('/api/my-review-issues?issue_id='+str(issue_id),api.get_my_issues)
                self.assertEqual((status,body['total']),(200,0))
                body,status=self.call('/api/issues/'+str(issue_id)+'/review',
                    lambda:api.submit_review(issue_id),method='POST',
                    data={'review_result':'整改不通过','review_photo':(BytesIO(b'fixture'),'fixture.png')})
                self.assertEqual(status,403,body)
            self.saved.assert_not_called()
        self.cur.execute('SELECT count(*) AS n FROM inspection_issue_flow_history WHERE issue_id IN (45,46,47)')
        self.assertEqual(self.cur.fetchone()['n'],0)

    def test_odor_belongs_only_to_quality_and_remains_in_supervision_center(self):
        self.cur.execute("INSERT INTO inspection_tables VALUES(7,'环境无异味管理检查表（现场）','offline',true)")
        self.cur.execute("INSERT INTO issues(id,inspection_table_id,status,rectification_result,audit_status) VALUES(49,7,'待复核','已整改','approved')")
        self.admin.commit()
        for role, visible in [('quality_safety',False),('oil_gas',False),('supervisor',True),('supervisor_manager',True)]:
            self.role(role)
            body,status=self.call('/api/my-review-issues?issue_id=49',api.get_my_issues)
            self.assertEqual((status,body['total']),(200,1 if visible else 0))
        self.role('oil_gas')
        self.assertNotIn(7,api.get_role_default_inspection_table_ids(self.cur,'oil_gas'))
        self.assertIn(7,api.get_role_default_inspection_table_ids(self.cur,'quality_safety'))
        self.assertEqual(self.call('/api/issues/49/review',lambda:api.submit_review(49),method='POST',
                                  data={'review_result':'整改不通过'})[1],403)

    def test_delegated_departments_can_still_review_their_own_tables(self):
        for role,issue_id in [('development_plan',46),('oil_gas',47),('finance',45)]:
            self.role(role)
            body,status=self.call('/api/issues/'+str(issue_id)+'/review',lambda:api.submit_review(issue_id),
                                  method='POST',data={'review_result':'整改不通过','review_note':'部门复核'})
            self.assertEqual((status,body.get('status')),(200,'待整改'))
            self.cur.execute("SELECT actor_role FROM inspection_issue_flow_history WHERE issue_id=%s AND action_type='review_submitted'",(issue_id,))
            self.assertEqual(self.cur.fetchone()['actor_role'],role)

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
        for issue_id in (42, 44):
            review_tests.mark_quality_handoff(self.cur, issue_id)
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
        review_tests.mark_quality_handoff(self.cur, 44)
        self.admin.commit()
        body,status=self.call('/api/issues/44/review',lambda:api.submit_review(44),method='POST',
            data={'review_result':'整改通过'})
        self.assertEqual((status,body.get('status')),(200,'已闭环'))
        self.cur.execute("SELECT actor_user_id,actor_role,result FROM inspection_issue_flow_history WHERE issue_id=44 AND action_type='review_submitted'")
        self.assertEqual(dict(self.cur.fetchone()),dict(actor_user_id=17,actor_role='quality_safety',result='整改通过'))

    def test_audit_failure_rolls_back_department_review(self):
        self.role('quality_safety')
        review_tests.mark_quality_handoff(self.cur, 44)
        self.cur.execute("ALTER TABLE inspection_issue_flow_history ADD CHECK(issue_id<>44) NOT VALID")
        self.admin.commit()
        body,status=self.call('/api/issues/44/review',lambda:api.submit_review(44),method='POST',
            data={'review_result':'整改通过'})
        self.assertEqual(status,500,body)
        self.cur.execute('SELECT status,review_result FROM issues WHERE id=44')
        self.assertEqual(dict(self.cur.fetchone()),dict(status='待复核',review_result=None))

    def test_concurrent_department_reviews_only_write_one_result_and_event(self):
        self.role('quality_safety')
        review_tests.mark_quality_handoff(self.cur, 44)
        self.admin.commit()
        def submit(_):
            return self.call('/api/issues/44/review',lambda:api.submit_review(44),method='POST',
                             data={'review_result':'整改通过'})[1]
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses=list(pool.map(submit,range(2)))
        self.assertEqual(sorted(statuses),[200,403])
        self.cur.execute("SELECT count(*) AS n FROM inspection_issue_flow_history WHERE issue_id=44 AND action_type='review_submitted'")
        self.assertEqual(self.cur.fetchone()['n'],1)
