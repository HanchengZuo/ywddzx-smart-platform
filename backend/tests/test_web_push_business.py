"""Real PostgreSQL transactions/triggers/outbox; no provider or business-file access."""
import os
import importlib.util
from pathlib import Path
from zoneinfo import ZoneInfo
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch
from tests import test_web_push as fixtures
from web_push_business import notify_appeal, process_signature_changes, recipient_resolver
from web_push_worker import deliver_one
from tests import test_issue_appeals as appeal_fixtures


@unittest.skipUnless(os.environ.get('WEB_PUSH_TEST_DSN'),'requires isolated PostgreSQL test DSN')
class BusinessPushTests(unittest.TestCase):
    connect=classmethod(fixtures.PushDatabaseTests.connect.__func__)
    setUpClass=classmethod(fixtures.PushDatabaseTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.PushDatabaseTests.tearDownClass.__func__)
    call=fixtures.PushDatabaseTests.call
    register=fixtures.PushDatabaseTests.register

    def setUp(self):
        fixtures.PushDatabaseTests.setUp(self)
        with self.connect() as conn,conn.cursor() as cur:
            cur.execute('TRUNCATE inspections,issues,stations,inspection_tables,inspection_issue_appeals CASCADE')
            cur.execute("DELETE FROM users WHERE id>4")
            cur.execute('''INSERT INTO stations VALUES(1,'浦东测试站','浦东'),(2,'松金测试站','松金');
              INSERT INTO inspection_tables VALUES(1,'质量安全环保检查表（现场）'),(2,'财务检查表（现场）');
              INSERT INTO users VALUES(5,'area','浦东片区','area_account','active',NULL),
                (6,'wrongarea','松金片区','area_account','active',NULL),(7,'quality','有权终审','quality_safety','active',NULL),
                (8,'noquality','无权终审','quality_safety','active',NULL),(9,'area2','另一个浦东账号','area_account','active',NULL);
              UPDATE clock_switch SET enabled=TRUE;
              INSERT INTO inspections(id,station_id,inspection_table_id,inspection_date,inspector_completion_status,sign_status)
                VALUES(1,1,1,'2026-10-01','待检查人确认','待签名确认');
              INSERT INTO issues VALUES(1,1,1,1,'pending'),(2,1,1,1,'pending');''')
        self.resolve=recipient_resolver(can_sign=lambda cur,u:bool(u.get('station_id')),
            has_permission=lambda cur,u,p:u['id']==7,
            normalize_region=lambda value:value,
            region_scope=lambda cur,u,*args:{'浦东'} if u['id'] in (5,9) else {'松金'})

    def rows(self,sql,params=()):
        with self.connect() as conn,conn.cursor() as cur:
            cur.execute(sql,params);return cur.fetchall()

    def execute(self,sql,params=()):
        with self.connect() as conn,conn.cursor() as cur:cur.execute(sql,params)

    def ready(self):
        self.execute("UPDATE inspections SET inspector_completion_status='已确认完成' WHERE id=1")
        self.execute("UPDATE issues SET audit_status='approved' WHERE inspection_id=1")

    def scan(self):return process_signature_changes(self.connect,self.resolve)

    def test_all_issues_and_completion_required_same_station_only_and_dedup(self):
        self.execute("UPDATE issues SET audit_status='approved' WHERE id=1")
        self.scan();self.assertEqual(self.rows('SELECT * FROM web_push_messages'),[])
        self.execute("UPDATE issues SET audit_status='rejected' WHERE id=2")
        self.scan();self.assertEqual(self.rows('SELECT * FROM web_push_messages'),[])
        self.execute("UPDATE inspections SET inspector_completion_status='已确认完成' WHERE id=1")
        self.scan();self.scan()
        self.assertEqual(len(self.rows('SELECT * FROM web_push_messages')),1)
        self.assertEqual([r['user_id'] for r in self.rows('SELECT user_id FROM web_push_recipients')],[2])
        self.execute("UPDATE issues SET audit_status='approved' WHERE id=1")
        self.scan();self.assertEqual(len(self.rows('SELECT * FROM web_push_messages')),1)
        detail=self.call('/api/management/notifications').json
        self.assertEqual(len(detail['sources']),3)
        self.assertEqual(detail['records'][0]['inbox_only'],1)
        message=detail['records'][0]['id']
        self.assertEqual(self.call(f'/api/management/notifications/{message}/deliveries').json['items'][0]['status'],'inbox_only')
        self.assertEqual(self.call('/api/management/notifications',user=2).status_code,403)

    def test_no_pending_issues_includes_empty_records_and_audit_reset_new_episode(self):
        self.ready();self.scan()
        self.execute("UPDATE issues SET audit_status='pending' WHERE id=1")
        self.scan()
        self.execute("UPDATE issues SET audit_status='approved' WHERE id=1")
        self.scan()
        self.assertEqual(len(self.rows('SELECT * FROM web_push_messages')),2)
        self.execute("INSERT INTO inspections(id,station_id,inspection_table_id,inspector_completion_status) VALUES(2,2,2,'已确认完成')")
        self.scan()
        self.assertEqual(len(self.rows('SELECT * FROM web_push_messages')),3)

    def test_acceptance_deadline_in_message_and_hint_only_for_enabled_quality_tables(self):
        self.execute("UPDATE inspections SET quality_accept_started_at=now(),quality_accept_deadline_at='2026-11-05T02:00:00Z' WHERE id=1")
        self.ready();self.scan()
        message=self.rows('SELECT * FROM web_push_messages')[0]
        self.assertIn('2026-11-05 10:00',message['body']);self.assertIn('系统将自动验收',message['push_hint'])
        self.assertNotIn('浦东',message['push_hint'])
        for sql in ("UPDATE clock_switch SET enabled=FALSE", "UPDATE inspections SET inspection_table_id=2 WHERE id=1"):
            self.execute("UPDATE inspections SET sign_status='已签名确认' WHERE id=1");self.scan()
            self.execute(sql)
            self.execute("UPDATE inspections SET sign_status='待签名确认' WHERE id=1");self.scan()
            self.assertNotIn('截止',self.rows('SELECT * FROM web_push_messages ORDER BY created_at DESC')[0]['body'])
            self.assertNotIn('时限',self.rows('SELECT * FROM web_push_messages ORDER BY created_at DESC')[0]['body'])

    def test_transaction_rollback_and_background_failure_preserve_retry(self):
        conn=self.connect()
        with conn.cursor() as cur:
            cur.execute("UPDATE issues SET audit_status='approved'")
            cur.execute("UPDATE inspections SET inspector_completion_status='已确认完成'")
        conn.rollback();conn.close();self.scan()
        self.assertFalse(self.rows('SELECT * FROM web_push_messages'))
        self.ready()
        with patch('web_push_business.enqueue_business',side_effect=RuntimeError('simulated')):
            with self.assertRaises(RuntimeError):self.scan()
        self.assertTrue(self.rows('SELECT * FROM web_push_signature_changes'))
        self.assertFalse(self.rows('SELECT * FROM web_push_messages'))
        self.scan();self.assertEqual(len(self.rows('SELECT * FROM web_push_messages')),1)

    def test_concurrent_scanners_and_writer_invalidations_are_not_lost(self):
        self.ready()
        with ThreadPoolExecutor(4) as pool:list(pool.map(lambda _:self.scan(),range(4)))
        self.assertEqual(len(self.rows('SELECT * FROM web_push_messages')),1)
        self.execute("UPDATE issues SET audit_status='pending' WHERE id=1")
        self.scan()
        self.execute("UPDATE issues SET audit_status='approved' WHERE id=1")
        original_resolve=self.resolve
        def fail_resolve(*args):
            # A separate record is changed during a scan; its invalidation must remain.
            self.execute("INSERT INTO inspections(id,station_id,inspection_table_id,inspector_completion_status) VALUES(2,2,2,'已确认完成')")
            return original_resolve(*args)
        process_signature_changes(self.connect,fail_resolve)
        self.assertEqual(self.rows('SELECT inspection_id FROM web_push_signature_changes')[0]['inspection_id'],2)
        self.scan();self.assertEqual(len(self.rows('SELECT * FROM web_push_messages')),3)

    def test_appeal_recipients_and_handoff_are_transactional_with_no_manual_rate_limit(self):
        self.execute("INSERT INTO inspection_issue_appeals VALUES(1,1,'area_pending')")
        with self.connect() as conn,conn.cursor() as cur:
            ids=self.resolve(cur,'area_pending',1,'浦东');self.assertEqual(ids,[5,9])
            notify_appeal(cur,1,'area_pending',ids);notify_appeal(cur,1,'area_pending',ids)
        self.assertEqual(len(self.rows('SELECT * FROM web_push_messages')),1)
        conn=self.connect()
        with conn.cursor() as cur:
            cur.execute("UPDATE inspection_issue_appeals SET status='quality_pending'")
            notify_appeal(cur,1,'quality_pending',self.resolve(cur,'quality_pending',1,'浦东'))
        conn.rollback();conn.close()
        self.assertEqual(len(self.rows('SELECT * FROM web_push_messages')),1)
        with self.connect() as conn,conn.cursor() as cur:
            cur.execute("UPDATE inspection_issue_appeals SET status='quality_pending'")
            notify_appeal(cur,1,'quality_pending',self.resolve(cur,'quality_pending',1,'浦东'))
        self.assertEqual(self.rows("SELECT r.user_id FROM web_push_recipients r JOIN web_push_messages m ON m.id=r.message_id WHERE m.source='appeal_quality'"),[dict(user_id=7)])
        self.assertEqual(self.call('/api/management/notifications?log_source=appeal_quality').json['records_total'],1)

    def test_fanout_optout_and_stale_business_deliveries_are_logged_without_network(self):
        self.register(2);self.register(2,key=fixtures.b64(bytes(reversed(range(32)))),suffix='second')
        self.ready();self.scan()
        self.assertEqual(len(self.rows('SELECT * FROM web_push_deliveries')),2)
        sent=[]
        def sender(subscription,payload,config):sent.append(payload);return SimpleNamespace(status_code=201)
        deliver_one(self.connect,self.app.config['SECRET_KEY'],config=self.configuration,sender=sender,recipients=self.resolve)
        self.assertEqual(sent[0]['scene'],'inspection_signature')
        self.assertNotIn('浦东',sent[0]['hint'])
        self.execute("UPDATE inspections SET sign_status='已签名确认'")
        deliver_one(self.connect,self.app.config['SECRET_KEY'],config=self.configuration,sender=sender,recipients=self.resolve)
        self.assertEqual(len(sent),1)
        self.assertEqual(len(self.rows("SELECT * FROM web_push_deliveries WHERE status='skipped'")),1)
        self.scan()
        self.execute("INSERT INTO web_push_preferences(user_id,enabled) VALUES(2,FALSE)")
        self.execute("UPDATE inspections SET sign_status='待签名确认'");self.scan()
        self.assertIn('暂停',self.rows("SELECT r.delivery_note FROM web_push_recipients r JOIN web_push_messages m ON m.id=r.message_id ORDER BY m.created_at DESC")[0]['delivery_note'])

    def test_upgrade_baselines_existing_pending_records_without_broadcast(self):
        self.ready()
        path=Path(__file__).parents[1]/'migrations/versions/20261101_002_business_push.py'
        spec=importlib.util.spec_from_file_location('baseline_business_push',path)
        migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
        with self.connect() as conn,conn.cursor() as cur:
            migration.op=SimpleNamespace(execute=cur.execute);migration.downgrade();migration.upgrade()
        self.scan()
        self.assertFalse(self.rows('SELECT * FROM web_push_messages'))
        self.execute("UPDATE issues SET audit_status='approved' WHERE id=1");self.scan()
        self.assertFalse(self.rows('SELECT * FROM web_push_messages'))

    def test_same_record_audit_writer_and_scanner_do_not_deadlock_or_lose_a_change(self):
        self.ready()
        with ThreadPoolExecutor(1) as pool:
            writes=[]
            def write_audit():
                with self.connect() as conn,conn.cursor() as cur:
                    cur.execute("SET LOCAL statement_timeout='5s'")
                    cur.execute("UPDATE issues SET audit_status='pending' WHERE id=1")
                    cur.execute('SELECT refresh_quality_acceptance(1)')
            def resolve(*args):
                writes.append(pool.submit(write_audit))
                return self.resolve(*args)
            process_signature_changes(self.connect,resolve)
            writes[0].result(timeout=8)
        self.assertTrue(self.rows('SELECT * FROM web_push_signature_changes'))
        self.scan()
        self.assertFalse(self.rows('SELECT ready FROM web_push_signature_state')[0]['ready'])

    def test_permissions_and_finished_appeals_rechecked_before_provider_send(self):
        self.register(2)
        self.execute("UPDATE users SET role='quality_safety',station_id=NULL WHERE id=2")
        self.execute("INSERT INTO inspection_issue_appeals VALUES(1,1,'quality_pending')")
        with self.connect() as conn,conn.cursor() as cur:
            notify_appeal(cur,1,'quality_pending',[2])
        sender=unittest.mock.Mock()
        deliver_one(self.connect,self.app.config['SECRET_KEY'],config=self.configuration,sender=sender,recipients=self.resolve)
        sender.assert_not_called()
        self.assertEqual(self.rows('SELECT status FROM web_push_deliveries')[0]['status'],'skipped')


@unittest.skipUnless(os.environ.get('ISSUE_LIFECYCLE_DB_TEST')=='1','requires isolated complete application schema')
class WorkflowPushTests(unittest.TestCase):
    setUp=appeal_fixtures.AppealDatabaseTests.setUp
    cleanup_database=appeal_fixtures.AppealDatabaseTests.cleanup_database
    post=appeal_fixtures.AppealDatabaseTests.post
    start=appeal_fixtures.AppealDatabaseTests.start
    decide=appeal_fixtures.AppealDatabaseTests.decide

    def test_actual_appeal_submission_and_handoff_enqueue_inside_the_business_transaction(self):
        aid=self.start()
        self.cur.execute("SELECT source FROM web_push_messages WHERE entity_id=%s AND kind='business'",(aid,))
        self.assertEqual([r['source'] for r in self.cur.fetchall()],['appeal_area'])
        self.assertEqual(self.decide(aid,'area','area_pending').status_code,200)
        self.cur.execute("SELECT source FROM web_push_messages WHERE entity_id=%s AND kind='business' ORDER BY source",(aid,))
        self.assertEqual([r['source'] for r in self.cur.fetchall()],['appeal_area','appeal_quality'])

    def test_notification_failure_rolls_back_appeal_and_its_claim_not_just_the_outbox(self):
        with patch('issue_appeals.notify_appeal',side_effect=RuntimeError('test-only failure')):
            response=self.post(f"/api/issues/{self.issue['id']}/appeals",reason='测试回滚')
        self.assertEqual(response.status_code,500)
        self.cur.execute('SELECT id FROM inspection_issue_appeals WHERE issue_id=%s',(self.issue['id'],))
        self.assertIsNone(self.cur.fetchone())
        self.cur.execute('SELECT issue_id FROM inspection_issue_appeal_claims WHERE issue_id=%s',(self.issue['id'],))
        self.assertIsNone(self.cur.fetchone())

    def test_signature_uses_real_badge_recipients_and_real_work_hour_deadline(self):
        import app as core
        self.cur.execute('''INSERT INTO users(username,role,real_name,password_hash,station_id)
          VALUES('push-test-signature','station_manager','测试站经理','test-only-no-login',%s) RETURNING *''',(self.issue['station_id'],))
        user=self.cur.fetchone()
        self.cur.execute("UPDATE inspections SET sign_status='待签名确认',inspector_completion_status='已确认完成',inspector_completed_at=CURRENT_TIMESTAMP WHERE id=%s",(self.issue['inspection_id'],))
        self.cur.execute("UPDATE issues SET audit_status='approved',audited_at=CURRENT_TIMESTAMP WHERE inspection_id=%s",(self.issue['inspection_id'],))
        # The fully migrated fixture must not run legacy lazy DDL, which commits its connection.
        with patch.object(core,'ISSUE_INSPECTOR_SCHEMA_READY',True),patch.object(core,'INSPECTION_COMPLETION_SCHEMA_READY',True):
            self.assertEqual(core.get_inspection_sign_pending_count_for_user(self.cur,user),1)
        wrapper=SimpleNamespace(cursor=self.conn.cursor,commit=lambda:None,rollback=lambda:None,close=lambda:None)
        process_signature_changes(lambda:wrapper,core.push_recipients)
        self.cur.execute("SELECT id,body,push_hint FROM web_push_messages WHERE source='inspection_signature' AND entity_id=%s",(self.issue['inspection_id'],))
        message=self.cur.fetchone();self.assertIsNotNone(message)
        self.cur.execute('SELECT user_id FROM web_push_recipients WHERE message_id=%s',(message['id'],))
        self.assertIn(user['id'],[row['user_id'] for row in self.cur.fetchall()])
        self.cur.execute("SELECT quality_effective_deadline('acceptance',quality_accept_deadline_at,quality_accept_started_at) AS deadline FROM inspections WHERE id=%s",(self.issue['inspection_id'],))
        deadline=self.cur.fetchone()['deadline'].astimezone(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M')
        self.assertIn(deadline,message['body']);self.assertIn(deadline,message['push_hint'])


if __name__=='__main__':unittest.main()
