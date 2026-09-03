"""Shared, last-saved report settings and append-only generation request history."""

from datetime import timedelta

from psycopg2.extras import Json


DATE_OPTION_KEYS = (
    "date_from", "date_to", "non_oil_rectification_date_from", "non_oil_rectification_date_to",
)


def _time(value):
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else ""


def get_report_workspace(cur, report_type):
    cur.execute("""
        SELECT report_type, generation_options, revision, updated_by_name, updated_at
        FROM inspection_report_workspaces WHERE report_type = %s
    """, (report_type,))
    row = cur.fetchone() or {}
    return {
        "generation_options": row.get("generation_options") or {},
        "revision": int(row.get("revision") or 0),
        "updated_by_name": row.get("updated_by_name") or "",
        "updated_at": _time(row.get("updated_at")),
    }


def save_report_workspace(cur, report_type, user, options=None):
    """An omitted options argument marks a saved classification/selection change."""
    dates = {key: options[key] for key in DATE_OPTION_KEYS if options.get(key)} if options is not None else {}
    cur.execute("""
        INSERT INTO inspection_report_workspaces
            (report_type, generation_options, revision, updated_by, updated_by_name)
        VALUES (%s, %s, 1, %s, %s)
        ON CONFLICT (report_type) DO UPDATE SET
            generation_options = CASE WHEN %s THEN EXCLUDED.generation_options
                ELSE inspection_report_workspaces.generation_options END,
            revision = inspection_report_workspaces.revision + 1,
            updated_by = EXCLUDED.updated_by,
            updated_by_name = EXCLUDED.updated_by_name,
            updated_at = CURRENT_TIMESTAMP
        WHERE NOT %s OR inspection_report_workspaces.generation_options IS DISTINCT FROM EXCLUDED.generation_options
    """, (
        report_type, Json(dates), user.get("id"), user.get("real_name") or user.get("username") or "",
        options is not None, options is not None,
    ))
    return get_report_workspace(cur, report_type)


def list_report_generation_requests(cur, report_type, limit=100):
    cur.execute("""
        SELECT task_id, requested_by_name, created_at, status, period_start, period_end_exclusive
        FROM inspection_report_jobs
        WHERE report_type = %s
        ORDER BY created_at DESC, task_id DESC LIMIT %s
    """, (report_type, max(1, min(500, int(limit)))))
    return [{
        "task_id": row["task_id"],
        "requested_by_name": row.get("requested_by_name") or "历史用户",
        "requested_at": _time(row.get("created_at")),
        "status": row.get("status") or "queued",
        "date_from": row["period_start"].isoformat(),
        "date_to": (row["period_end_exclusive"] - timedelta(days=1)).isoformat(),
    } for row in cur.fetchall()]
