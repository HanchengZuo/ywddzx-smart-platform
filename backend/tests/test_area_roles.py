"""Regional specialists are restricted by both dimensions, including direct access."""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import psycopg2
from psycopg2.extras import RealDictCursor

import app as api
from area_roles import AREA_SHARED_MENU_PERMISSIONS, AREA_SPECIALIST_DEPARTMENTS, require_specialist_region, specialist_can_read_media
from certificates import scope as certificate_scope
from issue_appeals import appeal_scope, can_decide
from quality_deadlines import responsible_users


class AreaPolicyTests(unittest.TestCase):
    def test_existing_role_stays_compatible(self):
        self.assertEqual(api.ROLE_LABELS['area_account'], '片区经理')
        self.assertFalse(api.role_default_permission('area_account', 'limit_issue_inspection_table_scope'))
        self.assertTrue(api.role_default_permission('area_account', 'limit_issue_station_region_scope'))

    def test_specialists_require_one_region(self):
        key = 'limit_issue_station_region_scope'
        for role in AREA_SPECIALIST_DEPARTMENTS:
            self.assertEqual(api.normalize_user_role(role), role)
            for regions in ([], ['浦东', '松金']):
                with self.assertRaises(ValueError):
                    require_specialist_region(role, {key: regions})
            require_specialist_region(role, {key: ['浦东']})

    def test_authenticated_requests_cannot_bypass_scope_with_other_apis(self):
        user = {'id': 17, 'role': 'area_safety'}
        with patch.object(api, 'verify_auth_token', return_value=(user, {})), \
             patch.object(api, 'touch_online_user_presence'), patch.object(api, 'start_backup_scheduler_once'):
            client = api.app.test_client()
            headers = {'Authorization': 'Bearer fixture'}
            for path in ('/api/stations',
                         '/api/inspection-reports/status', '/api/my-review-issues'):
                self.assertEqual(client.get(path, headers=headers).status_code, 403)
            with patch.dict(api.app.view_functions, {'decide_issue_appeal': lambda appeal_id: ('handler reached', 200)}):
                self.assertEqual(client.post('/api/issue-appeals/5/decision', headers=headers).status_code, 200)
                for role in ('area_oil_gas', 'area_non_oil'):
                    user['role'] = role
                    self.assertEqual(client.post('/api/issue-appeals/5/decision', headers=headers).status_code, 403)

    def test_shared_menu_grants_follow_manager_template_not_specialist_overrides(self):
        for enable in (False, True):
            def overrides(_cur, role):
                return {key: (enable if role == 'area_account' else not enable)
                        for key in AREA_SHARED_MENU_PERMISSIONS}
            with patch.object(api, 'get_role_permission_overrides', side_effect=overrides), \
                 patch.object(api, 'get_permission_overrides', return_value={key: not enable for key in AREA_SHARED_MENU_PERMISSIONS}):
                for role in AREA_SPECIALIST_DEPARTMENTS:
                    permissions = api.get_effective_permissions(None, {'id': 17, 'role': role})
                    self.assertTrue(all(permissions[key] == enable for key in AREA_SHARED_MENU_PERMISSIONS))
                    self.assertTrue(permissions['limit_issue_inspection_table_scope'])
                    self.assertFalse(permissions['view_my_review_issues'])

    def test_certificate_default_scope_is_the_same_for_all_area_roles(self):
        for role in ('area_account', *AREA_SPECIALIST_DEPARTMENTS):
            for operation in ('view', 'register'):
                self.assertEqual(certificate_scope({'role': role}, {}, {'浦东'}, operation)[1:], ([['浦东']], 'region'))
                self.assertEqual(certificate_scope({'role': role}, {}, set(), operation)[2], 'none')

    def test_shared_page_endpoints_reach_their_own_permission_checks(self):
        endpoints = {
            ('GET','/api/station-map'): 'get_station_map',
            ('GET','/api/station-map/1/issues'): 'get_station_map_issues',
            ('GET','/api/event-feed'): 'get_event_feed',
            ('GET','/api/inspection-table-originals'): 'get_inspection_table_originals',
            ('GET','/api/checklist-versions/1/original'): 'version_original',
            ('GET','/api/operations/expert/meta'): 'expert_meta',
            ('POST','/api/operations/expert/questions'): 'expert_questions',
            ('GET','/api/station-certificates/options'): 'certificates.options',
            ('POST','/api/station-certificates'): 'certificates.register',
        }
        user = {'id': 17, 'role': 'area_safety'}
        with patch.object(api, 'verify_auth_token', return_value=(user, {})), \
             patch.object(api, 'touch_online_user_presence'), patch.object(api, 'start_backup_scheduler_once'):
            client = api.app.test_client()
            for (method, path), endpoint in endpoints.items():
                with self.subTest(path=path), patch.dict(api.app.view_functions, {endpoint: lambda **_: ('allowed handler', 200)}):
                    response = client.open(path, method=method, headers={'Authorization': 'Bearer fixture'})
                    self.assertEqual(response.get_data(as_text=True), 'allowed handler')

    def test_security_filter_accepts_family_and_exact_child(self):
        accounts = [{'role': role} for role in ('area_account', 'area_safety', 'area_non_oil', 'quality_safety')]
        self.assertEqual(api.filter_security_accounts(accounts, {'role': 'area_family'}), accounts[:3])
        self.assertEqual(api.filter_security_accounts(accounts, {'role': 'area_safety'}), accounts[1:2])


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST') == '1', 'isolated database opt-in')
class AreaScopeDatabaseTests(unittest.TestCase):
    def setUp(self):
        config = api.get_db_config()
        if not config['dbname'].startswith('test_schedule_'):
            raise RuntimeError('Refusing non-test database')
        self.conn = psycopg2.connect(**config, cursor_factory=RealDictCursor)
        self.addCleanup(self.conn.close)
        self.cur = self.conn.cursor()
        self.schema = 'area_roles_' + uuid4().hex
        self.cur.execute(f'CREATE SCHEMA {self.schema}; SET LOCAL search_path TO {self.schema}')
        self.cur.execute("""
            CREATE TABLE inspection_tables(id int, table_name text, checklist_mode text, is_active bool);
            INSERT INTO inspection_tables VALUES
                (1,'现场检查明细表（现场）','offline',true),
                (2,'非油检查表（现场）','offline',true),
                (3,'质量安全环保检查表（视频）','online',true),
                (4,'质量安全环保检查表（现场）','offline',false),
                (5,'财务检查表（现场）','offline',true);
            CREATE TABLE user_station_region_scopes(user_id int, scope_key text, station_region text);
            INSERT INTO user_station_region_scopes VALUES
                (17,'limit_issue_station_region_scope','浦东'),
                (17,'limit_record_station_region_scope','松金');
            CREATE TABLE stations(id int, region text);
            INSERT INTO stations VALUES(1,'浦东'),(2,'松金');
            CREATE TABLE inspections(id int, inspector_id int);
            INSERT INTO inspections VALUES(1,8);
            CREATE TABLE issues(id int, station_id int, inspection_id int, inspection_table_id int,
                inspector_id int, audit_status text, photo_path text,
                rectification_photo_path text, review_photo_path text, status text);
            INSERT INTO issues
                SELECT s.id*100+t.id,s.id,1,t.id,8,'approved','/issues/'||s.id||'-'||t.id||'.jpg',NULL,NULL,'待复核'
                FROM stations s CROSS JOIN inspection_tables t;
            INSERT INTO issues VALUES(999,1,1,3,8,'pending','issues/pending.jpg',NULL,NULL,'待审核');
            CREATE TABLE inspection_issue_flow_history(issue_id int, photo_path text);
            CREATE TABLE inspection_highlights(station_id int, inspection_table_id int, audit_status text, photo_path text);
            INSERT INTO inspection_highlights VALUES(1,3,'approved','issues/highlight.jpg');
        """)
        self.enterContext(patch.object(api, 'USER_SECURITY_SCHEMA_READY', True))
        overrides = {'view_all_inspection_issues': True, 'view_all_inspection_records': True,
                     'limit_issue_inspection_table_scope': False, 'limit_issue_station_region_scope': False,
                     'manage_users': True, 'submit_my_issue_reviews': True}
        self.enterContext(patch.object(api, 'get_role_permission_overrides', return_value=overrides))
        self.enterContext(patch.object(api, 'get_permission_overrides', return_value=overrides))

    def test_list_filters_and_direct_media_include_history_without_leaking(self):
        for role, expected in {'area_oil_gas': [101], 'area_non_oil': [102], 'area_safety': [103, 104]}.items():
            user = {'id': 17, 'role': role}
            with self.subTest(role=role):
                self.assertFalse(api.has_permission(self.cur, user, 'manage_users'))
                self.assertFalse(api.can_view_review_queue(self.cur, user))
                where, params = api.build_issue_list_visibility_scope(self.cur, user)
                self.cur.execute('SELECT i.id FROM issues i JOIN stations s ON s.id=i.station_id '
                                 'JOIN inspections ins ON ins.id=i.inspection_id WHERE '
                                 + ' AND '.join(where) + ' ORDER BY i.id', params)
                self.assertEqual([row['id'] for row in self.cur.fetchall()], expected)
                regions = api.get_effective_station_region_scope_values(self.cur, user, 'limit_record_station_region_scope')
                tables = api.get_effective_inspection_table_scope_ids(self.cur, user, 'limit_record_inspection_table_scope')
                self.assertEqual(regions, {'浦东'})
                self.assertTrue(specialist_can_read_media(self.cur, f'issues/1-{expected[0]-100}.jpg', regions, tables))
                self.assertFalse(specialist_can_read_media(self.cur, f'issues/2-{expected[0]-100}.jpg', regions, tables))
                self.assertFalse(specialist_can_read_media(self.cur, 'issues/1-5.jpg', regions, tables))
                self.assertFalse(specialist_can_read_media(self.cur, 'issues/pending.jpg', regions, tables))
                self.assertEqual(specialist_can_read_media(self.cur, 'issues/highlight.jpg', regions, tables), role == 'area_safety')

    def test_cockpit_sees_all_checklists_only_within_bound_region_and_map_photos_follow_map(self):
        user = {'id': 17, 'role': 'area_safety'}
        where, params = api.build_issue_list_visibility_scope(
            self.cur, user, include_pending_area=True, include_all_area_tables=True)
        self.cur.execute('SELECT i.id FROM issues i JOIN stations s ON s.id=i.station_id '
                         'JOIN inspections ins ON ins.id=i.inspection_id WHERE '
                         + ' AND '.join(where) + ' ORDER BY i.id', params)
        self.assertEqual([row['id'] for row in self.cur.fetchall()], [101, 102, 103, 104, 105, 999])
        self.assertFalse(specialist_can_read_media(self.cur, 'issues/2-5.jpg', {'浦东'}, {3, 4}))
        self.assertTrue(specialist_can_read_media(self.cur, 'issues/2-5.jpg', {'浦东'}, {3, 4}, map_statuses=('待复核',)))
        self.assertFalse(specialist_can_read_media(self.cur, 'issues/pending.jpg', {'浦东'}, {3, 4}, map_statuses=('待复核',)))

    def test_safety_first_review_requires_matching_region_and_table(self):
        core = SimpleNamespace(**vars(api))
        user = {'id': 17, 'role': 'area_safety'}
        where, params = appeal_scope(core, self.cur, user)
        self.assertEqual(len(where), 2)
        self.assertEqual(params[0], ['浦东'])
        self.assertEqual(set(params[1]), {3, 4})
        appeal = {'status': 'area_pending', 'region': '浦东', 'inspection_table_id': 3}
        self.assertTrue(can_decide(core, self.cur, user, appeal))
        self.assertTrue(can_decide(core, self.cur, user, dict(appeal, inspection_table_id=4)))
        self.assertFalse(can_decide(core, self.cur, user, dict(appeal, region='松金')))
        self.assertFalse(can_decide(core, self.cur, user, dict(appeal, inspection_table_id=5)))
        self.assertFalse(can_decide(core, self.cur, user, dict(appeal, status='quality_pending')))
        self.assertFalse(can_decide(core, self.cur, dict(user, role='area_oil_gas'), appeal))

    def test_deadline_responsibility_includes_only_eligible_first_reviewers(self):
        self.cur.execute("""
            CREATE TABLE users(id int, username text, real_name text, role text, station_id int, account_status text);
            INSERT INTO users VALUES
                (17,'safety','安全专员','area_safety',NULL,'active'),
                (18,'manager','片区经理','area_account',NULL,'active'),
                (19,'other_area','其他片区','area_safety',NULL,'active'),
                (20,'non_oil','非油专员','area_non_oil',NULL,'active'),
                (21,'suspended','停用安全专员','area_safety',NULL,'suspended');
            INSERT INTO user_station_region_scopes VALUES
                (18,'limit_issue_station_region_scope','浦东'),
                (19,'limit_issue_station_region_scope','松金'),
                (20,'limit_issue_station_region_scope','浦东'),
                (21,'limit_issue_station_region_scope','浦东');
        """)
        core = SimpleNamespace(**vars(api))
        with patch.object(api, 'get_role_station_region_scope_overrides', return_value=[]):
            users = responsible_users(self.cur, core, 'area_pending', 1, '浦东', 3)
            self.assertEqual([user['id'] for user in users], [17, 18])
            users = responsible_users(self.cur, core, 'area_pending', 1, '浦东', 5)
            self.assertEqual([user['id'] for user in users], [18])

    def test_missing_or_invalid_binding_fails_closed(self):
        user = {'id': 18, 'role': 'area_safety'}
        key = 'limit_issue_station_region_scope'
        self.assertEqual(api.get_effective_station_region_scope_values(self.cur, user, key), set())
        self.cur.execute("INSERT INTO user_station_region_scopes VALUES (17,%s,'松金')", (key,))
        self.assertEqual(api.get_effective_station_region_scope_values(self.cur, {'id': 17, 'role': 'area_safety'}, key), set())
