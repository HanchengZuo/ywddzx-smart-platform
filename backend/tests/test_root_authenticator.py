import base64
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
import uuid

from cryptography.fernet import InvalidToken
from flask import Flask, g, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor

from root_authenticator import eligible, hotp, matching_counter, seal, unseal, authenticate, register_root_authenticator

ROOT = {'id':1,'username':'root','role':'root','account_status':'active','auth_version':1}
SECRET = base64.b32encode(b'12345678901234567890').decode()


class TotpCryptoTests(unittest.TestCase):
    def test_rfc6238_sha1_vectors_with_six_digits(self):
        for now,expected in [(59,'287082'),(1111111109,'081804'),(1111111111,'050471'),
                (1234567890,'005924'),(2000000000,'279037'),(20000000000,'353130')]:
            self.assertEqual(hotp(SECRET,now//30),expected)
            self.assertEqual(matching_counter(SECRET,expected,now),now//30)

    def test_window_replay_malformed_and_root_only(self):
        now=1234567890;counter=now//30
        self.assertEqual(matching_counter(SECRET,hotp(SECRET,counter-1),now),counter-1)
        self.assertEqual(matching_counter(SECRET,hotp(SECRET,counter+1),now),counter+1)
        self.assertIsNone(matching_counter(SECRET,hotp(SECRET,counter),now,counter))
        self.assertIsNone(matching_counter(SECRET,hotp(SECRET,counter-2),now))
        for value in ('１２３４５６','12345','1234567','123 456',123456,None):
            self.assertIsNone(matching_counter(SECRET,value,now))
        self.assertTrue(eligible(ROOT))
        for changes in ({'role':'quality_safety'},{'username':'other-root'},{'account_status':'suspended'}):
            cur=MagicMock()
            self.assertFalse(authenticate(cur,{**ROOT,**changes},'123456','test-key'))
            cur.execute.assert_not_called()

    def test_secret_is_encrypted_bound_to_user_and_fails_closed_on_key_change(self):
        encrypted=seal(SECRET,1,'key')
        self.assertNotIn(SECRET,encrypted)
        self.assertEqual(unseal(encrypted,1,'key'),SECRET)
        self.assertNotEqual(encrypted,seal(SECRET,1,'key'))
        with self.assertRaises(ValueError):unseal(encrypted,2,'key')
        with self.assertRaises(InvalidToken):unseal(encrypted,1,'new-key')


@unittest.skipUnless(os.environ.get('ROOT_AUTHENTICATOR_TEST_DSN'), 'Requires isolated test PostgreSQL')
class TotpDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.dsn=os.environ['ROOT_AUTHENTICATOR_TEST_DSN']
        self.schema='root_totp_test_'+uuid.uuid4().hex
        self.bootstrap=psycopg2.connect(self.dsn)
        self.addCleanup(self.cleanup)
        with self.bootstrap.cursor() as cur:
            cur.execute('SELECT current_database()')
            if not cur.fetchone()[0].startswith('test_'):raise RuntimeError('Only test databases are allowed')
            cur.execute(f'CREATE SCHEMA {self.schema}')
            cur.execute(f'SET search_path TO {self.schema}')
            cur.execute('CREATE TABLE users(id INTEGER PRIMARY KEY,auth_version INTEGER DEFAULT 1,updated_at TIMESTAMPTZ)')
            cur.execute('INSERT INTO users(id) VALUES (1)')
            cur.execute('CREATE TABLE audit_events(action TEXT,result TEXT)')
            # Rate-limit tables stay isolated too.
            cur.execute('''CREATE TABLE authentication_rate_limits(scope_key TEXT PRIMARY KEY,scope_type TEXT,
                attempt_count INTEGER,window_started_at TIMESTAMPTZ,blocked_until TIMESTAMPTZ,updated_at TIMESTAMPTZ)''')
            path=Path(__file__).parents[1]/'migrations/versions/20261031_001_root_authenticator.py'
            spec=importlib.util.spec_from_file_location('root_totp_migration',path)
            migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
            with patch.object(migration.op,'execute',cur.execute):migration.upgrade()
        self.bootstrap.commit()
        self.current_user=ROOT.copy();self.impersonator=None
        self.app=Flask(__name__);self.app.config['SECRET_KEY']='isolated-test-key'
        @self.app.before_request
        def identity():g.current_user=self.current_user;g.impersonator=self.impersonator
        def verify(token,user):
            if token!='fresh-passkey-grant':raise ValueError('需要Passkey验证')
        self.invalidate=MagicMock()
        def audit(cur,user,action,result):cur.execute('INSERT INTO audit_events VALUES(%s,%s)',(action,result))
        register_root_authenticator(self.app,connect=self.connect,fetch_user=lambda cur,uid:self.current_user,
            verify_management=verify,audit=audit,invalidate=self.invalidate)
        self.client=self.app.test_client()

    def connect(self):
        conn=psycopg2.connect(self.dsn,cursor_factory=RealDictCursor)
        with conn.cursor() as cur:cur.execute(f'SET search_path TO {self.schema}')
        return conn

    def cleanup(self):
        self.bootstrap.rollback()
        with self.bootstrap.cursor() as cur:cur.execute(f'DROP SCHEMA IF EXISTS {self.schema} CASCADE')
        self.bootstrap.commit();self.bootstrap.close()

    def row(self):
        conn=self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT *,EXTRACT(EPOCH FROM clock_timestamp()) AS now FROM root_authenticators WHERE user_id=1')
                return cur.fetchone()
        finally:conn.close()

    def start(self):
        response=self.client.post('/api/auth/root-authenticator',json={'management_token':'fresh-passkey-grant'})
        self.assertEqual(response.status_code,200,response.json)
        return response.json

    def confirm(self,setup,code):
        return self.client.put('/api/auth/root-authenticator',json={'management_token':'fresh-passkey-grant','setup_id':setup['setup_id'],'code':code})

    def test_enrollment_status_no_secret_and_disable_requires_step_up(self):
        self.assertFalse(self.client.get('/api/auth/root-authenticator').json['enabled'])
        self.assertEqual(self.client.post('/api/auth/root-authenticator',json={}).status_code,400)
        setup=self.start()
        self.assertTrue(setup['qr_code'].startswith('data:image/png;base64,'))
        row=self.row()
        self.assertNotIn(setup['secret'],row['pending_ciphertext'])
        status=self.client.get('/api/auth/root-authenticator').json
        self.assertNotIn('secret',status);self.assertNotIn('qr_code',status);self.assertFalse(status['enabled'])
        step=int(row['now'])//30
        response=self.confirm(setup,hotp(setup['secret'],step))
        self.assertEqual(response.status_code,200,response.json)
        self.assertTrue(response.json['session_invalidated'])
        self.assertTrue(self.client.get('/api/auth/root-authenticator').json['enabled'])
        self.assertIsNone(self.row()['pending_ciphertext'])
        conn=self.connect()
        try:
            with conn.cursor() as cur:
                self.assertFalse(authenticate(cur,ROOT,hotp(setup['secret'],step),self.app.config['SECRET_KEY']))
            conn.commit()
        finally:conn.close()
        self.assertEqual(self.client.delete('/api/auth/root-authenticator',json={}).status_code,400)
        response=self.client.delete('/api/auth/root-authenticator',json={'management_token':'fresh-passkey-grant'})
        self.assertEqual(response.status_code,200)
        self.assertIsNone(self.row());self.assertEqual(self.invalidate.call_count,2)

    def test_wrong_codes_lock_setup_and_new_setup_invalidates_old_nonce(self):
        first=self.start();second=self.start()
        self.assertEqual(self.confirm(first,'123456').status_code,400)
        for _ in range(5):self.assertEqual(self.confirm(second,'bad').status_code,400)
        self.assertEqual(self.row()['pending_attempts'],5)
        self.assertEqual(self.confirm(second,hotp(second['secret'],int(self.row()['now'])//30)).status_code,400)
        third=self.start()
        conn=self.connect()
        with conn.cursor() as cur:cur.execute("UPDATE root_authenticators SET pending_expires_at=clock_timestamp()-interval '1 second'")
        conn.commit();conn.close()
        self.assertEqual(self.confirm(third,hotp(third['secret'],int(self.row()['now'])//30)).status_code,400)

    def test_other_users_and_impersonation_cannot_manage(self):
        for user in (None,{**ROOT,'role':'quality_safety'},{**ROOT,'username':'other'}):
            self.current_user=user
            for method in ('get','post','put','delete'):
                self.assertEqual(getattr(self.client,method)('/api/auth/root-authenticator').status_code,403)
        self.current_user=ROOT;self.impersonator=ROOT
        self.assertEqual(self.client.get('/api/auth/root-authenticator').status_code,403)

    def test_concurrent_login_consumes_code_once_and_failed_transaction_does_not_consume(self):
        conn=self.connect()
        with conn.cursor() as cur:
            cur.execute('INSERT INTO root_authenticators(user_id,secret_ciphertext) VALUES (1,%s)',(seal(SECRET,1,self.app.config['SECRET_KEY']),))
            cur.execute('SELECT EXTRACT(EPOCH FROM clock_timestamp()) AS now')
            code=hotp(SECRET,int(cur.fetchone()['now'])//30)
        conn.commit()
        with conn.cursor() as cur:self.assertTrue(authenticate(cur,ROOT,code,self.app.config['SECRET_KEY']))
        conn.rollback();conn.close()
        def attempt(_):
            connection=self.connect()
            try:
                with connection.cursor() as cur:result=authenticate(cur,ROOT,code,self.app.config['SECRET_KEY'])
                connection.commit();return result
            finally:connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,range(2)))
        self.assertEqual(sorted(results),[False,True])

    def test_account_wide_guess_budget_blocks_even_a_correct_code_after_failures(self):
        from auth_rate_limit import AuthenticationRateLimitExceeded, LOGIN_PAIR_FAILURE_LIMIT
        conn=self.connect()
        with conn.cursor() as cur:
            cur.execute('INSERT INTO root_authenticators(user_id,secret_ciphertext) VALUES(1,%s)',(seal(SECRET,1,self.app.config['SECRET_KEY']),))
        conn.commit();conn.close()
        for index in range(LOGIN_PAIR_FAILURE_LIMIT+1):
            connection=self.connect()
            try:
                with connection.cursor() as cur:
                    cur.execute('SELECT EXTRACT(EPOCH FROM clock_timestamp()) AS now')
                    step=int(cur.fetchone()['now'])//30
                    valid={hotp(SECRET,step+offset) for offset in (-1,0,1)}
                    wrong=next(f'{value:06d}' for value in range(10) if f'{value:06d}' not in valid)
                    if index<LOGIN_PAIR_FAILURE_LIMIT:self.assertFalse(authenticate(cur,ROOT,wrong,self.app.config['SECRET_KEY']))
                    else:
                        with self.assertRaises(AuthenticationRateLimitExceeded):authenticate(cur,ROOT,wrong,self.app.config['SECRET_KEY'])
                connection.commit()
            finally:connection.close()
        connection=self.connect()
        try:
            with connection.cursor() as cur:
                with self.assertRaises(AuthenticationRateLimitExceeded):authenticate(cur,ROOT,hotp(SECRET,step),self.app.config['SECRET_KEY'])
        finally:connection.close()
        self.assertEqual(self.row()['last_counter'],-1)


class RootLoginIntegrationTests(unittest.TestCase):
    def test_authenticator_management_is_never_a_public_login_endpoint(self):
        import app as core
        self.assertFalse(core.is_public_api_path('/api/auth/root-authenticator'))
        self.assertTrue(core.is_public_api_path('/api/login'))

    def test_login_method_password_policy_failure_and_rate_limit_compatibility(self):
        import app as core
        from auth_rate_limit import AuthenticationRateLimitExceeded
        cases=[(ROOT,True,False,1,200,'totp'),(ROOT,False,True,1,403,None),
            (ROOT,False,True,0,409,None),(ROOT,False,False,1,401,None),
            ({**ROOT,'role':'station_manager'},False,True,0,200,'password')]
        for user,totp,password,keys,status,method in cases:
            conn=MagicMock();conn.cursor.return_value.fetchone.return_value=user
            with self.subTest(status=status,method=method),core.app.test_request_context('/api/login',json={'username':user['username'],'password':'123456'}),patch.multiple(core,
                get_db_connection=MagicMock(return_value=conn),ensure_user_security_schema=MagicMock(),
                check_password_login_allowed=MagicMock(),authenticate_root_totp=MagicMock(return_value=totp),
                verify_user_password=MagicMock(return_value=password),count_user_passkeys=MagicMock(return_value=keys),
                record_password_login_failure=MagicMock(),clear_successful_password_login=MagicMock(),
                record_security_event=MagicMock(),touch_online_user_presence=MagicMock(),
                build_auth_user_payload=MagicMock(side_effect=lambda cur,u,m:{'authentication_method':m}),
                build_authenticated_response=lambda payload,token:jsonify(payload)):
                result=core.login();response=result[0] if isinstance(result,tuple) else result
                self.assertEqual(result[1] if isinstance(result,tuple) else response.status_code,status)
                if method:
                    self.assertEqual(response.json['user']['authentication_method'],method)
                    token=core.get_auth_serializer().loads(response.json['token'])
                    self.assertEqual(token['amr'],method)
                else:self.assertNotIn('token',response.json)
        conn=MagicMock();conn.cursor.return_value.fetchone.return_value=ROOT
        with core.app.test_request_context('/api/login',json={'username':'root','password':'123456'}),patch.multiple(core,
            get_db_connection=MagicMock(return_value=conn),ensure_user_security_schema=MagicMock(),
            check_password_login_allowed=MagicMock(),authenticate_root_totp=MagicMock(side_effect=AuthenticationRateLimitExceeded(60,'login_pair'))):
            response=core.login()
            self.assertEqual(response.status_code,429);self.assertEqual(response.headers['Retry-After'],'60')
