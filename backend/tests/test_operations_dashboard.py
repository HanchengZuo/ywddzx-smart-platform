import importlib.util
import os
import unittest
import uuid
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from flask import Flask
import app as core_app
from operations_dashboard import PERMISSIONS, dashboard, details, issue_cte, parse_period, register_operations


class OperationsTest(unittest.TestCase):
    def test_period_defaults_and_bounds(self):
        self.assertEqual(parse_period({}, date(2026, 9, 23)), (date(2026, 9, 1), date(2026, 9, 23)))
        for args in [{'date_from':'bad'}, {'date_from':'2026-02-30'},
                     {'date_from':'2026-02-02','date_to':'2026-02-01'},
                     {'date_from':'2020-01-01','date_to':'2026-01-01'}]:
            with self.assertRaises(ValueError): parse_period(args)
        self.assertEqual(parse_period({'date_from':'2024-01-01','date_to':'2024-12-31'})[1],date(2024,12,31))

    def test_defaults_only_supervisor_and_root(self):
        self.assertEqual(PERMISSIONS, {'overview':'view_operations_overview'})
        for retired in ('view_operations_rectification','view_operations_insights'):
            self.assertNotIn(retired,core_app.PERMISSION_KEYS)
        for key in PERMISSIONS.values():
            for role in core_app.ROLE_OPTIONS:
                self.assertEqual(core_app.role_default_permission(role, key), role in ('root','supervisor'))

    def test_scoped_cte_uses_existing_business_visibility(self):
        core = SimpleNamespace(build_issue_list_visibility_scope=MagicMock(return_value=(['i.station_id=%s','i.inspection_table_id=%s'],[12,8])))
        cte, params = issue_cte(core, MagicMock(), {'id':5}, {'date_from':'2026-09-01','date_to':'2026-09-02','region':"x' OR TRUE --"})
        self.assertIn('i.station_id=%s AND i.inspection_table_id=%s', cte)
        self.assertNotIn("x' OR TRUE", cte)
        self.assertEqual(params[:2],[12,8])
        self.assertEqual(params[-1],"x' OR TRUE --")
        core.build_issue_list_visibility_scope.assert_called_once()

    def test_api_authentication_and_independent_authorization(self):
        response = core_app.app.test_client().get('/api/operations/overview')
        self.assertEqual(response.status_code,401)
        user={'id':17,'role':'station_manager'}
        core=dict(get_current_request_user=lambda:user, get_db_connection=MagicMock(),
                  has_permission=MagicMock(return_value=False), close_db_resources=MagicMock())
        app=Flask(__name__); register_operations(app,core)
        for mode,key in PERMISSIONS.items():
            for suffix in ['', '/issues']:
                response=app.test_client().get(f'/api/operations/{mode}{suffix}?user_id=1')
                self.assertEqual(response.status_code,403)
                self.assertEqual(core['has_permission'].call_args.args[1:],(user,key))
        self.assertEqual(app.test_client().get('/api/operations/unknown').status_code,404)
        for mode in ('rectification','insights'):
            self.assertEqual(app.test_client().get('/api/operations/'+mode).status_code,404)
            self.assertEqual(app.test_client().get('/api/operations/'+mode+'/issues').status_code,404)

    def test_api_errors_do_not_expose_internals(self):
        core=dict(get_current_request_user=lambda:{'id':1}, get_db_connection=MagicMock(),
                  has_permission=lambda *args:True, close_db_resources=MagicMock())
        app=Flask(__name__); register_operations(app,core)
        with patch('operations_dashboard.dashboard',side_effect=RuntimeError('SECRET SQL')):
            with self.assertLogs(level='ERROR'):
                response=app.test_client().get('/api/operations/overview')
        self.assertEqual(response.status_code,500)
        self.assertNotIn('SECRET SQL',response.get_data(as_text=True))


@unittest.skipUnless(os.getenv('OPERATIONS_DB_TEST') == '1', 'isolated database test opt-in')
class OperationsDatabaseTest(unittest.TestCase):
    def setUp(self):
        self.conn=core_app.get_db_connection(); self.cur=self.conn.cursor()
        self.schema='test_operations_'+uuid.uuid4().hex
        self.cur.execute(f'CREATE SCHEMA {self.schema}; SET LOCAL search_path TO {self.schema}')
        self.cur.execute('''
          CREATE TABLE stations(id int,station_name text,region text);
          CREATE TABLE inspection_tables(id int,table_name text,checklist_mode text);
          CREATE TABLE inspections(id int,station_id int,inspector_id int,inspection_table_id int,inspection_date date,
            sign_status text,station_manager_signed_at timestamp,station_manager_signature_path text,
            station_manager_signed_name text,quality_accept_source text);
          CREATE TABLE issues(id int,station_id int,inspection_id int,inspection_table_id int,inspector_id int,
            standard_id bigint,internal_standard_id text,standard_detail_text text,internal_standard_detail_text text,
            description text,created_at timestamp,audit_status text,status text);
          CREATE TABLE inspection_highlights(id int,station_id int,inspection_table_id int,inspector_id int,
            created_at timestamp,audit_status text);
          CREATE TABLE role_permissions(role text,permission_key text,is_allowed bool,PRIMARY KEY(role,permission_key));
          INSERT INTO stations VALUES(1,'甲站','浦东'),(2,'乙站','宝静'),(3,'零问题站','浦东'),(4,'仅零问题片区','嘉青');
          INSERT INTO inspection_tables VALUES(1,'计量','offline'),(2,'非油','online');
          INSERT INTO inspections(id,station_id,inspector_id,inspection_table_id,inspection_date,sign_status) VALUES
            (1,1,10,1,'2020-01-15','已签名确认'),(2,1,10,1,'2020-01-15','待签名确认'),
            (3,2,11,1,'2020-01-15','已签名确认'),(4,3,10,1,'2020-01-15','已签名确认'),
            (5,1,10,2,'2020-01-15','已签名确认'),(6,4,10,1,'2020-01-15','已签名确认');
          INSERT INTO inspection_highlights VALUES(1,1,1,10,'2020-01-15','approved'),(2,1,1,10,'2020-01-15','pending');
        ''')
        for id,ins,station,table,audit,status in [
            (1,1,1,1,'approved','已闭环'),(2,1,1,1,'approved','待复核'),(3,1,1,1,'approved','站级无法整改'),
            (4,1,1,1,'pending','待整改'),(5,1,1,1,'rejected','待整改'),(6,1,1,1,'approved','已销毁'),
            (7,1,1,1,'approved','申诉中'),(8,2,1,1,'approved','待整改'),(9,1,1,1,'approved','待整改'),
            (10,3,2,1,'approved','已闭环'),(11,5,1,2,'approved','已整改')]:
            self.cur.execute('''INSERT INTO issues(id,inspection_id,station_id,inspection_table_id,inspector_id,
              audit_status,status,created_at,standard_id,standard_detail_text,description)
              VALUES(%s,%s,%s,%s,10,%s,%s,'2020-01-15',9000,'规范内容','问题描述')''',
              (id,ins,station,table,audit,status))
        self.core=SimpleNamespace(
            build_issue_list_visibility_scope=lambda *args:([],[]),
            can_view_all_inspection_records=lambda *args:True,
            can_view_region_inspection_records=lambda *args:False,
            append_inspection_table_scope_filter=lambda *args:True,
            append_station_region_scope_filter=lambda *args:True,
            append_pending_audit_inspection_visibility_filter=lambda *args:None,
        )
        self.source={'date_from':'2020-01-01','date_to':'2020-01-31'}
        self.user={'id':1,'role':'supervisor'}

    def tearDown(self):
        self.conn.rollback(); self.cur.close(); self.conn.close()

    def test_all_dashboards_statistics_and_zero_problem_inspections(self):
        overview=dashboard(self.core,self.cur,self.user,'overview',self.source)
        self.assertEqual(overview['summary'],dict(total=11,valid=8,stations=2,pending_audit=1,closed=3,unable=1,destroyed=2,open=4,aged=4))
        self.assertEqual(overview['records']['stations'],4)
        self.assertEqual(overview['records']['records'],6)
        self.assertIn('嘉青',overview['regions'])
        self.assertEqual(overview['highlights'],1)
        self.assertEqual(overview['trend'][0]['valid'],8)
        rectification=overview
        self.assertEqual(rectification['ages'][0]['count'],4)
        self.assertEqual(rectification['stations'][0]['count'],4)
        insight=overview
        self.assertEqual(len(insight['tables']),2)
        self.assertEqual(insight['standards'][0]['count'],8)
        self.assertEqual(insight['standards'][0]['stations'],2)

    def test_scope_filters_apply_to_summary_and_every_drilldown(self):
        self.core.build_issue_list_visibility_scope=lambda *args:(['i.station_id=%s','i.inspection_table_id=%s'],[1,1])
        for mode in PERMISSIONS:
            result=dashboard(self.core,self.cur,self.user,mode,self.source)
            self.assertEqual(result['summary']['valid'],6)
            self.assertEqual([r['region'] for r in result['units']],['浦东'])
        rows=details(self.core,self.cur,self.user,self.source)
        self.assertEqual(rows['total'],9)
        self.assertTrue(all(r['station_name']=='甲站' and r['table_name']=='计量' for r in rows['rows']))
        self.assertEqual(details(self.core,self.cur,self.user,dict(self.source,station_id=2))['total'],0)
        self.assertEqual(details(self.core,self.cur,self.user,dict(self.source,region='宝静'))['total'],0)
        self.assertEqual(details(self.core,self.cur,self.user,dict(self.source,phase='待验收'))['total'],1)

    def test_empty_bounds_and_pagination(self):
        self.cur.execute('''INSERT INTO issues SELECT 100+n,1,1,1,10,9000,NULL,'规范',NULL,'分页','2020-01-31 23:59:59','approved','待整改'
          FROM generate_series(1,25) n;
          INSERT INTO issues(id,station_id,inspection_id,inspection_table_id,created_at,audit_status,status)
          VALUES(999,1,1,1,'2020-02-01','approved','待整改')''')
        first=details(self.core,self.cur,self.user,self.source)
        second=details(self.core,self.cur,self.user,dict(self.source,page=2))
        self.assertEqual(first['total'],36)
        self.assertEqual(len(first['rows']),20)
        self.assertEqual(len(second['rows']),16)
        self.assertFalse({r['id'] for r in first['rows']} & {r['id'] for r in second['rows']})
        for mode in PERMISSIONS:
            result=dashboard(self.core,self.cur,self.user,mode,dict(date_from='2019-01-01',date_to='2019-01-01'))
            self.assertEqual(result['summary']['total'],0)
            self.assertEqual(result['phases'],[])

    def test_record_scope_and_missing_record_permission_do_not_leak_counts(self):
        self.core.can_view_all_inspection_records=lambda *args:False
        self.core.can_view_own_inspection_records=lambda *args:False
        result=dashboard(self.core,self.cur,self.user,'overview',self.source)
        self.assertIsNone(result['records'])
        self.assertNotIn('嘉青',result['regions'])
        self.core.can_view_own_inspection_records=lambda *args:True
        result=dashboard(self.core,self.cur,dict(self.user,station_id=3),'overview',self.source)
        self.assertEqual(result['records']['stations'],1)
        self.assertEqual(result['records']['records'],1)
        self.core.append_inspection_table_scope_filter=lambda *args:False
        result=dashboard(self.core,self.cur,dict(self.user,station_id=3),'overview',self.source)
        self.assertEqual(result['records']['records'],0)

    def test_empty_issue_scope_also_hides_highlights_and_rejects_bad_drilldowns(self):
        self.core.build_issue_list_visibility_scope=lambda *args:(['FALSE'],[])
        result=dashboard(self.core,self.cur,self.user,'overview',self.source)
        self.assertEqual(result['highlights'],0)
        self.assertEqual(result['summary']['total'],0)
        for filters in [{'page':'bad'},{'page':100001},{'phase':'fake'},{'station_id':'x'}]:
            with self.assertRaises(ValueError): details(self.core,self.cur,self.user,dict(self.source,**filters))

    def test_migration_is_repeatable_and_respects_explicit_denials(self):
        path=Path(__file__).parents[1]/'migrations/versions/20260923_001_operations_permissions.py'
        spec=importlib.util.spec_from_file_location('operations_migration',path)
        migration=importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
        with patch.object(migration.op,'execute',side_effect=self.cur.execute):
            migration.upgrade(); migration.upgrade()
            self.cur.execute('SELECT COUNT(*) AS count FROM role_permissions')
            self.assertEqual(self.cur.fetchone()['count'],3)
            self.cur.execute("UPDATE role_permissions SET is_allowed=FALSE WHERE permission_key='view_operations_insights'")
            migration.upgrade()
            self.cur.execute("SELECT is_allowed FROM role_permissions WHERE permission_key='view_operations_insights'")
            self.assertFalse(self.cur.fetchone()['is_allowed'])
