"""Run only against a disposable full database clone; never a business database.

CHECKLIST_VERSION_DB_TEST=1 DB_NAME=checklist_v127_test python -m unittest tests.test_checklist_versions -v
"""
import os
import unittest
import uuid
from datetime import date
from unittest.mock import patch

import psycopg2
from flask import Flask, g
from psycopg2 import sql
from psycopg2.extras import Json

import app as api
import checklist_versions as editions
from checklist_version_migration import install
from external_standard_status import require_active_standards


class FilterTests(unittest.TestCase):
    def test_filter_keeps_table_and_version_together_and_uses_parameters(self):
        clauses, params = ['station_id=%s'], [7]
        editions.append_filter(clauses, params, ['表A · v2', "表B' OR true --", '表C · v1'])
        self.assertEqual(params, [7, '表A', 2, '表C', 1, ["表B' OR true --"]])
        self.assertNotIn('OR true --', clauses[-1])
        self.assertEqual(clauses[0], 'station_id=%s')


@unittest.skipUnless(os.getenv('CHECKLIST_VERSION_DB_TEST') == '1', 'requires an isolated full database clone')
class VersionDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.getenv('DB_NAME', '').endswith('_test'):
            raise RuntimeError('Refusing writes outside an explicitly named test database')
        with api.get_db_connection() as conn:
            with conn.cursor() as cur:
                install(cur)
                api.ensure_inspection_checklist_management_schema(cur)

    def setUp(self):
        self.conn = api.get_db_connection()
        self.cur = self.conn.cursor()
        self.code = 'test_v127_' + uuid.uuid4().hex[:12]
        self.cur.execute('''INSERT INTO inspection_tables(table_code,table_name,is_active)
            VALUES(%s,%s,TRUE) RETURNING id,active_version_id''', (self.code,self.code))
        self.table_id = self.cur.fetchone()['id']
        self.cur.execute('UPDATE inspection_tables SET standard_id_base=id*1000 WHERE id=%s RETURNING active_version_id', (self.table_id,))
        self.v1 = self.cur.fetchone()['active_version_id']
        self.fields = api.normalize_checklist_field_rows([{'field_key':'f_'+self.code,'field_label':'旧字段'}],self.code)
        self.physical = api.get_physical_table_name_by_code(self.code)
        api.ensure_checklist_field_columns(self.cur,self.physical,self.fields)
        api.upsert_checklist_fields(self.cur,self.table_id,self.fields)
        self.standard = self.table_id*1000
        self.cur.execute(sql.SQL('INSERT INTO {}(standard_id,{}) VALUES(%s,%s)').format(sql.Identifier(self.physical),sql.Identifier(self.fields[0]['field_key'])), (self.standard,'旧规范原文'))
        self.cur.execute('SELECT id FROM stations ORDER BY id LIMIT 1')
        self.station = self.cur.fetchone()['id']
        self.user = {'id':1,'role':'root','username':'root','real_name':'版本测试'}
        self.conn.commit()
        self.app = Flask('versions_test')
        @self.app.before_request
        def identity(): g.current_user = self.user
        paths = ('/api/management/checklists/<int:table_id>/versions',
            '/api/management/checklists/<int:table_id>/versions/<int:version_id>',
            '/api/management/checklists/<int:table_id>/versions/<int:version_id>/activate',
            '/api/checklist-versions/<int:version_id>/original')
        for rule in api.app.url_map.iter_rules():
            if rule.rule in paths:
                self.app.add_url_rule(rule.rule,rule.endpoint,api.app.view_functions[rule.endpoint],methods=rule.methods)
        # Existing routes are tested with actual handlers, not mocked DB results.
        for name, path, methods in (
            ('get_inspection_table_standards','/standards',['GET']),
            ('get_management_checklist_standards','/manage/<int:inspection_table_id>/standards',['GET']),
            ('create_management_checklist_standard','/manage/<int:inspection_table_id>/standards',['POST']),
            ('update_management_checklist_standard','/manage/<int:inspection_table_id>/standards/<standard_id>',['PUT']),
        ):
            self.app.add_url_rule(path,name,getattr(api,name),methods=methods)
        self.client = self.app.test_client()

    def tearDown(self):
        self.conn.rollback(); self.cur.close(); self.conn.close()

    def request_version(self, suffix='', method='get', **kwargs):
        return getattr(self.client,method)(f'/api/management/checklists/{self.table_id}/versions{suffix}',**kwargs)

    def make_v2(self):
        response = self.request_version(method='post',json={'version_name':'新版','fields':[{'field_label':'新字段'}]})
        self.assertEqual(response.status_code,200,response.json)
        v2 = response.json['version_id']
        response = self.client.post(f'/manage/{self.table_id}/standards',json={'user_id':1,'version_id':v2,'values':{editions.version(self.cur,self.table_id,v2)['fields'][0]['field_key']:'新规范'}})
        self.assertEqual(response.status_code,200,response.json)
        return v2,response.json['standard_id']

    def create_history(self):
        self.cur.execute('''INSERT INTO inspections(station_id,inspector_id,inspection_table_id,inspection_date)
            VALUES(%s,1,%s,%s) RETURNING id,checklist_version_id''',(self.station,self.table_id,date.today()))
        record = self.cur.fetchone()
        self.assertEqual(record['checklist_version_id'],self.v1)
        self.cur.execute('''INSERT INTO issues(inspection_id,station_id,inspection_table_id,standard_id,standard_detail_text,description,photo_path)
            VALUES(%s,%s,%s,%s,'旧字段：旧规范原文','测试问题','tests/never-read.png') RETURNING id''', (record['id'],self.station,self.table_id,self.standard))
        issue = self.cur.fetchone()['id']
        self.cur.execute('''INSERT INTO inspection_highlights(station_id,inspector_id,inspection_table_id,description,photo_path)
            VALUES(%s,1,%s,'测试亮点','tests/never-read.png') RETURNING checklist_version_id''',(self.station,self.table_id))
        self.assertEqual(self.cur.fetchone()['checklist_version_id'],self.v1)
        self.conn.commit()
        return record['id'],issue

    def test_draft_activation_registration_history_and_filters(self):
        record,issue = self.create_history()
        v2,standard2 = self.make_v2()
        # Draft standards are invisible and unusable for registration.
        with self.assertRaises(ValueError):require_active_standards(self.cur,[standard2])
        self.conn.rollback()
        response = self.request_version(f'/{v2}/activate',method='post',json={'expected_active_version_id':self.v1})
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual([r['standard_id'] for r in self.client.get('/standards',query_string={'table_id':self.table_id}).json],[standard2])
        old = self.client.get('/standards',query_string={'table_id':self.table_id,'version_id':self.v1,'include_inactive':1})
        self.assertEqual(old.json[0]['standard_id'],self.standard)
        self.assertFalse(old.json[0]['is_active'])
        self.cur.execute('SELECT checklist_version_id,standard_detail_text FROM issues WHERE id=%s',(issue,))
        self.assertEqual(dict(self.cur.fetchone()),{'checklist_version_id':self.v1,'standard_detail_text':'旧字段：旧规范原文'})
        self.assertIsNone(api.find_period_inspection(self.cur,self.station,self.table_id,date.today()))
        with self.assertRaises(ValueError):require_active_standards(self.cur,[self.standard])
        self.conn.rollback()
        self.cur.execute('''INSERT INTO inspections(station_id,inspector_id,inspection_table_id,inspection_date)
            VALUES(%s,1,%s,%s) RETURNING checklist_version_id''',(self.station,self.table_id,date.today()))
        self.assertEqual(self.cur.fetchone()['checklist_version_id'],v2)
        self.conn.rollback()
        clauses,params=[],[]
        editions.append_filter(clauses,params,[f'{self.code} · v1'])
        self.cur.execute('SELECT i.id FROM issues i JOIN inspection_tables t ON t.id=i.inspection_table_id WHERE '+' AND '.join(clauses),params)
        self.assertEqual([r['id'] for r in self.cur.fetchall()],[issue])
        with self.assertRaisesRegex(ValueError,'报告模板'):editions.report_guard(self.cur,[self.code])

    def test_permission_denial_and_empty_version_do_not_change_activation(self):
        self.user = {'id':999999,'role':'station_manager','username':'denied'}
        self.assertEqual(self.request_version(method='post',json={'version_name':'越权'}).status_code,403)
        self.user={'id':1,'role':'root'}
        v2=self.request_version(method='post',json={'version_name':'空草稿'}).json['version_id']
        response=self.request_version(f'/{v2}/activate',method='post',json={'expected_active_version_id':self.v1})
        self.assertEqual(response.status_code,400)
        self.assertEqual(editions.version(self.cur,self.table_id)['id'],self.v1)
        self.assertEqual(self.request_version(f'/{v2}/activate',method='post',json={'expected_active_version_id':-1}).status_code,409)

    def test_field_structure_protected_revision_and_failed_update_rolls_back(self):
        self.create_history()
        current=editions.version(self.cur,self.table_id)
        incoming=[dict(f,field_label='不应覆盖历史') for f in current['fields']]
        response=self.request_version(f'/{self.v1}',method='put',json={'revision':current['revision'],'fields':incoming})
        self.assertEqual(response.status_code,400,response.json)
        self.assertEqual(editions.version(self.cur,self.table_id)['fields'][0]['field_label'],'旧字段')
        self.assertEqual(self.request_version(f'/{self.v1}',method='put',json={'revision':-1,'fields':current['fields']}).status_code,409)
        # Standard edits also must not overwrite the issue's stored text.
        response=self.client.put(f'/manage/{self.table_id}/standards/{self.standard}',json={'user_id':1,'version_id':self.v1,'values':{self.fields[0]['field_key']:'新版文字'}})
        self.assertEqual(response.status_code,200,response.json)
        self.cur.execute('SELECT standard_detail_text FROM issues WHERE inspection_table_id=%s',(self.table_id,))
        self.assertEqual(self.cur.fetchone()['standard_detail_text'],'旧字段：旧规范原文')

    def test_global_id_reservation_and_wrong_version_rejection(self):
        v2,standard2=self.make_v2()
        response=self.client.put(f'/manage/{self.table_id}/standards/{self.standard}',json={'user_id':1,'version_id':v2,'values':{editions.version(self.cur,self.table_id,v2)['fields'][0]['field_key']:'错误'}})
        self.assertEqual(response.status_code,400,response.json)
        self.cur.execute(sql.SQL('DELETE FROM {} WHERE standard_id=%s').format(sql.Identifier(self.physical)),(standard2,))
        self.conn.commit()
        with self.assertRaises(psycopg2.IntegrityError):
            self.cur.execute(sql.SQL('INSERT INTO {}(standard_id,checklist_version_id) VALUES(%s,%s)').format(sql.Identifier(self.physical)),(standard2,self.v1))
        self.conn.rollback()
        self.assertGreater(api.get_next_checklist_standard_id(self.cur,{'id':self.table_id},self.physical),standard2)

    def test_registration_lock_serializes_activation_and_releases_on_rollback(self):
        editions.require_active(self.cur,self.table_id)
        other=api.get_db_connection()
        try:
            with other.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout='150ms'")
                with self.assertRaises(psycopg2.errors.LockNotAvailable):
                    cursor.execute('UPDATE inspection_tables SET active_version_id=active_version_id WHERE id=%s',(self.table_id,))
                other.rollback(); self.conn.rollback()
                cursor.execute("SET LOCAL lock_timeout='500ms'")
                cursor.execute('UPDATE inspection_tables SET active_version_id=active_version_id WHERE id=%s',(self.table_id,))
        finally:other.rollback();other.close()

    def test_cross_family_and_duplicate_structural_fields_are_rejected_atomically(self):
        v2,_=self.make_v2()
        selected=editions.version(self.cur,self.table_id,v2)
        response=self.request_version(f'/{v2}',method='put',json={'revision':selected['revision'],'fields':self.fields})
        self.assertEqual(response.status_code,400,response.json)
        self.assertEqual(editions.version(self.cur,self.table_id,v2)['revision'],selected['revision'])
        self.cur.execute('SELECT id FROM inspection_checklist_versions WHERE inspection_table_id<>%s LIMIT 1',(self.table_id,))
        foreign=self.cur.fetchone()['id']
        self.assertEqual(self.request_version(f'/{foreign}',method='put',json={'revision':1,'fields':self.fields}).status_code,400)

    def test_seed_is_idempotent_and_four_fields_are_complete(self):
        self.cur.execute("SELECT id FROM inspection_tables WHERE table_name='现场检查明细表（现场）'")
        family=self.cur.fetchone()['id']
        current=editions.version(self.cur,family)
        self.assertEqual([f['field_label'] for f in current['fields']],['项目','内容','检查评比标准','检查方式'])
        self.assertEqual(editions.standard_ids(self.cur,current['id']),set(range(11039,11053)))
        self.cur.execute("SELECT count(*) AS n FROM issues i JOIN inspection_checklist_versions v ON v.id=i.checklist_version_id WHERE i.standard_id BETWEEN 11039 AND 11052 AND v.version_number<>1")
        self.assertEqual(self.cur.fetchone()['n'],0)
        before=editions.versions(self.cur,family)
        install(self.cur)
        self.assertEqual([v['id'] for v in editions.versions(self.cur,family)],[v['id'] for v in before])
        self.conn.rollback()

    def test_real_routes_catalog_history_pdf_report_warning_and_exports(self):
        record,issue=self.create_history()
        # Authentication alone is substituted; actual scopes, SQL, serializers,
        # and route handlers execute against the isolated clone. No jobs run.
        with patch.object(api,'verify_auth_token',return_value=(self.user,{})), \
             patch.object(api,'start_backup_scheduler_once'), \
             patch.object(api,'touch_online_user_presence'):
            client=api.app.test_client()
            headers={'Authorization':'Bearer isolated-test'}
            for path,query in (
                ('/api/management/checklists',{'user_id':1}),
                ('/api/inspection-tables',{'user_id':1,'scope':'issues','include_inactive':1}),
                ('/api/issues',{'user_id':1,'paginated':1,'inspection_tables':'["'+self.code+' · v1"]'}),
                ('/api/inspections',{'user_id':1,'inspection_tables':'["'+self.code+' · v1"]'}),
                (f'/api/inspections/{record}/issues',{'user_id':1}),
                ('/api/highlights',{'table':'["'+self.code+' · v1"]'}),
                ('/api/inspection-table-originals',{'user_id':1}),
                ('/api/inspection-reports/types',{}),
            ):
                response=client.get(path,query_string=query,headers=headers)
                self.assertEqual(response.status_code,200,(path,response.json))
                if path=='/api/inspection-reports/types':
                    service=next(r for r in response.json['report_types'] if r['key']=='on_site_service')
                    self.assertIn('版本',service['version_warning'])
                if path=='/api/issues':
                    self.assertIn(' · v1',response.json['items'][0]['inspection_table_display_name'])
            response=client.post('/api/inspection-reports/generate',headers=headers,json={'report_type':'on_site_service','generation_options':{'date_from':'2026-10-01','date_to':'2026-10-31'}})
            self.assertEqual(response.status_code,400,response.json)
            self.cur.execute("SELECT v.id FROM inspection_checklist_versions v JOIN inspection_tables t ON t.id=v.inspection_table_id WHERE v.source_key='service-onsite-20260707'")
            pdf_version=self.cur.fetchone()['id']; self.conn.rollback()
            response=client.get(f'/api/checklist-versions/{pdf_version}/original',headers=headers)
            self.assertEqual(response.status_code,200)
            self.assertTrue(response.data.startswith(b'%PDF-'))
            response.close()
            self.assertEqual(client.get(f'/api/checklist-versions/{pdf_version}/original').status_code,401)
            self.assertEqual(client.get(f'/storage/checklist-versions/{pdf_version}/original').status_code,401)
            self.cur.execute('SELECT auth_version FROM users WHERE id=1')
            auth_version=self.cur.fetchone()['auth_version'];self.conn.rollback()
            cookie=api.get_file_access_serializer().dumps({'uid':1,'av':auth_version,'exp':api.current_epoch_seconds()+60,'scope':'storage:read'})
            client.set_cookie(api.FILE_ACCESS_COOKIE_NAME,cookie,path='/storage')
            response=client.get(f'/storage/checklist-versions/{pdf_version}/original')
            self.assertEqual(response.status_code,200,response.json)
            self.assertTrue(response.data.startswith(b'%PDF-'))
            self.assertEqual(response.headers['Cache-Control'],'private, no-store')
            response.close()
            # The read-only file cookie grants neither API edits nor upload.
            self.assertEqual(client.post(f'/api/checklist-versions/{pdf_version}/original').status_code,401)


if __name__ == '__main__':unittest.main()
