"""Real outbox persistence, recipient boundaries, dedup and stale-stage protection."""
import os
import unittest
from tests import test_web_push as fixtures
from non_oil_notifications import notify_stage, delivery_allowed


@unittest.skipUnless(os.environ.get('WEB_PUSH_TEST_DSN'), 'isolated PostgreSQL opt-in')
class NonOilNotificationsTests(unittest.TestCase):
    connect = classmethod(fixtures.PushDatabaseTests.connect.__func__)
    tearDownClass = classmethod(fixtures.PushDatabaseTests.tearDownClass.__func__)

    @classmethod
    def setUpClass(cls):
        fixtures.PushDatabaseTests.setUpClass.__func__(cls)
        with cls.connect() as conn, conn.cursor() as cur:
            cur.execute("""ALTER TABLE inspection_tables ADD COLUMN checklist_mode text;
                ALTER TABLE issues ADD COLUMN status text, ADD COLUMN non_oil_review_stage text,
                    ADD COLUMN non_oil_review_event_id bigint;
                CREATE TABLE inspection_issue_flow_history(id bigint PRIMARY KEY,issue_id int);
                INSERT INTO stations VALUES(1,'测试站','浦东');
                INSERT INTO inspection_tables VALUES(1,'非油检查表（现场）','offline');
                INSERT INTO issues(id,station_id,inspection_table_id,audit_status,status,non_oil_review_stage,non_oil_review_event_id)
                    VALUES(48,1,1,'approved','待复核','department',100);
                INSERT INTO inspection_issue_flow_history VALUES(100,48);
                INSERT INTO users VALUES(5,'department','非油','non_oil','active',NULL),
                    (6,'area','片区','area_non_oil','active',NULL),
                    (7,'wrongarea','其他片区','area_account','active',NULL),
                    (8,'field','盛大','supervisor','active',NULL);""")

    def setUp(self):
        self.policy = dict(can_view_review_queue=lambda cur,user: True,
            can_view_rectification_queue=lambda cur,user: True,
            has_permission=lambda cur,user,key: True,
            issue_in_review_queue_scope=lambda cur,user,issue: user['id'] != 7)
        with self.connect() as conn,conn.cursor() as cur:
            cur.execute('TRUNCATE web_push_messages,web_push_recipients,web_push_deliveries CASCADE')
            cur.execute("UPDATE issues SET status='待复核',audit_status='approved',non_oil_review_stage='department',non_oil_review_event_id=100 WHERE id=48")
            cur.execute("UPDATE users SET account_status='active' WHERE id=5")

    def test_each_stage_uses_correct_recipients_and_a_single_persisted_event(self):
        for stage,expected in [('department',[5]),('field',[8]),('area',[6]),('area_return',[6]),('station',[2])]:
            with self.connect() as conn,conn.cursor() as cur:
                notify_stage(cur,48,100,stage,self.policy)
                notify_stage(cur,48,100,stage,self.policy)
                cur.execute('SELECT r.user_id FROM web_push_recipients r JOIN web_push_messages m ON m.id=r.message_id WHERE m.event_key=%s ORDER BY r.user_id',
                    (f'non_oil_review:100:{stage}',))
                self.assertEqual([row['user_id'] for row in cur.fetchall()],expected)
                cur.execute('SELECT count(*) AS n FROM web_push_messages WHERE event_key=%s',(f'non_oil_review:100:{stage}',))
                self.assertEqual(cur.fetchone()['n'],1)

    def test_delivery_rechecks_stage_permissions_and_active_account(self):
        message=dict(event_key='non_oil_review:100:department',entity_id=48)
        with self.connect() as conn,conn.cursor() as cur:
            self.assertTrue(delivery_allowed(cur,message,5,self.policy))
            self.assertFalse(delivery_allowed(cur,message,6,self.policy))
            cur.execute("UPDATE users SET account_status='disabled' WHERE id=5")
            self.assertFalse(delivery_allowed(cur,message,5,self.policy))
            cur.execute("UPDATE users SET account_status='active' WHERE id=5")
            self.policy['has_permission']=lambda *args:False
            self.assertFalse(delivery_allowed(cur,message,5,self.policy))
            self.policy['has_permission']=lambda *args:True
            cur.execute("UPDATE issues SET non_oil_review_stage='area_return',non_oil_review_event_id=101 WHERE id=48")
            self.assertFalse(delivery_allowed(cur,message,5,self.policy))

    def test_outbox_rollback_and_station_notice_becomes_stale_after_a_new_round(self):
        conn=self.connect()
        try:
            with conn.cursor() as cur: notify_stage(cur,48,100,'department',self.policy)
            conn.rollback()
            with conn.cursor() as cur:
                cur.execute('SELECT count(*) AS n FROM web_push_messages')
                self.assertEqual(cur.fetchone()['n'],0)
                cur.execute("UPDATE issues SET status='待整改',non_oil_review_stage=NULL,non_oil_review_event_id=NULL WHERE id=48")
                message=dict(event_key='non_oil_review:100:station',entity_id=48)
                self.assertTrue(delivery_allowed(cur,message,2,self.policy))
                cur.execute("UPDATE issues SET status='待复核' WHERE id=48")
                self.assertFalse(delivery_allowed(cur,message,2,self.policy))
        finally: conn.close()
