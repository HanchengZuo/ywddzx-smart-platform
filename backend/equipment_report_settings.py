"""Report-only phrase overrides; never rewrite the underlying inspection evidence."""

from psycopg2.extras import Json

TABLE = "inspection_report_equipment_settings"


def load(cur):
    cur.execute(
        f"SELECT settings,revision,updated_by_name,updated_at FROM {TABLE} WHERE id=1"
    )
    row = cur.fetchone() or {}
    return dict(
        settings={
            "phrases": {},
            "station_overrides": {},
            **(row.get("settings") or {}),
        },
        revision=row.get("revision", 0),
        updated_by_name=row.get("updated_by_name", ""),
        updated_at=str(row.get("updated_at") or ""),
    )


def save(cur, settings, revision, user):
    cur.execute(f"""INSERT INTO {TABLE}(id) VALUES(1) ON CONFLICT DO NOTHING""")
    cur.execute(f"SELECT revision FROM {TABLE} WHERE id=1 FOR UPDATE")
    if cur.fetchone()["revision"] != revision:
        raise ValueError("配置已被其他用户更新，请重新读取后再保存。")
    cur.execute(
        f"""UPDATE {TABLE} SET settings=%s,revision=revision+1,updated_by=%s,
        updated_by_name=%s,updated_at=CURRENT_TIMESTAMP WHERE id=1""",
        (
            Json(settings),
            user["id"],
            user.get("real_name") or user.get("username") or "",
        ),
    )


def reference(cur, rows):
    from equipment_report_analysis import catalog

    defaults = catalog()
    result = {}
    for row in rows:
        key = str(row["external_standard_id"])
        fields = row["fields"]
        result[key] = dict(
            phrase=fields.get("检查内容短语")
            or defaults.get(key, {}).get("phrase")
            or "",
            cause=fields.get("问题产生原因")
            or defaults.get(key, {}).get("cause")
            or "参考表未提供原因",
            fields=fields,
        )
    if "9067" in result and not result["9067"]["phrase"]:
        result["9067"]["phrase"] = "非检查表类问题"
    settings = load(cur)["settings"]
    for key, phrase in settings["phrases"].items():
        if key in result:
            result[key]["phrase"] = phrase
    return result
