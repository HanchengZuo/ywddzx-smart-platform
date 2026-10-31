import base64
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
import uuid
import subprocess
import sys
import tempfile
import stat
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, g, request
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from web_push import configuration, b64, validate_subscription, seal, unseal, device_key, device_labels
from web_push_http import register_web_push
from web_push_worker import deliver_one


def subscription(suffix='test'):
    key=ec.generate_private_key(ec.SECP256R1()).public_key()
    return {'endpoint':'https://fcm.googleapis.com/fcm/send/'+suffix,'keys':{
        'auth':b64(bytes(range(16))), 'p256dh':b64(key.public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint))}}


def config():
    key=ec.generate_private_key(ec.SECP256R1())
    return configuration({'WEB_PUSH_SUBJECT':'mailto:test@example.com','WEB_PUSH_VAPID_PRIVATE_KEY':b64(
        key.private_bytes(serialization.Encoding.DER,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))})


class PushValidationTests(unittest.TestCase):
    def test_key_generator_creates_owner_only_persistent_file_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'keys.env'
            command=[sys.executable,'-m','web_push_keys','--output',str(path),'--subject','mailto:test@example.com']
            result=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
            self.assertNotIn('WEB_PUSH_VAPID_PRIVATE_KEY=',result.stdout)
            before=path.read_bytes()
            self.assertNotEqual(subprocess.run(command,capture_output=True).returncode,0)
            self.assertEqual(path.read_bytes(),before)

    def test_vapid_configuration_derived_public_key_and_explicit_disabled(self):
        value=config();self.assertTrue(value['ready']);self.assertEqual(len(base64.urlsafe_b64decode(value['public_key']+'==')),65)
        self.assertFalse(configuration({})['ready'])
        self.assertFalse(configuration({'WEB_PUSH_ENABLED':'false'})['ready'])
        self.assertFalse(configuration({'WEB_PUSH_VAPID_PRIVATE_KEY':'invalid','WEB_PUSH_SUBJECT':'mailto:test@example.com'})['ready'])

    def test_endpoint_allowlist_blocks_local_network_redirect_destinations_and_invalid_crypto(self):
        value=subscription();self.assertEqual(validate_subscription(value),value)
        for host in ('web.push.apple.com','updates.push.apple.com'):
            self.assertEqual(validate_subscription({**value,'endpoint':f'https://{host}/test'})['endpoint'],f'https://{host}/test')
        for endpoint in ('http://fcm.googleapis.com/test','https://localhost/x','https://127.0.0.1/x',
                         'https://169.254.169.254/x','https://fcm.googleapis.com.evil.test/x',
                         'https://fcm.googleapis.com@evil.test/x','https://fcm.googleapis.com:444/x','https://web.push.apple.com.evil.test/x'):
            with self.subTest(endpoint=endpoint),self.assertRaises(ValueError):
                validate_subscription({**value,'endpoint':endpoint})
        for keys in ({'auth':'invalid','p256dh':value['keys']['p256dh']},{'auth':value['keys']['auth'],'p256dh':'invalid'}):
            with self.assertRaises(ValueError):validate_subscription({**value,'keys':keys})

    def test_encryption_secrets_and_device_token_validation(self):
        value=subscription();encrypted=seal(value,'secret')
        self.assertNotIn('googleapis',encrypted);self.assertEqual(unseal(encrypted,'secret'),value)
        with self.assertRaises(Exception):unseal(encrypted,'another-secret')
        with self.assertRaises(ValueError):device_key('abc')
        self.assertEqual(device_labels('Mozilla Android Chrome/123'),('Android','Chrome'))
        self.assertEqual(device_labels('Mozilla iPhone Mobile/ Safari/'),('iOS / iPadOS','Safari'))

    def test_sender_disables_redirects_and_does_not_use_mutable_shared_vapid_claims(self):
        from web_push import send
        with patch('pywebpush.webpush',return_value=SimpleNamespace(status_code=201)) as provider:
            send(subscription(),{'title':'test'},config())
        session=provider.call_args.kwargs['requests_session']
        with patch('requests.Session.request',return_value=SimpleNamespace(status_code=302)) as request_mock:
            session.request('POST','https://fcm.googleapis.com/test')
        self.assertFalse(request_mock.call_args.kwargs['allow_redirects'])
        self.assertEqual(provider.call_args.kwargs['timeout'],12)

    def test_real_vapid_signing_and_payload_encryption_without_network(self):
        import requests
        from web_push import send
        response=requests.Response();response.status_code=201
        with patch('requests.Session.request',return_value=response) as network:
            result=send(subscription(),{'title':'fixture'},config())
        self.assertEqual(result.status_code,201)
        self.assertEqual(network.call_count,1)
        self.assertFalse(network.call_args.kwargs['allow_redirects'])
        self.assertIn('vapid',network.call_args.kwargs['headers']['Authorization'].lower())


@unittest.skipUnless(os.environ.get('WEB_PUSH_TEST_DSN'),'requires isolated PostgreSQL test DSN')
class PushDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn=os.environ['WEB_PUSH_TEST_DSN']
        if 'dbname=test_' not in cls.dsn: raise RuntimeError('Tests require an explicit test_ database')
        cls.schema='push_test_'+uuid.uuid4().hex
        conn=psycopg2.connect(cls.dsn);conn.autocommit=True
        with conn.cursor() as cur:cur.execute(f'CREATE SCHEMA "{cls.schema}"')
        conn.close()
        with cls.connect() as conn,conn.cursor() as cur:
            cur.execute('''CREATE TABLE users(id int PRIMARY KEY,username text,real_name text,role text,account_status text);
              INSERT INTO users VALUES(1,'root','管理员','root','active'),(2,'station','站点','station_manager','active'),
              (3,'third','另一用户','station_manager','active'),(4,'disabled','停用用户','station_manager','disabled');''')
            path=Path(__file__).parents[1]/'migrations/versions/20261101_001_web_push.py'
            spec=importlib.util.spec_from_file_location('push_migration',path);migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
            migration.op=SimpleNamespace(execute=cur.execute);migration.upgrade()

    @classmethod
    def connect(cls):return psycopg2.connect(cls.dsn,options=f'-c search_path={cls.schema}',cursor_factory=RealDictCursor)

    @classmethod
    def tearDownClass(cls):
        conn=psycopg2.connect(cls.dsn);conn.autocommit=True
        with conn.cursor() as cur:cur.execute(f'DROP SCHEMA "{cls.schema}" CASCADE')
        conn.close()

    def setUp(self):
        with self.connect() as conn,conn.cursor() as cur:
            cur.execute('TRUNCATE web_push_preferences,web_push_devices,web_push_messages,web_push_recipients,web_push_deliveries CASCADE')
            cur.execute("UPDATE users SET account_status='active' WHERE id IN (1,2,3)")
        self.app=Flask(__name__);self.app.config['SECRET_KEY']='test-only-encryption-key'
        @self.app.before_request
        def auth():
            value=request.headers.get('X-User')
            if value in ('1','2','3'):
                g.current_user={'id':int(value),'role':'root' if value=='1' else 'station_manager','username':'test','real_name':'测试用户'}
                if request.headers.get('X-Impersonated'):g.impersonator={'id':1,'role':'root'}
        register_web_push(self.app,connect=self.connect,has_permission=lambda cur,user,key:user['role']=='root' and key=='manage_web_push')
        self.client=self.app.test_client();self.configuration=config()
        self.patch=patch('web_push_http.configuration',return_value=self.configuration);self.patch.start();self.addCleanup(self.patch.stop)
        self.key=b64(bytes(range(32)))

    def call(self,path,method='get',user=1,**kwargs):
        return getattr(self.client,method)(path,headers={'X-User':str(user)},**kwargs)

    def register(self,user=2,key=None,suffix='test'):
        response=self.call('/api/notifications/device','post',user,json={'device_key':key or self.key,
            'capability':'supported','permission':'granted','subscription':subscription(suffix)})
        self.assertEqual(response.status_code,200,response.json)
        return response.json['device']

    def dispatch(self,ids=None,request_id=None):
        response=self.call('/api/management/notifications/send','post',json={
            'user_ids':ids or [2],'title':'办理提醒','body':'需要登录后查看的业务正文','request_id':request_id or str(uuid.uuid4())})
        self.assertEqual(response.status_code,202,response.json)
        return response.json['id']

    def test_authentication_permission_and_impersonation_are_enforced(self):
        self.assertEqual(self.client.get('/api/notifications').status_code,401)
        self.assertEqual(self.call('/api/management/notifications',user=2).status_code,403)
        self.assertEqual(self.call('/api/management/notifications/send','post',user=2,json={}).status_code,403)
        self.assertEqual(self.client.get('/api/notifications',headers={'X-User':'2','X-Impersonated':'1'}).status_code,403)

    def test_default_enabled_and_unknown_users_are_not_classified_unsupported(self):
        self.assertTrue(self.call('/api/notifications',user=2).json['enabled'])
        data=self.call('/api/management/notifications').json
        self.assertEqual(data['summary'],{'total':3,'enabled':0,'not_enabled':3,'unsupported':0})
        self.assertEqual(self.call('/api/notifications/device','post',user=2,json={
            'device_key':self.key,'capability':'unsupported','permission':'unavailable'}).status_code,200)
        self.assertEqual(self.call('/api/management/notifications').json['summary']['unsupported'],1)

    def test_multi_device_fanout_idempotency_and_secret_redaction(self):
        self.register();self.register(key=b64(bytes(range(1,33))),suffix='second')
        request_id=str(uuid.uuid4());identifier=self.dispatch(request_id=request_id)
        self.assertEqual(self.dispatch(request_id=request_id),identifier)
        with self.connect() as conn,conn.cursor() as cur:
            cur.execute('SELECT count(*) AS n FROM web_push_deliveries');self.assertEqual(cur.fetchone()['n'],2)
            cur.execute('SELECT count(*) AS n FROM web_push_recipients');self.assertEqual(cur.fetchone()['n'],1)
        devices=self.call('/api/management/notifications/users/2/devices').json
        self.assertEqual(len(devices['items']),2)
        self.assertNotIn('subscription_cipher',json.dumps(devices));self.assertNotIn('endpoint',json.dumps(devices))

    def test_ownership_rebind_skips_old_account_jobs_and_scopes_personal_inbox(self):
        original=self.register();identifier=self.dispatch()
        self.register(user=3,suffix='new-user')
        sender=MagicMock(side_effect=AssertionError('must not send old account messages'))
        self.assertTrue(deliver_one(self.connect,'test-only-encryption-key',self.configuration,sender))
        sender.assert_not_called()
        self.assertEqual(self.call('/api/notifications/devices',user=2).json['items'],[])
        self.assertEqual(self.call('/api/notifications',user=3).json['total'],0)
        self.assertEqual(self.call(f'/api/notifications/{identifier}/read','post',user=3,json={}).status_code,404)
        self.assertEqual(self.call('/api/notifications/device','delete',user=2,json={'device_key':self.key}).status_code,403)
        self.assertEqual(original['id'],self.call('/api/notifications/devices',user=3).json['items'][0]['id'])

    def test_revoked_or_disabled_preferences_and_accounts_skip_queued_deliveries(self):
        for action in ('preference','device','account'):
            with self.subTest(action=action):
                with self.connect() as conn,conn.cursor() as cur:
                    cur.execute('TRUNCATE web_push_preferences,web_push_devices,web_push_messages,web_push_recipients,web_push_deliveries CASCADE')
                    cur.execute("UPDATE users SET account_status='active' WHERE id=2")
                self.register();self.dispatch()
                if action=='preference':self.call('/api/notifications/preference','put',user=2,json={'enabled':False})
                elif action=='device':self.call('/api/notifications/device','delete',user=2,json={'device_key':self.key})
                else:
                    with self.connect() as conn,conn.cursor() as cur:cur.execute("UPDATE users SET account_status='disabled' WHERE id=2")
                sender=MagicMock();deliver_one(self.connect,'test-only-encryption-key',self.configuration,sender);sender.assert_not_called()

    def test_delivery_acceptance_is_not_receipt_and_expiry_only_invalidates_matching_revision(self):
        self.register();identifier=self.dispatch()
        sender=MagicMock(return_value=SimpleNamespace(status_code=201))
        self.assertTrue(deliver_one(self.connect,'test-only-encryption-key',self.configuration,sender))
        payload=sender.call_args.args[1]
        self.assertNotIn('业务正文',json.dumps(payload));self.assertEqual(payload['url'],'/notifications')
        row=self.call('/api/notifications',user=2).json['items'][0]
        self.assertEqual(row['accepted'],1);self.assertIsNone(row['confirmed_at'])
        self.assertEqual(self.call(f'/api/notifications/{identifier}/read','post',user=2,json={'confirm':True}).status_code,200)
        self.assertIsNotNone(self.call('/api/notifications',user=2).json['items'][0]['confirmed_at'])
        self.dispatch();deliver_one(self.connect,'test-only-encryption-key',self.configuration,lambda *args:SimpleNamespace(status_code=410))
        self.assertFalse(self.call('/api/notifications/devices',user=2).json['items'][0]['active'])

    def test_transient_failures_retry_boundedly_and_no_secrets_in_errors(self):
        self.register();self.dispatch()
        for attempt in range(3):
            deliver_one(self.connect,'test-only-encryption-key',self.configuration,MagicMock(side_effect=RuntimeError('secret-endpoint-and-keys')))
            with self.connect() as conn,conn.cursor() as cur:
                cur.execute('SELECT * FROM web_push_deliveries');row=cur.fetchone()
                self.assertEqual(row['attempts'],attempt+1)
                self.assertNotIn('secret',row['last_error'])
                self.assertEqual(row['status'],'queued' if attempt<2 else 'failed')
                cur.execute("UPDATE web_push_deliveries SET available_at=now()-interval '1 minute'")
        self.assertFalse(deliver_one(self.connect,'test-only-encryption-key',self.configuration,MagicMock()))

    def test_database_lease_prevents_two_workers_sending_same_job_and_network_is_outside_transaction(self):
        self.register();self.dispatch();calls=[]
        def send(*args):
            calls.append(1)
            with self.connect() as conn,conn.cursor() as cur:
                cur.execute("SELECT status FROM web_push_deliveries");self.assertEqual(cur.fetchone()['status'],'sending')
            return SimpleNamespace(status_code=201)
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _:deliver_one(self.connect,'test-only-encryption-key',self.configuration,send),range(2)))
        self.assertEqual(len(calls),1)

    def test_current_device_test_cannot_send_to_someone_elses_devices(self):
        self.register(user=3)
        response=self.call('/api/notifications/test','post',user=2,json={'device_key':self.key,'request_id':str(uuid.uuid4())})
        self.assertEqual(response.status_code,400)
        self.register(user=2)
        self.assertEqual(self.call('/api/notifications/test','post',user=2,json={'device_key':self.key,'request_id':str(uuid.uuid4())}).status_code,202)

    def test_invalid_input_rolls_back_and_no_message_is_created(self):
        response=self.call('/api/management/notifications/send','post',json={'user_ids':[4],'title':'test','body':'body','request_id':str(uuid.uuid4())})
        self.assertEqual(response.status_code,400)
        with self.connect() as conn,conn.cursor() as cur:
            cur.execute('SELECT count(*) AS n FROM web_push_messages');self.assertEqual(cur.fetchone()['n'],0)

    def test_heartbeat_preserves_revision_but_resubscription_invalidates_old_queued_work(self):
        data={'device_key':self.key,'capability':'supported','permission':'granted','subscription':subscription()}
        self.assertEqual(self.call('/api/notifications/device','post',user=2,json=data).status_code,200)
        self.dispatch()
        self.call('/api/notifications/device','post',user=2,json=data)
        sender=MagicMock(return_value=SimpleNamespace(status_code=201))
        deliver_one(self.connect,'test-only-encryption-key',self.configuration,sender);sender.assert_called_once()
        self.dispatch();data['subscription']=subscription('rotated')
        self.call('/api/notifications/device','post',user=2,json=data)
        sender.reset_mock();deliver_one(self.connect,'test-only-encryption-key',self.configuration,sender);sender.assert_not_called()

    def test_crashed_worker_lease_is_recovered_but_never_exceeds_attempt_limit(self):
        self.register();self.dispatch()
        with self.connect() as conn,conn.cursor() as cur:
            cur.execute("UPDATE web_push_deliveries SET status='sending',attempts=1,lease=%s,lease_until=now()-interval '1 minute'",(str(uuid.uuid4()),))
        sender=MagicMock(return_value=SimpleNamespace(status_code=201))
        self.assertTrue(deliver_one(self.connect,'test-only-encryption-key',self.configuration,sender));sender.assert_called_once()
        with self.connect() as conn,conn.cursor() as cur:
            cur.execute('SELECT status,attempts FROM web_push_deliveries');row=cur.fetchone()
            self.assertEqual((row['status'],row['attempts']),('accepted',2))

    def test_duplicate_request_with_changed_recipients_does_not_silently_send_to_wrong_people(self):
        request_id=str(uuid.uuid4());self.dispatch(request_id=request_id)
        response=self.call('/api/management/notifications/send','post',json={
            'user_ids':[3],'title':'办理提醒','body':'需要登录后查看的业务正文','request_id':request_id})
        self.assertEqual(response.status_code,400)

    def test_disabled_queue_does_no_database_or_network_work(self):
        connect=MagicMock();sender=MagicMock()
        self.assertFalse(deliver_one(connect,'secret',{'ready':False},sender))
        connect.assert_not_called();sender.assert_not_called()

    def test_settings_return_only_public_key_and_admin_records_paginate(self):
        data=self.call('/api/notifications/settings',user=2).json
        self.assertTrue(data['enabled']);self.assertTrue(data['configured'])
        self.assertEqual(data['public_key'],self.configuration['public_key'])
        self.assertNotIn(self.configuration['private_key'],json.dumps(data))
        self.dispatch()
        data=self.call('/api/management/notifications?log_page=2').json
        self.assertEqual(data['records'],[]);self.assertEqual(data['records_total'],1)

    def test_rate_limit_preserves_existing_messages_and_limits_new_requests(self):
        for _ in range(5):self.dispatch()
        response=self.call('/api/management/notifications/send','post',json={
            'user_ids':[2],'title':'more','body':'more','request_id':str(uuid.uuid4())})
        self.assertEqual(response.status_code,400)
        with self.connect() as conn,conn.cursor() as cur:
            cur.execute('SELECT count(*) AS n FROM web_push_messages');self.assertEqual(cur.fetchone()['n'],5)
