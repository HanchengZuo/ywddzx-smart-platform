"""Opt-in disposable PostgreSQL checks; no production connections or paid AI calls."""
import os
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from flask import Flask
from psycopg2.extras import RealDictCursor
import psycopg2
from psycopg2.extensions import parse_dsn

from expert_qa import register_expert_qa
from expert_knowledge import retrieve
from expert_query import infer_options


@unittest.skipUnless(os.environ.get('EXPERT_QA_TEST_DSN'), 'requires an isolated test PostgreSQL database')
class ExpertDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ['EXPERT_QA_TEST_DSN']
        if not parse_dsn(cls.dsn).get('dbname', '').startswith('test_'):
            raise RuntimeError('Only disposable test_ databases are permitted')
        cls.schema = 'expert_test_' + uuid.uuid4().hex
        with psycopg2.connect(cls.dsn) as conn, conn.cursor() as cur:
            cur.execute('CREATE SCHEMA ' + cls.schema)

    @classmethod
    def tearDownClass(cls):
        with psycopg2.connect(cls.dsn) as conn, conn.cursor() as cur:
            cur.execute('DROP SCHEMA ' + cls.schema + ' CASCADE')

    def connect(self):
        return psycopg2.connect(self.dsn, options='-c search_path=' + self.schema, cursor_factory=RealDictCursor)

    def setUp(self):
        route_loader = patch('ai_routing._loader', None)
        route_loader.start()
        self.addCleanup(route_loader.stop)
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute('''CREATE TABLE IF NOT EXISTS expert_qa_questions(
                id VARCHAR(32) PRIMARY KEY,user_id INTEGER,session_key TEXT,question TEXT,
                options JSONB DEFAULT '{}',status TEXT,result JSONB,error_message TEXT DEFAULT '',cache_key TEXT,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP);
                TRUNCATE expert_qa_questions''')
        self.user = {'id': 17, 'role': 'area_account', 'auth_version': 1, 'account_status': 'active'}
        def close(cur, conn):
            cur.close()
            conn.close()
        self.core = dict(get_db_connection=self.connect, get_current_request_user=lambda: dict(self.user),
            has_permission=MagicMock(return_value=True), close_db_resources=close,
            fetch_auth_user_by_id=lambda cur, user_id: dict(self.user), is_password_change_enforced=lambda *args: False,
            fetch_password_policy=lambda cur: {}, record_ai_usage_log=MagicMock(), BEIJING_TZ=ZoneInfo('Asia/Shanghai'))
        self.app = Flask(__name__)
        register_expert_qa(self.app, self.core)
        self.client = self.app.test_client()

    def send_and_finish(self, question, parent=''):
        answer = {'paragraphs': [{'text': '有据回答', 'sources': ['S1']}], 'caveat': '', 'follow_up_questions': []}
        evidence = [{'id': 'S1', 'key': 'workflow:1', 'title': '说明', 'kind': '系统流程说明', 'text': '规范要求'}]
        with patch('expert_qa.executor.submit') as execute, patch('expert_qa.retrieve', return_value=(evidence, {'options': infer_options(question)})), \
             patch('expert_qa.get_deepseek_client', return_value=MagicMock()), \
             patch('expert_qa.generate', return_value=(answer, {'ai_called': True, 'success': True})) as generate:
            response = self.client.post('/api/operations/expert/questions', json={'question': question, 'parent_id': parent,
                'date_from': '2020-01-01', 'date_to': '2020-01-02', 'region': '不应继承的隐藏筛选'})
            self.assertEqual(response.status_code, 202, response.json)
            callback, *args = execute.call_args.args
            callback(*args)
            self.assertEqual(self.client.get('/api/operations/expert/questions/' + response.json['id']).json['item']['status'], 'completed')
            return response.json['id'], generate.call_args.args[2]

    def test_global_default_thread_history_and_multiple_rounds(self):
        first, _ = self.send_and_finish('铅封有什么规定')
        second, previous = self.send_and_finish('这些要求怎么落实', first)
        self.assertEqual(len(previous['turns']), 1)
        third, previous = self.send_and_finish('再解释一下站点要做什么', second)
        self.assertEqual(len(previous['turns']), 2)
        summary = self.client.get('/api/operations/expert/questions?summary=1').json['items']
        self.assertEqual(len(summary), 3)
        self.assertTrue(all('result' not in row for row in summary))
        thread = self.client.get('/api/operations/expert/questions?conversation_id=' + first).json['items']
        self.assertEqual({row['id'] for row in thread}, {first, second, third})
        self.assertTrue(all(row['options']['conversation_id'] == first for row in thread))
        self.assertTrue(all(row['options']['date_from'] == '' and row['options']['region'] == '' for row in thread))

    def test_foreign_parent_and_conversation_do_not_leak_other_users_history(self):
        first, _ = self.send_and_finish('复核照片有哪些要求')
        self.user['id'] = 18
        self.assertEqual(self.client.get('/api/operations/expert/questions?conversation_id=' + first).json['items'], [])
        with patch('expert_qa.executor.submit') as execute:
            response = self.client.post('/api/operations/expert/questions', json={'question': '补充解释', 'parent_id': first})
        self.assertEqual(response.status_code, 400)
        execute.assert_not_called()

    def test_retrieval_sql_executes_with_global_and_recognized_conditions(self):
        # Only columns from the explicit read-only evidence queries, no real business data.
        tables = {
            'stations': 'id int,station_name text,region text,address text,station_type text,asset_type text,status text,station_manager_name text',
            'inspection_tables': 'id int,table_name text,is_active boolean',
            'inspections': 'id int,station_id int,inspection_table_id int,inspection_date date,sign_status text,inspector_completion_status text,quality_accept_source text',
            'issues': 'id int,inspection_id int,station_id int,inspection_table_id int,created_at timestamptz,description text,standard_id text,standard_detail_text text,audit_status text,status text,rectification_result text,rectification_note text,review_result text,review_note text',
            'inspection_issue_flow_history': 'id int,issue_id int,action_type text,from_status text,to_status text,result text,note text,actor_name text,actor_role text,created_at timestamptz',
            'inspection_issue_appeals': 'id int,issue_id int,status text,reason text,area_reason text,quality_reason text,updated_at timestamptz',
            'inspection_highlights': 'id int,station_id int,inspection_table_id int,created_at timestamptz,description text,audit_status text',
            'inspection_plan_configs': 'id int,period_key text,coverage_type text,inspection_table_id int',
            'inspection_plan_station_items': 'id int,plan_config_id int,station_id int,completion_status text,note text,is_included boolean',
            'station_certificates': 'id int,station_id int,certificate_name text,certificate_type text,expiry_date date,remark text',
            'station_score_adjustments': 'id int,station_id int,inspection_table_id int,score_month date,standard_id text,manual_score numeric,note text',
            'system_feedbacks': 'id int,title text,module text,description text,feedback_type text,created_at timestamptz',
            'users': 'id int,real_name text,role text',
            'peer_review_tasks': 'id int,title text,description text,deadline_at timestamptz,status text',
            'ai_usage_logs': 'usage_module text,ai_called boolean,total_tokens_est numeric,total_cost_est numeric,created_at timestamptz',
            'inspection_internal_standards': 'internal_standard_id text,content text,field_values jsonb,notes text,is_active boolean',
            'inspection_table_original_files': 'id int,inspection_table_id int,file_path text',
            'training_materials': 'id int,title text,original_filename text,file_path text,updated_at timestamptz',
            'inspection_report_snapshots': 'id int,report_type text,report_month date,report_payload jsonb,generated_at timestamptz',
        }
        with self.connect() as conn, conn.cursor() as cur:
            for table, fields in tables.items():
                cur.execute('CREATE TABLE IF NOT EXISTS ' + table + '(' + fields + ')')
                cur.execute('TRUNCATE ' + table)
            cur.execute("INSERT INTO stations(id,station_name,region) VALUES(1,'国郃','浦东管理片区'),(2,'金山第二','松金管理片区')")
            cur.execute("INSERT INTO inspection_tables VALUES(1,'非油检查表（现场）',TRUE),(2,'加油站设备设施检查表（现场）',TRUE)")
            cur.execute("INSERT INTO inspections(id,station_id,inspection_table_id,inspection_date) VALUES(1,1,1,'2025-01-01'),(2,2,2,'2026-07-01'),(3,1,1,'2026-07-01')")
            cur.execute("INSERT INTO issues(id,inspection_id,station_id,inspection_table_id,created_at,description,audit_status) VALUES(6597,1,1,1,'2025-01-01','铅封异常','pending'),(7000,2,2,2,'2026-07-01','接地锈蚀','approved'),(7001,3,1,1,'2026-07-01','商品过期','approved')")
            cur.execute("INSERT INTO inspection_highlights VALUES(1,1,1,'2026-07-01','货架整齐','approved'),(2,2,2,'2026-07-01','接地维护','approved')")
        core = SimpleNamespace(STORAGE_ROOT='/nonexistent-test-storage', disabled_standard_ids=lambda cur: set(), fetch_external_standard_map=lambda cur: {})
        with self.connect() as conn, conn.cursor() as cur:
            evidence, info = retrieve(core, cur, '系统问题总数是多少', infer_options('系统问题总数是多少'))
            total = next(row for row in evidence if row['key'] == 'stats:issues')
            self.assertIn('"registered": 3', total['text'])
            self.assertEqual(info['options']['date_from'], '')
            evidence, info = retrieve(core, cur, '2026年7月非油问题总数是多少', infer_options('2026年7月非油问题总数是多少'))
            self.assertIn('"registered": 1', next(row for row in evidence if row['key'] == 'stats:issues')['text'])
            self.assertIn('"registered": 1', next(row for row in evidence if row['key'] == 'stats:highlights')['text'])
            evidence, info = retrieve(core, cur, '问题ID 6597 的处理过程', infer_options('问题ID 6597 的处理过程'))
            self.assertTrue(any(row['key'] == 'issue:6597' for row in evidence))
            evidence, info = retrieve(core, cur, '2026年7月计量申诉统计', infer_options('2026年7月计量申诉统计'))
            self.assertTrue(any(row['key'] == 'stats:appeals' for row in evidence))
            evidence, info = retrieve(core, cur, '国郃站点有几座', infer_options('国郃站点有几座'))
            self.assertIn('"stations": 1', next(row for row in evidence if row['key'] == 'stats:stations')['text'])
