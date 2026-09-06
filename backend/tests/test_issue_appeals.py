import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from flask import Flask, g, request
import app as core
from issue_appeals import appeal_table_allowed, can_decide, register_issue_appeals, APPEAL_LABELS


class AppealRulesTests(unittest.TestCase):
    def test_only_root_can_grant_final_review_permission(self):
        with patch.object(core, 'get_user_by_id', return_value={'id': 2, 'role': 'supervisor'}), patch.object(core, 'has_permission', return_value=False):
            with self.assertRaises(PermissionError):
                core.apply_user_permission_updates(None, {'id': 3, 'role': 'quality_safety'}, {'review_quality_appeals': True}, 2)

    def test_five_checklists_only(self):
        for name, mode in core.QUALITY_SAFETY_DEFAULT_CHECKLIST_SCOPE:
            self.assertTrue(appeal_table_allowed(core, name, mode))
        self.assertFalse(appeal_table_allowed(core, '财务检查表', 'offline'))
        self.assertFalse(appeal_table_allowed(core, '环境无异味管理检查表', 'online'))
        self.assertTrue(appeal_table_allowed(core, '加油站质量安全环保检查表（视频）', 'online'))

    def test_permission_and_area_scope(self):
        fake = SimpleNamespace(
            normalize_station_region_value=core.normalize_station_region_value,
            get_effective_station_region_scope_values=lambda *args: {'浦东'},
            has_permission=lambda cur, user, key: user.get('allowed', False),
        )
        self.assertTrue(can_decide(fake, None, {'role': 'area_account'}, {'status': 'area_pending', 'region': '浦东'}))
        self.assertFalse(can_decide(fake, None, {'role': 'area_account'}, {'status': 'area_pending', 'region': '松金'}))
        for role in ('station_manager', 'supervisor', 'area_account'):
            self.assertFalse(can_decide(fake, None, {'role': role, 'allowed': True}, {'status': 'quality_pending'}))
        self.assertFalse(can_decide(fake, None, {'role': 'quality_safety'}, {'status': 'quality_pending'}))
        self.assertTrue(can_decide(fake, None, {'role': 'quality_safety', 'allowed': True}, {'status': 'quality_pending'}))
        catalog = next(p for p in core.PERMISSION_CATALOG if p['key'] == 'review_quality_appeals')
        self.assertFalse(catalog['defaults']['quality_safety'])
        for action, label in APPEAL_LABELS.items():
            self.assertEqual(core.serialize_issue_flow_history_event({'action_type': action})['action_label'], label)


@unittest.skipUnless(os.environ.get('ISSUE_LIFECYCLE_DB_TEST') == '1', 'Local PostgreSQL only; all data changes rolled back')
class AppealDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.conn = core.get_db_connection()
        self.cur = self.conn.cursor()
        self.addCleanup(self.cleanup_database)
        for name in ('20260905_001_issue_lifecycle', '20260905_002_review_branches', '20260905_003_issue_appeals', '20260906_001_appeal_notifications'):
            path = Path(__file__).parents[1] / f'migrations/versions/{name}.py'
            spec = importlib.util.spec_from_file_location(name, path)
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            migration.op = SimpleNamespace(execute=self.cur.execute)
            migration.upgrade()
        migration.upgrade()
        self.cur.execute('SELECT i.id,i.station_id,i.inspection_id,s.region FROM issues i JOIN stations s ON s.id=i.station_id WHERE NOT EXISTS (SELECT 1 FROM inspection_issue_appeal_claims c WHERE c.issue_id=i.id) ORDER BY i.id DESC LIMIT 1')
        self.issue = self.cur.fetchone()
        if not self.issue:
            self.skipTest('Needs one local issue')
        self.cur.execute('SELECT id FROM users ORDER BY id LIMIT 1')
        uid = self.cur.fetchone()['id']
        self.cur.execute('SELECT id,table_name,checklist_mode FROM inspection_tables')
        table = next(t for t in self.cur.fetchall() if appeal_table_allowed(core, t['table_name'], t['checklist_mode']))
        self.cur.execute("UPDATE inspections SET sign_status='已签名确认' WHERE id=%s", (self.issue['inspection_id'],))
        self.cur.execute("UPDATE issues SET status='待整改',audit_status='approved',inspection_table_id=%s WHERE id=%s", (table['id'], self.issue['id']))
        base = dict(id=uid, username='appeal-test', real_name='测试用户')
        self.users = {
            'station': dict(base, role='station_manager', station_id=self.issue['station_id']),
            'wrong_station': dict(base, role='station_manager', station_id=-1),
            'area': dict(base, role='area_account', regions={self.issue['region']}),
            'wrong_area': dict(base, role='area_account', regions={'不存在的测试片区'}),
            'quality': dict(base, role='quality_safety', allowed=True),
            'quality_readonly': dict(base, role='quality_safety', allowed=False),
        }
        test_app = Flask(__name__)

        @test_app.before_request
        def identify():
            g.current_user = self.users.get(request.headers.get('X-Test-Identity'))

        conn = self.conn

        class RequestTransaction:
            def __init__(self):
                with conn.cursor() as cur:
                    cur.execute('SAVEPOINT appeal_request')
                    cur.execute("SELECT set_config('app.actor_id',%s,true)", (str(uid),))

            def cursor(self):
                return conn.cursor()

            def commit(self):
                with conn.cursor() as cur:
                    cur.execute('RELEASE SAVEPOINT appeal_request')

            def rollback(self):
                with conn.cursor() as cur:
                    cur.execute('ROLLBACK TO SAVEPOINT appeal_request')
                    cur.execute('RELEASE SAVEPOINT appeal_request')

            def close(self):
                pass

        namespace = dict(vars(core))
        namespace.update(
            get_db_connection=RequestTransaction,
            get_effective_station_region_scope_values=lambda cur, user, *args: user.get('regions', set()),
            has_permission=lambda cur, user, key: user.get('allowed', False),
        )
        register_issue_appeals(test_app, namespace)
        self.client = test_app.test_client()

    def cleanup_database(self):
        self.conn.rollback()
        self.cur.close()
        self.conn.close()

    def post(self, path, identity='station', **data):
        return self.client.post(path, json=data, headers={'X-Test-Identity': identity})

    def start(self):
        response = self.post(f"/api/issues/{self.issue['id']}/appeals", reason='问题事实与检查结论不符')
        self.assertEqual(response.status_code, 200, response.json)
        return response.json['id']

    def state(self):
        self.cur.execute('SELECT status FROM issues WHERE id=%s', (self.issue['id'],))
        return self.cur.fetchone()['status']

    def decide(self, aid, identity, stage, decision='approve'):
        return self.post(f'/api/issue-appeals/{aid}/decision', identity, stage=stage, decision=decision, reason='根据问题事实和申诉依据作出判断')

    def test_submit_scope_and_duplicate(self):
        path = f"/api/issues/{self.issue['id']}/appeals"
        self.assertEqual(self.client.post(path, json={'reason': 'x'}).status_code, 401)
        self.assertEqual(self.post(path, 'wrong_station', reason='x').status_code, 403)
        self.assertEqual(self.post(path, reason=' ').status_code, 400)
        self.cur.execute("UPDATE issues SET audit_status='pending' WHERE id=%s", (self.issue['id'],))
        self.assertEqual(self.post(path, reason='x').status_code, 409)
        self.cur.execute("UPDATE issues SET audit_status='approved' WHERE id=%s", (self.issue['id'],))
        self.start()
        self.assertEqual(self.state(), '申诉中')
        self.assertEqual(self.post(path, reason='重复').status_code, 409)
        response = self.client.get('/api/issue-appeals', headers={'X-Test-Identity': 'wrong_station'})
        self.assertEqual(response.json['total'], 0)
        response = self.client.get('/api/issue-appeals', headers={'X-Test-Identity': 'wrong_area'})
        self.assertEqual(response.json['total'], 0)

    def test_both_approval_stages_and_denials(self):
        aid = self.start()
        self.assertEqual(self.decide(aid, 'wrong_area', 'area_pending').status_code, 403)
        self.assertEqual(self.decide(aid, 'quality', 'area_pending').status_code, 403)
        self.assertEqual(self.decide(aid, 'area', 'area_pending').status_code, 200)
        self.assertEqual(self.decide(aid, 'area', 'area_pending').status_code, 409)
        self.assertEqual(self.decide(aid, 'quality_readonly', 'quality_pending').status_code, 403)
        self.assertEqual(self.decide(aid, 'quality', 'quality_pending').status_code, 200)
        self.assertEqual(self.state(), '已销毁')
        self.cur.execute('SELECT audit_status FROM issues WHERE id=%s', (self.issue['id'],))
        self.assertEqual(self.cur.fetchone()['audit_status'], 'rejected')
        self.cur.execute("SELECT count(*) AS n FROM inspection_issue_flow_history WHERE issue_id=%s AND action_type LIKE 'appeal_%%'", (self.issue['id'],))
        self.assertEqual(self.cur.fetchone()['n'], 3)

    def test_area_rejection_restores_and_reappeal_is_forbidden(self):
        aid = self.start()
        self.assertEqual(self.decide(aid, 'area', 'area_pending', 'reject').status_code, 200)
        self.assertEqual(self.state(), '待整改')
        self.assertEqual(self.post(f"/api/issues/{self.issue['id']}/appeals", reason='再次申诉').status_code, 409)

    def test_quality_rejection_restores_and_reappeal_is_forbidden(self):
        aid = self.start()
        self.assertEqual(self.decide(aid, 'area', 'area_pending').status_code, 200)
        self.assertEqual(self.decide(aid, 'quality', 'quality_pending', 'reject').status_code, 200)
        self.assertEqual(self.state(), '待整改')
        self.assertEqual(self.post(f"/api/issues/{self.issue['id']}/appeals", reason='再次申诉').status_code, 409)

    def test_notifications_persist_until_end_then_read_per_user(self):
        def listing(identity):
            return self.client.get(f"/api/issue-appeals?archive=1&keyword={self.issue['id']}", headers={'X-Test-Identity': identity}).json
        before = listing('station')['counts']
        aid = self.start()
        data = listing('station')
        self.assertEqual(data['counts']['active'], before['active'] + 1)
        self.assertEqual(data['counts']['total'], before['total'] + 1)
        self.assertEqual(listing('wrong_station')['counts']['total'], 0)
        self.decide(aid, 'area', 'area_pending', 'reject')
        data = listing('station')
        self.assertEqual(data['counts']['active'], before['active'])
        self.assertEqual(listing('station')['counts']['unread_ended'], before['unread_ended'] + 1)
        version = next(i for i in data['items'] if i['id'] == aid)['notification_version']
        self.assertEqual(self.post(f'/api/issue-appeals/{aid}/read', 'wrong_station', version=version).status_code, 403)
        self.assertEqual(self.post(f'/api/issue-appeals/{aid}/read', version='stale').status_code, 409)
        self.assertEqual(self.post(f'/api/issue-appeals/{aid}/read', version=version).json['counts']['total'], before['total'])
        self.assertEqual(listing('station')['counts']['total'], before['total'])
        self.cur.execute('SELECT id FROM users WHERE id<>%s LIMIT 1', (self.users['quality']['id'],))
        self.users['quality']['id'] = self.cur.fetchone()['id']
        self.assertTrue(next(i for i in listing('quality')['items'] if i['id'] == aid)['unread'])

    def test_appeal_action_has_no_generic_duplicate_event(self):
        self.cur.execute('SELECT max(id) AS id FROM inspection_issue_flow_history')
        since = self.cur.fetchone()['id'] or 0
        aid = self.start()
        self.decide(aid, 'area', 'area_pending')
        self.decide(aid, 'quality', 'quality_pending')
        self.cur.execute('SELECT action_type FROM inspection_issue_flow_history WHERE issue_id=%s AND id>%s ORDER BY id', (self.issue['id'], since))
        self.assertEqual([r['action_type'] for r in self.cur.fetchall()], ['appeal_submitted', 'appeal_area_approved', 'appeal_quality_approved'])

    def test_reset_cancels_pending_appeal(self):
        aid = self.start()
        self.cur.execute("UPDATE issues SET audit_status='pending' WHERE id=%s", (self.issue['id'],))
        self.assertEqual(self.state(), '待整改')
        self.cur.execute('SELECT status FROM inspection_issue_appeals WHERE id=%s', (aid,))
        self.assertEqual(self.cur.fetchone()['status'], 'cancelled')
        self.assertEqual(self.decide(aid, 'area', 'area_pending').status_code, 409)
        self.cur.execute("UPDATE issues SET audit_status='approved' WHERE id=%s", (self.issue['id'],))
        self.assertEqual(self.post(f"/api/issues/{self.issue['id']}/appeals", reason='重置后再次申诉').status_code, 409)

    def test_rejection_is_one_business_event(self):
        aid = self.start()
        self.assertEqual(self.decide(aid, 'area', 'area_pending', 'reject').status_code, 200)
        self.cur.execute("SELECT action_type FROM inspection_issue_flow_history WHERE issue_id=%s AND from_status='申诉中' AND to_status='待整改' ORDER BY id", (self.issue['id'],))
        self.assertEqual([r['action_type'] for r in self.cur.fetchall()], ['appeal_area_rejected'])

    def test_deleted_appeal_does_not_restore_lifetime_eligibility(self):
        aid = self.start()
        self.decide(aid, 'area', 'area_pending', 'reject')
        self.cur.execute('DELETE FROM inspection_issue_appeals WHERE id=%s', (aid,))
        self.cur.execute('SAVEPOINT lifetime_check')
        with self.assertRaises(Exception) as raised:
            self.cur.execute("INSERT INTO inspection_issue_appeals(issue_id,status,reason) VALUES (%s,'area_pending','再次申请')", (self.issue['id'],))
        self.assertEqual(raised.exception.pgcode, '23505')
        self.cur.execute('ROLLBACK TO SAVEPOINT lifetime_check')
        self.cur.execute('RELEASE SAVEPOINT lifetime_check')

    def test_active_read_does_not_clear_badge(self):
        aid = self.start()
        before = self.client.get('/api/issue-appeals', headers={'X-Test-Identity': 'station'}).json
        item = next(i for i in before['items'] if i['id'] == aid)
        self.assertEqual(self.post(f'/api/issue-appeals/{aid}/read', version=item['notification_version']).status_code, 409)
        after = self.client.get('/api/issue-appeals', headers={'X-Test-Identity': 'station'}).json
        self.assertEqual(before['counts'], after['counts'])

    def test_database_prevents_two_active_appeals(self):
        self.start()
        self.cur.execute('SAVEPOINT duplicate_check')
        with self.assertRaises(Exception) as raised:
            self.cur.execute("INSERT INTO inspection_issue_appeals (issue_id,status,reason) VALUES (%s,'area_pending','重复')", (self.issue['id'],))
        self.assertEqual(raised.exception.pgcode, '23505')
        self.cur.execute('ROLLBACK TO SAVEPOINT duplicate_check')
        self.cur.execute('RELEASE SAVEPOINT duplicate_check')

    def test_unsigned_issue_and_required_decision_reason(self):
        self.cur.execute("UPDATE inspections SET sign_status='待签名确认' WHERE id=%s", (self.issue['inspection_id'],))
        response = self.post(f"/api/issues/{self.issue['id']}/appeals", reason='测试')
        self.assertEqual(response.status_code, 409)
        self.cur.execute("UPDATE inspections SET sign_status='已签名确认' WHERE id=%s", (self.issue['inspection_id'],))
        aid = self.start()
        response = self.post(f'/api/issue-appeals/{aid}/decision', 'area', stage='area_pending', decision='approve', reason=' ')
        self.assertEqual(response.status_code, 400)
