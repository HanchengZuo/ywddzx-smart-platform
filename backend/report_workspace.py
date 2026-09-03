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
        SELECT report_type, generation_options, revision, updated_by_name, updated_at, section_meta
        FROM inspection_report_workspaces WHERE report_type = %s
    """, (report_type,))
    row = cur.fetchone() or {}
    return {
        "generation_options": row.get("generation_options") or {},
        "revision": int(row.get("revision") or 0),
        "updated_by_name": row.get("updated_by_name") or "",
        "updated_at": _time(row.get("updated_at")),
        "section_meta": row.get("section_meta") or {},
    }


def save_report_workspace(cur, report_type, user, options=None, section=None):
    """An omitted options argument marks a saved classification/selection change."""
    dates = {key: options[key] for key in DATE_OPTION_KEYS if options.get(key)} if options is not None else {}
    before = get_report_workspace(cur, report_type)
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
    sections = [section] if section else []
    if options is not None:
        previous = before["generation_options"]
        for name, keys in (("date_range", DATE_OPTION_KEYS[:2]), ("rectification", DATE_OPTION_KEYS[2:])):
            if any(previous.get(key) != dates.get(key) for key in keys):
                sections.append(name)
    for name in sections:
        cur.execute("""
            UPDATE inspection_report_workspaces SET section_meta = section_meta || jsonb_build_object(
                %s::text, jsonb_build_object('updated_by_name', %s::text,
                    'updated_at', TO_CHAR(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'))
            ) WHERE report_type = %s
        """, (name, user.get("real_name") or user.get("username") or "", report_type))
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
