"""Read-only team inbox. A separate permission protects cross-account access."""
import logging

from flask import g, jsonify, request

from schedule_common import today
from schedule_task_progress import ALL_PEOPLE_PROGRESS_SQL, BUCKETS, SUMMARY_COLUMNS, inbox_page
from staff_availability import roster_people

VIEW = "view_schedule_task_overview"
COUNT_FIELDS = ("total", "pending", "completed", "exempted", "stations")
DETAIL_FIELDS = ("id", "station_id", "station_name", "mode", "scheduled_date", "table_name",
                 "column_key", "status", "last_inspection_date", "coverage_from", "coverage_to",
                 "exception_reason", "exception_reporter", "exception_reported_at")


def people_overview(cur, day):
    people = {
        p["id"]: {"id": p["id"], "name": p["display_name"], "position": p["position"], "buckets": {}}
        for p in roster_people(cur) if p["id"] is not None
    }
    cur.execute(ALL_PEOPLE_PROGRESS_SQL + f"""
        , counts AS (
          SELECT user_id,bucket,{SUMMARY_COLUMNS} FROM visible GROUP BY user_id,bucket
        )
        SELECT c.*,COALESCE(NULLIF(TRIM(u.real_name),''),u.username) AS name
        FROM counts c JOIN users u ON u.id=c.user_id
    """, (day, day, day))
    for row in cur.fetchall():
        person = people.setdefault(row["user_id"], {"id": row["user_id"], "name": row["name"],
                                                   "position": "", "buckets": {}})
        person["buckets"][row["bucket"]] = {key: row[key] for key in COUNT_FIELDS}
    return sorted(people.values(), key=lambda p: (p["name"], p["id"]))


def public_task(task):
    result = {key: task[key] for key in DETAIL_FIELDS}
    team = task.get("plan_team")
    if isinstance(team, dict):
        result["plan_team"] = {
            "name": team.get("name") or "",
            "members": [{"display_name": p.get("display_name") or ""} for p in team.get("members") or []],
        }
    return result


def register_schedule_task_overview(app, *, connect, has_permission):
    @app.get("/api/schedule-task-overview")
    @app.get("/api/schedule-task-overview/<int:user_id>")
    def schedule_task_overview(user_id=None):
        actor = getattr(g, "current_user", None)
        if not actor:
            return jsonify(success=False, error="请先登录。"), 401
        conn = cur = None
        try:
            conn = connect()
            # The platform connection sets the request actor before returning.
            conn.commit()
            cur = conn.cursor()
            cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            cur.execute("SET LOCAL statement_timeout='10s'")
            if not has_permission(cur, actor, VIEW):
                conn.commit()
                return jsonify(success=False, error="当前账号无权查看待办总览。"), 403
            day = today()
            if user_id is None:
                result = {"people": people_overview(cur, day)}
            else:
                try:
                    bucket = request.args.get("bucket", "all")
                    page = int(request.args.get("page", "1"))
                    page_size = int(request.args.get("page_size", "12"))
                    if bucket not in ("all", *BUCKETS) or not 1 <= user_id <= 2**31-1 or page < 1 or not 1 <= page_size <= 50:
                        raise ValueError
                except ValueError:
                    conn.commit()
                    return jsonify(success=False, error="待办分类或分页参数不合法。"), 400
                data = inbox_page(cur, user_id, day, bucket, page, page_size)
                result = {key: data[key] for key in ("page", "page_size", "total_groups", "has_more")}
                result["tasks"] = [public_task(task) for task in data["tasks"]]
            conn.commit()
            response = jsonify(success=True, today=day.isoformat(), **result)
            response.headers["Cache-Control"] = "private, no-store"
            return response
        except Exception:
            logging.exception("Schedule task overview failed")
            return jsonify(success=False, error="待办总览暂时无法读取，请稍后重试。"), 500
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
