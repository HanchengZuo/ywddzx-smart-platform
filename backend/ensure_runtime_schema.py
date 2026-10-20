import os
import sys

import psycopg2


REPORT_JOB_COLUMNS = {
    "task_id",
    "report_type",
    "report_month",
    "scope_key",
    "requested_by",
    "status",
    "progress",
    "stage_message",
    "error_message",
    "created_at",
    "started_at",
    "finished_at",
    "updated_at",
}
SECURITY_USER_COLUMNS = {
    "password_hash",
    "must_change_password",
    "force_change_immediately",
    "password_changed_at",
    "password_policy_version",
    "password_risk_flags",
    "auth_version",
    "account_status",
}
SECURITY_TABLES = {
    "authentication_rate_limits",
    "password_security_policies",
    "user_passkeys",
    "user_password_history",
    "security_audit_logs",
    "webauthn_challenges",
}
SECURITY_POLICY_COLUMNS = {
    "require_uppercase",
    "require_lowercase",
    "require_number",
    "require_special",
}


def get_db_config():
    return {
        "host": os.environ.get("DB_HOST", "db"),
        "port": str(os.environ.get("DB_PORT", 5432)),
        "dbname": os.environ.get("DB_NAME", "ywddzx"),
        "user": os.environ.get("DB_USER", "postgres"),
        "password": os.environ.get("DB_PASSWORD", "postgres"),
    }


def ensure_inspection_report_jobs(cur):
    cur.execute("SELECT pg_advisory_xact_lock(%s);", (2026071402,))
    cur.execute("SELECT to_regclass('public.users');")
    if cur.fetchone()[0] is None:
        raise RuntimeError("required table public.users does not exist")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS public.inspection_report_jobs (
            task_id TEXT PRIMARY KEY,
            report_type TEXT NOT NULL,
            report_month TEXT NOT NULL,
            scope_key TEXT NOT NULL,
            requested_by INTEGER NOT NULL
                REFERENCES public.users(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'queued',
            progress SMALLINT NOT NULL DEFAULT 0,
            stage_message TEXT NOT NULL DEFAULT '等待后台处理',
            error_message TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP WITHOUT TIME ZONE,
            finished_at TIMESTAMP WITHOUT TIME ZONE,
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT ck_inspection_report_jobs_status
                CHECK (status IN ('queued', 'running', 'completed', 'failed')),
            CONSTRAINT ck_inspection_report_jobs_progress
                CHECK (progress >= 0 AND progress <= 100)
        );
        """
    )
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_inspection_report_jobs_active_scope
        ON public.inspection_report_jobs (report_type, report_month, scope_key)
        WHERE status IN ('queued', 'running');
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_inspection_report_jobs_user_updated
        ON public.inspection_report_jobs (requested_by, updated_at);
        """
    )


def verify_inspection_report_jobs(cur):
    cur.execute("SELECT to_regclass('public.inspection_report_jobs');")
    if cur.fetchone()[0] is None:
        raise RuntimeError("public.inspection_report_jobs is still missing")

    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'inspection_report_jobs';
        """
    )
    actual_columns = {row[0] for row in cur.fetchall()}
    missing_columns = sorted(REPORT_JOB_COLUMNS - actual_columns)
    if missing_columns:
        raise RuntimeError(
            "public.inspection_report_jobs is incomplete; missing columns: "
            + ", ".join(missing_columns)
        )


def verify_expert_qa_schema(cur):
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='expert_qa_questions'")
    columns = {row[0] for row in cur.fetchall()}
    required = {'id', 'user_id', 'session_key', 'question', 'options', 'status', 'result',
                'error_message', 'cache_key', 'created_at', 'updated_at'}
    missing = sorted(required - columns)
    if missing:
        raise RuntimeError('public.expert_qa_questions columns missing: ' + ', '.join(missing))


def get_alembic_version(cur):
    cur.execute("SELECT to_regclass('public.alembic_version');")
    if cur.fetchone()[0] is None:
        return "missing"
    cur.execute("SELECT version_num FROM public.alembic_version LIMIT 1;")
    row = cur.fetchone()
    return row[0] if row else "empty"


def verify_account_security_schema(cur):
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'users';
        """
    )
    user_columns = {row[0] for row in cur.fetchall()}
    missing_columns = sorted(SECURITY_USER_COLUMNS - user_columns)
    if missing_columns:
        raise RuntimeError("public.users security columns missing: " + ", ".join(missing_columns))
    for table_name in sorted(SECURITY_TABLES):
        cur.execute("SELECT to_regclass(%s);", (f"public.{table_name}",))
        if cur.fetchone()[0] is None:
            raise RuntimeError(f"required security table public.{table_name} does not exist")
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'password_security_policies';
        """
    )
    policy_columns = {row[0] for row in cur.fetchall()}
    missing_policy_columns = sorted(SECURITY_POLICY_COLUMNS - policy_columns)
    if missing_policy_columns:
        raise RuntimeError(
            "public.password_security_policies columns missing: "
            + ", ".join(missing_policy_columns)
        )
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'users'
          AND column_name = 'password'
        LIMIT 1;
        """
    )
    if cur.fetchone():
        raise RuntimeError("legacy plaintext credential column public.users.password still exists")


def verify_quality_deadline_schema(cur):
    for table in ('quality_deadline_policy','quality_deadline_events','quality_deadline_worker_state','quality_work_calendar'):
        cur.execute('SELECT to_regclass(%s)', (table,))
        if cur.fetchone()[0] is None:
            raise RuntimeError(f'Quality deadline migration missing: {table}')
    for table, column in (('inspections','quality_accept_deadline_at'),('issues','quality_appeal_deadline_at'),('inspection_issue_appeals','review_phase'),('inspection_issue_appeals','quality_timeout_at'),('quality_deadline_policy','quality_review_hours'),('quality_deadline_policy','area_review_hours'),('quality_deadline_worker_state','next_scan_at')):
        cur.execute('SELECT 1 FROM information_schema.columns WHERE table_schema=\'public\' AND table_name=%s AND column_name=%s', (table,column))
        if not cur.fetchone():
            raise RuntimeError(f'Quality deadline column missing: {table}.{column}')


def main():
    config = get_db_config()
    target = (
        f"{config['host']}:{config['port']}/{config['dbname']} "
        f"as {config['user']}"
    )
    print(f"Verifying runtime database schema at {target} ...", flush=True)

    conn = None
    try:
        conn = psycopg2.connect(**config)
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT current_database(), current_schema(), current_user;"
                )
                database_name, schema_name, database_user = cur.fetchone()
                alembic_version = get_alembic_version(cur)
                ensure_inspection_report_jobs(cur)
                verify_inspection_report_jobs(cur)
                verify_account_security_schema(cur)
                verify_quality_deadline_schema(cur)
                verify_expert_qa_schema(cur)
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='stations' AND is_nullable='NO' AND data_type='boolean'")
                if not {'include_offline_plan', 'include_online_plan'}.issubset({row[0] for row in cur.fetchall()}):
                    raise RuntimeError('Station plan enrollment migration missing')
                for table, required in (
                    ('inspection_schedule_cells', {'mode', 'year', 'period_number', 'station_id', 'column_key', 'inspector_ids', 'revision', 'updated_by', 'updated_at', 'scheduled_date'}),
                    ('inspection_schedule_events', {'station_id', 'before_ids', 'after_ids', 'actor_id', 'actor_name', 'created_at'}),
                    ('staff_availability', {'person_name', 'day', 'available', 'reason', 'revision', 'updated_by', 'history_status'}),
                    ('staff_daily_teams', {'day', 'assignments', 'revision', 'updated_by'}),
                    ('staff_daily_team_events', {'day', 'before_value', 'after_value', 'actor_id'}),
                    ('staff_availability_events', {'before_value', 'after_value', 'actor_id'}),
                    ('inspection_schedule_tasks', {'user_id', 'scheduled_date', 'team_ids', 'status', 'completion_inspection_id'}),
                ):
                    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s", (table,))
                    if not required.issubset({row[0] for row in cur.fetchall()}):
                        raise RuntimeError(f'Inspection schedule migration missing: {table}')
        print(
            "Runtime schema ready: "
            f"database={database_name}, schema={schema_name}, "
            f"user={database_user}, alembic={alembic_version}, "
            "inspection_report_jobs=ready, account_security=ready",
            flush=True,
        )
    except Exception as exc:
        print(
            f"Runtime schema verification failed at {target}: {exc}",
            file=sys.stderr,
            flush=True,
        )
        raise
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    main()
