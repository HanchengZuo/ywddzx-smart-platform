"""v11 global switches and monthly scoring; disposable schemas only, no AI or real files."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import date
import os
import unittest
import uuid
from unittest.mock import patch

import psycopg2
from psycopg2.extras import RealDictCursor
import app as api


class ScoreMonthTests(unittest.TestCase):
    def test_previous_month_uses_beijing_date_and_preserves_attendance_default(self):
        for day, month in ((date(2026,10,24),'2026-09'),(date(2026,1,1),'2025-12'),(date(2024,3,1),'2024-02')):
            with patch.object(api,'beijing_today',return_value=day):
                self.assertEqual(api.parse_station_score_month()[0],month)
                self.assertEqual(api.parse_reporting_date_range()[0],day.strftime('%Y-%m'))
        self.assertEqual(api.parse_station_score_month('2024-02'),('2024-02',date(2024,2,1),date(2024,3,1)))

    def test_legacy_full_month_is_compatible_but_days_ranges_and_conflicting_month_are_rejected(self):
        self.assertEqual(api.parse_station_score_month(None,'2026-09-01','2026-09-30')[0],'2026-09')
        for values in (('2026-9',None,None),('2026-13',None,None),('9999-12',None,None),
                       (None,'2026-09-02','2026-09-30'),(None,'2026-09-01','2026-10-31'),
                       ('2026-10','2026-09-01','2026-09-30')):
            with self.assertRaises(ValueError):api.parse_station_score_month(*values)

    def test_visibility_permission_defaults_are_independent_not_manage_users(self):
        self.assertIn('manage_page_visibility',api.PERMISSION_KEYS)
        for role in api.ROLE_OPTIONS:
            self.assertEqual(api.role_default_permission(role,'manage_page_visibility'),role=='root')
        for value in ('false',None,1):
            with self.assertRaises(ValueError):api.normalize_page_visibility_items([dict(page_key='/inspection/issues',is_visible=value)])


@unittest.skipUnless(os.environ.get('INSPECTION_SCHEDULE_DB_TEST')=='1','isolated database opt-in')
class VisibilityScoreDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.config=api.get_db_config()
        if not self.config['dbname'].startswith('test_schedule_'):raise RuntimeError('Refusing non-test database')
        self.schema='v110_'+uuid.uuid4().hex
        self.admin=psycopg2.connect(**self.config,cursor_factory=RealDictCursor)
        self.cur=self.admin.cursor()
        self.cur.execute(f'CREATE SCHEMA {self.schema};SET search_path TO {self.schema}')
        self.cur.execute('''CREATE TABLE users(id int PRIMARY KEY,username text,real_name text,role text);
          INSERT INTO users VALUES(1,'root','管理员','root'),(2,'area','片区','area_account'),(3,'staff','检查员','supervisor');
          CREATE TABLE stations(id int PRIMARY KEY,station_name text,region text,hos_station_code text);
          INSERT INTO stations VALUES(1,'测试站','测试片区','S1');
          CREATE TABLE inspection_tables(id int PRIMARY KEY,table_code text,table_name text,checklist_mode text,
            standard_id_base int,description text,is_active boolean);
          INSERT INTO inspection_tables VALUES(1,'qa','可评分表','offline',9000,'',TRUE),(2,'none','无评分字段','online',10000,'',TRUE),
            (3,'disabled','停用表','offline',11000,'',FALSE);
          CREATE TABLE inspection_table_fields(inspection_table_id int,field_key text,field_label text,is_scorable boolean);
          INSERT INTO inspection_table_fields VALUES(1,'detail','检查内容',TRUE),(2,'detail','检查内容',FALSE),(3,'detail','检查内容',TRUE);
          CREATE TABLE inspections(id int PRIMARY KEY,inspection_date date,inspector_id int);
          INSERT INTO inspections VALUES(1,'2026-09-01',3),(2,'2026-09-30',3),(3,'2026-10-01',3),(4,'2026-08-31',3);
          CREATE TABLE issues(id int PRIMARY KEY,station_id int,inspection_id int,inspection_table_id int,standard_id bigint,
            internal_standard_id int,internal_standard_detail_text text,description text,photo_path text,status text,audit_status text,
            inspector_id int,created_at timestamp DEFAULT CURRENT_TIMESTAMP);
          INSERT INTO issues(id,station_id,inspection_id,inspection_table_id,standard_id,description,status,audit_status) VALUES
            (1,1,1,1,9001,'通过问题','待整改','approved'),(2,1,2,1,9001,'同规范再次通过','待整改','approved'),
            (3,1,1,1,9002,'未审核','待整改','pending'),(4,1,1,1,9002,'否决','已销毁','rejected'),
            (5,1,3,1,9002,'下月通过','待整改','approved'),(6,1,4,1,9002,'上月通过','待整改','approved');
          CREATE TABLE system_page_visibility(page_key text PRIMARY KEY,is_visible boolean,updated_by int,created_at timestamptz,updated_at timestamptz);
          CREATE TABLE security_audit_logs(actor_user_id int,actor_username text,actor_role text,target_user_id int,
            target_username text,action_type text,action_result text,failure_reason text,request_ip text,user_agent text,
            affected_count int,details jsonb,created_at timestamptz);
          CREATE TABLE station_score_adjustments(id serial PRIMARY KEY,station_id int,inspection_table_id int,standard_id bigint,
            score_month text,manual_score numeric,note text,adjusted_by int,adjusted_at timestamp DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(station_id,inspection_table_id,standard_id,score_month));''')
        api.ensure_station_score_export_schema(self.cur)
        self.admin.commit()
        self.actor=dict(id=2,username='area',real_name='片区',role='area_account')
        self.permissions={'manage_page_visibility','view_station_scores','adjust_station_scores'}
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(api,'get_db_connection',side_effect=self.connect))
        self.stack.enter_context(patch.object(api,'verify_auth_token',side_effect=lambda *_:(self.actor,{})))
        self.stack.enter_context(patch.object(api,'get_user_by_id',side_effect=lambda *_:self.actor))
        self.stack.enter_context(patch.object(api,'has_permission',side_effect=lambda cur,user,key:key in self.permissions))
        self.stack.enter_context(patch.object(api,'beijing_today',return_value=date(2026,10,24)))
        for name in ('ensure_user_security_schema','ensure_system_page_visibility_schema','ensure_inspection_checklist_management_schema',
                     'ensure_issue_inspector_schema','ensure_station_score_schema','ensure_station_score_export_schema',
                     'cleanup_expired_station_score_exports','touch_online_user_presence','start_backup_scheduler_once'):
            self.stack.enter_context(patch.object(api,name))
        self.client=api.app.test_client()
        self.headers={'Authorization':'Bearer isolated-test'}

    def connect(self):
        return psycopg2.connect(**self.config,cursor_factory=RealDictCursor,options=f'-c search_path={self.schema} -c timezone=Asia/Shanghai')

    def tearDown(self):
        self.admin.rollback();self.cur.execute(f'DROP SCHEMA {self.schema} CASCADE');self.admin.commit();self.cur.close();self.admin.close()

    def change(self,key='/inspection/issues',value=False,**extra):
        return self.client.put('/api/management/page-visibility',json=dict(pages=[dict(page_key=key,is_visible=value)],**extra),headers=self.headers)

    def test_delegated_permission_saves_global_partial_patch_and_actor_and_all_users_read_same_settings(self):
        self.assertEqual(self.change().status_code,200)
        self.assertEqual(self.change('/inspection/records',False).status_code,200)
        self.actor=dict(id=3,role='supervisor',username='staff')
        response=self.client.get('/api/page-visibility',headers=self.headers)
        self.assertEqual(response.json['settings'],{'/inspection/issues':False,'/inspection/records':False})
        self.cur.execute('SELECT DISTINCT updated_by FROM system_page_visibility');self.assertEqual(self.cur.fetchone()['updated_by'],2)
        self.cur.execute('SELECT COUNT(*) AS n FROM security_audit_logs');self.assertEqual(self.cur.fetchone()['n'],2)

    def test_no_permission_and_forged_identity_are_denied_without_updates(self):
        self.permissions={'manage_users'}
        self.assertEqual(self.change().status_code,403)
        self.assertEqual(self.client.get('/api/management/page-visibility',headers=self.headers).status_code,403)
        self.permissions.add('manage_page_visibility')
        self.assertEqual(self.change(user_id=1).status_code,403)
        self.assertEqual(self.client.put('/api/management/page-visibility',json={'pages':[]}).status_code,401)
        self.cur.execute('SELECT COUNT(*) AS n FROM system_page_visibility');self.assertEqual(self.cur.fetchone()['n'],0)

    def test_audit_failure_rolls_back_page_change_and_concurrent_different_pages_do_not_clobber(self):
        with patch.object(api,'record_security_event',side_effect=RuntimeError('audit failed')):
            self.assertEqual(self.change().status_code,500)
        self.cur.execute('SELECT COUNT(*) AS n FROM system_page_visibility');self.assertEqual(self.cur.fetchone()['n'],0)
        def submit(key):
            return api.app.test_client().put('/api/management/page-visibility',json={'pages':[{'page_key':key,'is_visible':False}]},headers=self.headers).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(submit,['/inspection/issues','/inspection/records'])),[200,200])
        self.cur.execute('SELECT COUNT(*) AS n FROM system_page_visibility WHERE is_visible=FALSE');self.assertEqual(self.cur.fetchone()['n'],2)

    def test_only_active_scorable_tables_and_approved_issues_inside_natural_month_are_used(self):
        self.assertEqual([r['id'] for r in api.fetch_scorable_checklist_rows(self.cur)],[1])
        mapped=api.fetch_station_score_issue_map(self.cur,1,date(2026,9,1),date(2026,10,1),[1])
        self.assertEqual(set(mapped),{(1,9001)})
        self.assertEqual(len(mapped[(1,9001)]),1)
        self.assertIn(mapped[(1,9001)][0]['id'],(1,2))
        response=self.client.get('/api/assessment/station-scores/scorable-checklists',headers=self.headers)
        self.assertEqual([r['id'] for r in response.json['checklists']],[1])
        denied=self.client.get('/api/assessment/station-scores?station_id=1&month=2026-09&inspection_table_id=2',headers=self.headers)
        self.assertEqual(denied.status_code,400)

    def test_score_payload_and_manual_adjustment_keep_the_same_month_and_full_month_legacy_key(self):
        fields=[dict(field_key='detail',field_label='检查内容',is_scorable=True)]
        with patch.object(api,'get_management_checklist_fields',return_value=fields), \
             patch.object(api,'get_physical_table_name_by_code',return_value='qa_standards'), \
             patch.object(api,'ensure_checklist_field_columns'), \
             patch.object(api,'fetch_checklist_standard_rows',return_value=[dict(standard_id=9001,detail='接地'),dict(standard_id=9002,detail='其他')]):
            response=self.client.get('/api/assessment/station-scores?station_id=1&inspection_table_id=1',headers=self.headers)
            self.assertEqual(response.status_code,200,response.json)
            self.assertEqual(response.json['month'],'2026-09')
            self.assertEqual((response.json['summary']['final_score'],response.json['summary']['deducted_item_count']),(50,1))
            self.assertFalse(response.json['tables'][0]['standards'][1]['issues'])
        self.cur.execute("INSERT INTO station_score_adjustments(station_id,inspection_table_id,standard_id,score_month,manual_score,adjusted_by) VALUES(1,1,9001,'2026-09',25,2)")
        self.admin.commit()
        self.assertEqual(api.fetch_station_score_adjustment_map(self.cur,1,'2026-09')[(1,9001)]['manual_score'],25)
        invalid=self.client.get('/api/assessment/station-scores?station_id=1&date_from=2026-09-02&date_to=2026-09-30',headers=self.headers)
        self.assertEqual(invalid.status_code,400)
        denied_export=self.client.post('/api/assessment/station-scores/export-tasks',json=dict(mode='single',station_id=1,inspection_table_id=2,month='2026-09'),headers=self.headers)
        self.assertEqual(denied_export.status_code,404)

    def test_manual_month_snapshot_permissions_and_rollback(self):
        context=dict(month='2026-09',max_score=50)
        payload=dict(station_id=1,inspection_table_id=1,standard_id=9001,month='2026-09',manual_score=25)
        with patch.object(api,'fetch_station_score_standard_context',return_value=context) as lookup:
            response=self.client.put('/api/assessment/station-scores/adjustment',json=payload,headers=self.headers)
            self.assertEqual(response.status_code,200,response.json)
            self.assertEqual(lookup.call_args.args[2],'2026-09')
            self.cur.execute("SELECT score_month,manual_score,adjusted_by FROM station_score_adjustments")
            self.assertEqual(dict(self.cur.fetchone()),dict(score_month='2026-09',manual_score=25,adjusted_by=2))
            self.cur.execute('ALTER TABLE station_score_adjustments ADD CHECK(manual_score<30) NOT VALID');self.admin.commit()
            self.assertEqual(self.client.put('/api/assessment/station-scores/adjustment',json=dict(payload,manual_score=40),headers=self.headers).status_code,500)
            self.cur.execute('SELECT manual_score FROM station_score_adjustments');self.assertEqual(self.cur.fetchone()['manual_score'],25)
            self.permissions.discard('adjust_station_scores')
            self.assertEqual(self.client.put('/api/assessment/station-scores/adjustment',json=payload,headers=self.headers).status_code,403)

    def test_export_job_uses_the_same_month_without_generating_files(self):
        payload=dict(station={'id':1,'station_name':'测试站'},tables=[dict(id=1,table_name='可评分表',item_count=2)])
        with patch.object(api,'build_station_score_payload',return_value=payload),patch.object(api,'start_station_score_export_task') as start:
            response=self.client.post('/api/assessment/station-scores/export-tasks',json=dict(mode='single',station_id=1,inspection_table_id=1,month='2026-09'),headers=self.headers)
            self.assertEqual(response.status_code,200,response.json)
            self.assertEqual(start.call_args.args[3:6],('2026-09',date(2026,9,1),date(2026,10,1)))
            self.assertIn('2026-09',response.json['task']['download_filename'])
            self.cur.execute('SELECT status,created_by FROM station_score_export_tasks')
            self.assertEqual(dict(self.cur.fetchone()),dict(status='pending',created_by=2))
