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


def get_alembic_version(cur):
    cur.execute("SELECT to_regclass('public.alembic_version');")
    if cur.fetchone()[0] is None:
        return "missing"
    cur.execute("SELECT version_num FROM public.alembic_version LIMIT 1;")
    row = cur.fetchone()
    return row[0] if row else "empty"


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
        print(
            "Runtime schema ready: "
            f"database={database_name}, schema={schema_name}, "
            f"user={database_user}, alembic={alembic_version}, "
            "inspection_report_jobs=ready",
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
