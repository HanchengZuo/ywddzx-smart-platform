import importlib.util
import os
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from flask import Flask
import app as api
import highlights as hl


class HighlightTests(unittest.TestCase):
    def test_shared_visibility_predicate_and_parameterized_filters(self):
        core = MagicMock()
        core.build_issue_list_visibility_scope.return_value = (['i.station_id=%s'], [3])
        core.should_hide_inspector_contact_info.return_value = False
        where, params = hl.filters(core, None, {'id':9}, {'id':'hl10','description':"' OR 1=1",'date_from':'2026-09-01','date_to':'2026-09-09'})
        self.assertIn('i.station_id=%s', where)
        self.assertIn('HL10', params)
        self.assertNotIn("' OR 1=1", where)
        with self.assertRaises(ValueError): hl.filters(core,None,{}, {'date_from':'2026-10-01','date_to':'2026-09-01'})

    def test_audit_requires_permission_and_both_scopes(self):
        core = MagicMock()
        row = {'station_id':1,'inspection_table_id':2,'region':'浦东'}
        for failing in ('can_audit_inspection_issues','is_inspection_table_allowed_for_user','is_station_region_allowed_for_user'):
            getattr(core,failing).return_value = False
            self.assertFalse(hl.can_audit(core,None,{'id':1},row))
            getattr(core,failing).return_value = True
        self.assertTrue(hl.can_audit(core,None,{'id':1},row))

    def test_unauthenticated_api_is_rejected(self):
        with api.app.test_client() as client:
            self.assertEqual(client.get('/api/highlights').status_code,401)


@unittest.skipUnless(os.getenv('ISSUE_LIFECYCLE_DB_TEST') == '1','local database opt-in')
class HighlightDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.conn = api.get_db_connection(); self.cur = self.conn.cursor()
        self.cur.execute('''CREATE TEMP TABLE users(id INTEGER PRIMARY KEY, real_name TEXT, phone TEXT);
          CREATE TEMP TABLE stations(id INTEGER PRIMARY KEY, region TEXT, station_name TEXT, station_manager_name TEXT, station_manager_phone TEXT);
          CREATE TEMP TABLE inspection_tables(id INTEGER PRIMARY KEY, table_name TEXT);
          SET LOCAL search_path TO pg_temp;
          INSERT INTO users VALUES(1,'管理员','100'),(2,'检查人','200'),(3,'站长','300');
          INSERT INTO stations VALUES(1,'浦东','甲站','站长','300'),(2,'松金','乙站','乙站长','400');
          INSERT INTO inspection_tables VALUES(1,'现场'),(2,'视频');''')
        spec = importlib.util.spec_from_file_location('hl_migration',Path(__file__).parents[1]/'migrations/versions/20260909_001_highlights.py')
        migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
        with patch.object(migration.op,'execute',side_effect=self.cur.execute):
            migration.upgrade(); migration.upgrade()
        self.user = {'id':1,'username':'root','role':'root','real_name':'管理员'}
        namespace = dict(vars(api))
        namespace.update(get_current_request_user=lambda:self.user,
            get_db_connection=lambda:SimpleNamespace(cursor=self.conn.cursor,commit=lambda:None,rollback=lambda:None),
            close_db_resources=lambda *args:None, save_uploaded_file=lambda *args:'/issues/test.jpg',
            remove_storage_file=lambda *args:None)
        self.app = Flask('highlight_tests'); hl.register_highlights(self.app,namespace)
        self.client = self.app.test_client()
        def permissions(cur,user):
            if user['role']=='root': return {key:True for key in api.PERMISSION_KEYS}
            return {'view_own_inspection_issues':True}
        self.patch = patch('app.get_effective_permissions',side_effect=permissions); self.patch.start()

    def tearDown(self):
        self.patch.stop(); self.conn.rollback(); self.conn.close()

    def create(self, station=1, table=1):
        return self.client.post('/api/highlights',data={'station_id':str(station),'inspection_table_id':str(table),'inspector_id':'3',
            'description':'值得推广的做法','photo':(BytesIO(b'photo'),'photo.jpg')})

    def test_independent_ids_and_audit_cycle(self):
        self.assertEqual(self.create().get_json()['id'],'HL1')
        self.cur.execute('SELECT inspector_id,audit_status FROM inspection_highlights WHERE id=1')
        row=self.cur.fetchone();self.assertEqual(row['inspector_id'],1);self.assertEqual(row['audit_status'],'pending')
        response=self.client.post('/api/highlights/1/audit',json={'action':'approve','expected_status':'pending','user_id':3})
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.client.post('/api/highlights/1/audit',json={'action':'reject','expected_status':'pending'}).status_code,409)
        self.assertEqual(self.client.post('/api/highlights/1/audit',json={'action':'reset','expected_status':'approved'}).status_code,200)
        self.assertEqual(self.client.post('/api/highlights/1/audit',json={'action':'reject','expected_status':'pending'}).status_code,200)
        self.cur.execute('SELECT actor_id FROM inspection_highlight_audits')
        self.assertEqual([r['actor_id'] for r in self.cur.fetchall()],[1,1,1])
        self.cur.execute("SELECT count(*) AS n FROM information_schema.columns WHERE table_name='inspection_highlights' AND column_name IN ('inspection_id','standard_id','rectification_result')")
        self.assertEqual(self.cur.fetchone()['n'],0)

    def test_pagination_filters_and_station_scope(self):
        for _ in range(7): self.assertEqual(self.create().status_code,200)
        self.create(2)
        data=self.client.get('/api/highlights?page=2&page_size=5').get_json()
        self.assertEqual(data['total'],8);self.assertEqual(len(data['items']),3)
        self.assertEqual(self.client.get('/api/highlights?id=HL1').get_json()['total'],1)
        self.client.post('/api/highlights/1/audit',json={'action':'approve','expected_status':'pending'})
        self.client.post('/api/highlights/8/audit',json={'action':'approve','expected_status':'pending'})
        self.user={'id':3,'role':'station_manager','station_id':1}
        data=self.client.get('/api/highlights').get_json()
        self.assertEqual(data['total'],1); self.assertEqual(data['items'][0]['display_id'],'HL1')
        self.assertEqual(self.client.post('/api/highlights/8/audit',json={'action':'reject','expected_status':'approved'}).status_code,403)
        self.assertEqual(self.create().status_code,403)
        self.assertEqual(self.client.get('/api/highlights/filter-options').get_json()['stations'],['甲站'])

    def test_region_and_department_table_scope_and_contact_privacy(self):
        self.create(1,1); self.create(1,2); self.create(2,1)
        for identifier in (1,2,3):
            self.client.post(f'/api/highlights/{identifier}/audit',json={'action':'approve','expected_status':'pending'})
        self.user={'id':2,'role':'area_account'}
        with patch('app.get_effective_permissions',return_value={'limit_issue_station_region_scope':True,
                'limit_issue_inspection_table_scope':True,'audit_inspection_issues':True,'hide_inspector_contact_info':True}), \
             patch('app.get_effective_inspection_table_scope_ids',return_value={1}), \
             patch('app.get_effective_station_region_scope_values',return_value={'浦东'}):
            data=self.client.get('/api/highlights').get_json()
            self.assertEqual(data['total'],1)
            self.assertEqual(data['items'][0]['display_id'],'HL1')
            self.assertEqual(data['items'][0]['inspector'],'')
            self.assertNotIn('inspector_id',data['items'][0])
            for identifier in (2,3):
                self.assertEqual(self.client.post(f'/api/highlights/{identifier}/audit',json={'action':'reset','expected_status':'approved'}).status_code,403)
            self.assertEqual(self.client.get('/api/highlights/filter-options').get_json()['tables'],['现场'])
            with patch('app.get_effective_inspection_table_scope_ids',return_value=set()):
                self.assertEqual(self.client.get('/api/highlights').get_json()['total'],0)
        with patch('app.get_effective_permissions',return_value={}):
            self.assertEqual(self.client.get('/api/highlights').status_code,403)


if __name__=='__main__': unittest.main()
