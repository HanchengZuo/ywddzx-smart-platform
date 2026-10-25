import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import MagicMock

import psycopg2
from psycopg2.extensions import parse_dsn
from psycopg2.extras import RealDictCursor
from report_job_liveness import report_job_lease, expire_unowned_report_jobs, claim_report_job


class ReportJobLeaseTest(unittest.TestCase):
    def test_one_owner_across_processes_and_release_after_crash(self):
        with tempfile.TemporaryDirectory() as root:
            code = "from report_job_liveness import report_job_lease; import sys\nwith report_job_lease(sys.argv[1], 'job') as owned:\n print(owned,flush=True)\n sys.stdin.read()"
            child = subprocess.Popen([sys.executable, '-c', code, root], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, cwd=Path(__file__).resolve().parents[1])
            try:
                self.assertEqual(child.stdout.readline().strip(), 'True')
                with report_job_lease(root, 'job') as owned:
                    self.assertFalse(owned)
                child.kill()
                child.wait(timeout=5)
                with report_job_lease(root, 'job') as owned:
                    self.assertTrue(owned)
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=5)
                child.stdin.close()
                child.stdout.close()

    def test_live_owner_is_not_expired_and_reconciliation_never_calls_ai(self):
        with tempfile.TemporaryDirectory() as root, report_job_lease(root, 'live'):
            cur = MagicMock()
            cur.fetchall.return_value = [{'task_id': 'live'}]
            self.assertEqual(expire_unowned_report_jobs(cur, root, task_id='live'), 0)
            self.assertEqual(cur.execute.call_count, 1)


@unittest.skipUnless(os.environ.get('REPORT_AI_MEMORY_TEST_DSN'), 'requires isolated PostgreSQL DSN')
class ReportJobLivenessPostgresTest(unittest.TestCase):
    def test_orphan_expiry_live_long_ai_claim_and_rollback(self):
        dsn = os.environ['REPORT_AI_MEMORY_TEST_DSN']
        if not parse_dsn(dsn).get('dbname', '').startswith('test_'):
            raise RuntimeError('Refusing non-test database')
        schema = 'report_job_lease_' + uuid.uuid4().hex
        with tempfile.TemporaryDirectory() as root, psycopg2.connect(dsn, cursor_factory=RealDictCursor) as conn, conn.cursor() as cur:
            cur.execute(f'CREATE SCHEMA {schema}')
            cur.execute(f'SET LOCAL search_path = {schema}')
            cur.execute('''CREATE TABLE inspection_report_jobs (
                task_id TEXT PRIMARY KEY, report_type TEXT, status TEXT, progress INT,
                stage_message TEXT, error_message TEXT, started_at TIMESTAMP,
                finished_at TIMESTAMP, updated_at TIMESTAMP)''')
            for task, status, age in [('dead', 'running', '1 hour'), ('live', 'running', '1 hour'), ('queued', 'queued', '0 seconds'), ('done', 'completed', '1 hour')]:
                cur.execute("INSERT INTO inspection_report_jobs (task_id,report_type,status,progress,updated_at) VALUES (%s,'on_site_service',%s,52,CURRENT_TIMESTAMP-%s::interval)", (task, status, age))
            cur.execute('SAVEPOINT before_expiry')
            with report_job_lease(root, 'live'):
                self.assertEqual(expire_unowned_report_jobs(cur, root, report_type='on_site_service'), 1)
                cur.execute("SELECT status,progress,error_message FROM inspection_report_jobs WHERE task_id='dead'")
                dead = cur.fetchone()
                self.assertEqual(dead['status'], 'failed')
                self.assertEqual(dead['progress'], 52)
                self.assertIn('手动重新生成', dead['error_message'])
                cur.execute("SELECT status FROM inspection_report_jobs WHERE task_id='live'")
                self.assertEqual(cur.fetchone()['status'], 'running')
                self.assertIsNone(claim_report_job(cur, 'dead'))
            self.assertEqual(claim_report_job(cur, 'queued')['status'], 'running')
            self.assertIsNone(claim_report_job(cur, 'queued'))
            cur.execute('ROLLBACK TO before_expiry')
            cur.execute("SELECT status FROM inspection_report_jobs WHERE task_id='dead'")
            self.assertEqual(cur.fetchone()['status'], 'running')
            cur.execute(f'DROP SCHEMA {schema} CASCADE')
