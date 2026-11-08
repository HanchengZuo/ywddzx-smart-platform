"""Scoped certificate registration, ledger, reminders and private historical images."""

from datetime import date
from pathlib import Path
from io import BytesIO
from uuid import uuid4
import warnings
from PIL import Image, ImageOps
from flask import Blueprint, g, jsonify, request, send_file
from area_roles import AREA_ROLES


def scope(user, permissions, regions, operation="view", alias="s"):
    key = (
        "register_all_certificates"
        if operation == "register"
        else "view_all_certificates"
    )
    if user["role"] == "root" or permissions.get(key):
        return "TRUE", [], "all"
    if user["role"] == "station_manager" and user.get("station_id"):
        return f"{alias}.id=%s", [user["station_id"]], "station"
    if user["role"] in AREA_ROLES and regions:
        return (
            f"COALESCE(NULLIF(TRIM({alias}.region),''),'未填写片区')=ANY(%s)",
            [sorted(regions)],
            "region",
        )
    return "FALSE", [], "none"


def base_query(user, permissions, regions, types, operation="view"):
    where, params, _ = scope(user, permissions, regions, operation)
    recommended = (
        "CASE c.certificate_type "
        + " ".join("WHEN %s THEN %s" for _ in types)
        + " ELSE 30 END"
    )
    legal = (
        "CASE c.certificate_type "
        + " ".join("WHEN %s THEN %s" for _ in types)
        + " ELSE 7 END"
    )
    rules = [
        v for item in types for v in (item["code"], item["recommended_reminder_days"])
    ] + [v for item in types for v in (item["code"], item["legal_reminder_days"])]
    sql = f"""WITH b AS (SELECT c.*,s.station_name,s.region,
        c.expiry_date-(CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai')::date AS days_remaining,
        CASE WHEN NOT c.is_present THEN 'absent' WHEN c.expiry_date IS NULL THEN 'undated'
        WHEN c.expiry_date<(CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai')::date THEN 'expired'
        WHEN c.expiry_date-(CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai')::date<=({recommended}) THEN
            CASE WHEN c.expiry_date-(CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai')::date<=({legal}) THEN 'legal' ELSE 'recommended' END
        ELSE 'normal' END AS status
        FROM station_certificates c JOIN stations s ON s.id=c.station_id WHERE {where}),
        q AS (SELECT b.*, (r.user_id IS NULL AND b.status IN ('recommended','legal','expired')) AS unread,
        (SELECT id FROM station_certificate_history h WHERE h.certificate_id=b.id AND h.revision=b.revision) AS history_id
        FROM b LEFT JOIN station_certificate_reminder_reads r ON r.certificate_id=b.id AND r.revision=b.revision
        AND r.status=b.status AND r.user_id=%s) """
    return sql, [*rules, *params, user["id"]]


def unread_count(cur, user, permissions, regions, types):
    if scope(user, permissions, regions)[2] == "none":
        return 0
    query, params = base_query(user, permissions, regions, types)
    cur.execute(query + "SELECT count(*) AS n FROM q WHERE unread", params)
    return cur.fetchone()["n"]


def save_image(upload, root):
    raw = upload.read(25 * 1024 * 1024 + 1)
    if not raw or len(raw) > 25 * 1024 * 1024:
        raise ValueError("证照图片不能为空且不能超过25MB。")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as source:
                if source.width * source.height > 60000000:
                    raise ValueError("图片分辨率过高，请压缩后重试。")
                image = ImageOps.exif_transpose(source).convert("RGB")
                path = Path(root) / "certificate_documents" / f"{uuid4().hex}.jpg"
                path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    image.save(path, "JPEG", quality=92)
                except Exception:
                    path.unlink(missing_ok=True)
                    raise
                return str(path.relative_to(root))
    except (
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ValueError("请上传有效的证照图片。") from exc


def record_json(row):
    value = dict(row)
    for key in ("start_date", "expiry_date", "created_at", "updated_at", "read_at"):
        if value.get(key) is not None:
            value[key] = (
                value[key].isoformat(sep=" ")
                if hasattr(value[key], "hour")
                else value[key].isoformat()
            )
    value.pop("photo_path", None)
    if row.get("photo_path") and row.get("history_id"):
        value["photo_url"] = (
            f"/storage/certificates/{row['id']}/{row['history_id']}.jpg"
        )
    else:
        value["photo_url"] = ""
    return value


def register_certificates(
    app, *, connect, permissions, regions, types, storage_root, file_user
):
    bp = Blueprint("certificates", __name__)
    by_code = {item["code"]: item for item in types}

    def identity(cur):
        user = getattr(g, "current_user", None)
        if not user:
            raise PermissionError("请先登录。")
        return user, permissions(cur, user), regions(cur, user)

    def run(fn, new_files=()):
        conn = connect()
        success = False
        try:
            result = fn(conn, conn.cursor())
            conn.commit()
            success = True
            return result
        except PermissionError as exc:
            conn.rollback()
            return jsonify(error=str(exc)), 403
        except (ValueError, TypeError) as exc:
            conn.rollback()
            return jsonify(error=str(exc)), 400
        except Exception:
            conn.rollback()
            app.logger.exception("Certificate request failed")
            return jsonify(error="证照处理失败，请稍后重试。"), 500
        finally:
            conn.close()
            if not success:
                for path in new_files:
                    (Path(storage_root) / path).unlink(missing_ok=True)

    def check(cur, user, perms, area, station_id, operation="view"):
        where, params, _ = scope(user, perms, area, operation)
        cur.execute(
            f"SELECT s.id FROM stations s WHERE s.id=%s AND {where}",
            [station_id, *params],
        )
        if not cur.fetchone():
            raise PermissionError("当前账号无权访问此站点的证照。")

    @bp.get("/api/station-certificates/options")
    def options():
        def operation(conn, cur):
            user, perms, area = identity(cur)
            purpose = (
                "register" if request.args.get("purpose") == "register" else "view"
            )
            where, params, kind = scope(user, perms, area, purpose)
            cur.execute(
                f"SELECT s.id,s.station_name,s.region FROM stations s WHERE {where} ORDER BY s.region,s.station_name,s.id",
                params,
            )
            return jsonify(
                success=True,
                stations=cur.fetchall(),
                certificate_types=types,
                scope=kind,
                view_scope=scope(user, perms, area)[2],
                register_scope=scope(user, perms, area, "register")[2],
            )

        return run(operation)

    @bp.get("/api/station-certificates")
    def ledger():
        def operation(conn, cur):
            user, perms, area = identity(cur)
            if scope(user, perms, area)[2] == "none":
                raise PermissionError("当前账号没有查看证照数据权限。")
            query, params = base_query(user, perms, area, types)
            clauses = []
            values = []
            for field, column in [
                ("station_id", "station_id"),
                ("certificate_type", "certificate_type"),
                ("region", "region"),
                ("status", "status"),
            ]:
                if request.args.get(field):
                    clauses.append(f"{column}=%s")
                    values.append(request.args[field])
            keyword = request.args.get("keyword", "").strip()
            if len(keyword) > 200:
                raise ValueError("搜索关键词过长。")
            if keyword:
                clauses.append(
                    "(station_name ILIKE %s OR certificate_name ILIKE %s OR COALESCE(remark,'') ILIKE %s)"
                )
                values.extend(["%" + keyword + "%"] * 3)
            if request.args.get("mode") == "reminders":
                clauses.append("status IN ('recommended','legal','expired')")
            if request.args.get("unread") == "true":
                clauses.append("unread")
            where = " WHERE " + " AND ".join(clauses) if clauses else ""
            page = max(1, int(request.args.get("page", 1)))
            size = min(100, max(1, int(request.args.get("page_size", 20))))
            cur.execute(
                query + "SELECT count(*) AS total FROM q" + where, params + values
            )
            total = cur.fetchone()["total"]
            cur.execute(
                query
                + "SELECT * FROM q"
                + where
                + " ORDER BY expiry_date ASC NULLS LAST,station_name,id LIMIT %s OFFSET %s",
                params + values + [size, (page - 1) * size],
            )
            rows = [record_json(row) for row in cur.fetchall()]
            cur.execute(
                query
                + """SELECT count(*) AS total,count(*) FILTER(WHERE status='absent') AS absent,
                count(*) FILTER(WHERE status IN ('recommended','legal','expired')) AS due,count(*) FILTER(WHERE status='expired') AS expired,
                count(*) FILTER(WHERE unread) AS unread FROM q""",
                params,
            )
            summary = cur.fetchone()
            cur.execute(
                query
                + """SELECT certificate_type,count(*) AS recorded,count(*) FILTER(WHERE status='absent') AS absent,
                count(*) FILTER(WHERE status IN ('recommended','legal','expired')) AS due FROM q GROUP BY certificate_type""",
                params,
            )
            return jsonify(
                success=True,
                records=rows,
                total=total,
                page=page,
                page_size=size,
                summary=summary,
                type_summary=cur.fetchall(),
            )

        return run(operation)

    @bp.get("/api/station-certificates/current")
    def current():
        def operation(conn, cur):
            user, perms, area = identity(cur)
            station = int(request.args.get("station_id", 0))
            check(cur, user, perms, area, station, "register")
            cur.execute(
                "SELECT revision,is_present,start_date,expiry_date,remark FROM station_certificates WHERE station_id=%s AND certificate_type=%s",
                (station, request.args.get("certificate_type", "")),
            )
            row = cur.fetchone()
            return jsonify(success=True, record=record_json(row) if row else None)

        return run(operation)

    @bp.post("/api/station-certificates")
    def register():
        new_files = []

        def operation(conn, cur):
            user, perms, area = identity(cur)
            data = (
                (request.get_json(silent=True) or {})
                if request.is_json
                else request.form
            )
            station = int(data.get("station_id", 0))
            code = data.get("certificate_type")
            present = data.get("is_present", "true")
            if present not in (True, False, "true", "false"):
                raise ValueError("请选择是否拥有此证照。")
            present = present in (True, "true")
            remark = str(data.get("remark", "")).strip()
            if code not in by_code:
                raise ValueError("请选择有效的证照类型。")
            if len(remark) > 2000:
                raise ValueError("备注不能超过2000字。")
            start = (
                date.fromisoformat(data["start_date"])
                if present and data.get("start_date")
                else None
            )
            expiry = (
                date.fromisoformat(data["expiry_date"])
                if present and data.get("expiry_date")
                else None
            )
            if present and not expiry:
                raise ValueError("到期时间必须录入。")
            if start and start > expiry:
                raise ValueError("起始日期不能晚于到期时间。")
            check(cur, user, perms, area, station, "register")
            cur.execute("SELECT pg_advisory_xact_lock(125000,%s)", (station,))
            cur.execute(
                "SELECT id,revision FROM station_certificates WHERE station_id=%s AND certificate_type=%s FOR UPDATE",
                (station, code),
            )
            old = cur.fetchone()
            if int(data.get("revision", -1)) != (old["revision"] if old else 0):
                return (
                    jsonify(error="该证照已被其他用户更新，请重新读取后再登记。"),
                    409,
                )
            upload = request.files.get("photo")
            if present and (not upload or not upload.filename):
                raise ValueError("请上传证照图片。")
            path = None
            try:
                if present:
                    path = save_image(upload, Path(storage_root))
                    new_files.append(path)
                cur.execute(
                    """INSERT INTO station_certificates(station_id,certificate_type,certificate_name,is_present,start_date,expiry_date,
                    remark,photo_path,created_by,updated_by,revision) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)
                    ON CONFLICT(station_id,certificate_type) DO UPDATE SET is_present=EXCLUDED.is_present,start_date=EXCLUDED.start_date,
                    expiry_date=EXCLUDED.expiry_date,remark=EXCLUDED.remark,photo_path=EXCLUDED.photo_path,updated_by=EXCLUDED.updated_by,
                    updated_at=CURRENT_TIMESTAMP,revision=station_certificates.revision+1 RETURNING *""",
                    (
                        station,
                        code,
                        by_code[code]["name"],
                        present,
                        start,
                        expiry,
                        remark,
                        path,
                        user["id"],
                        user["id"],
                    ),
                )
                row = cur.fetchone()
                cur.execute(
                    """INSERT INTO station_certificate_history(certificate_id,revision,is_present,start_date,expiry_date,remark,photo_path,
                    actor_id,actor_name,action) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                    (
                        row["id"],
                        row["revision"],
                        present,
                        start,
                        expiry,
                        remark,
                        path,
                        user["id"],
                        user.get("real_name") or user.get("username") or "",
                        (
                            "登记无此证照"
                            if not present
                            else "更新证照" if old else "首次登记"
                        ),
                    ),
                )
                history_id = cur.fetchone()["id"]
                return jsonify(
                    success=True,
                    id=row["id"],
                    revision=row["revision"],
                    history_id=history_id,
                    message="证照已登记，历史版本已保留。",
                )
            except Exception:
                conn.rollback()
                if path:
                    (Path(storage_root) / path).unlink(missing_ok=True)
                raise

        return run(operation, new_files)

    @bp.get("/api/station-certificates/<int:identifier>/history")
    def history(identifier):
        def operation(conn, cur):
            user, perms, area = identity(cur)
            cur.execute(
                "SELECT station_id FROM station_certificates WHERE id=%s", (identifier,)
            )
            row = cur.fetchone()
            if not row:
                return jsonify(error="证照记录不存在。"), 404
            check(cur, user, perms, area, row["station_id"])
            cur.execute(
                "SELECT * FROM station_certificate_history WHERE certificate_id=%s ORDER BY revision DESC",
                (identifier,),
            )
            rows = []
            for item in cur.fetchall():
                value = record_json(item)
                value["photo_url"] = (
                    f"/storage/certificates/{identifier}/{item['id']}.jpg"
                    if item["photo_path"]
                    else ""
                )
                rows.append(value)
            return jsonify(success=True, records=rows)

        return run(operation)

    @bp.post("/api/station-certificates/<int:identifier>/read")
    def read(identifier):
        def operation(conn, cur):
            user, perms, area = identity(cur)
            query, params = base_query(user, perms, area, types)
            cur.execute(query + "SELECT * FROM q WHERE id=%s", params + [identifier])
            row = cur.fetchone()
            if not row:
                raise PermissionError("当前账号无权查看此提醒。")
            data = request.get_json(silent=True) or {}
            if row["revision"] != data.get("revision") or row["status"] != data.get(
                "status"
            ):
                return jsonify(error="证照状态已更新，请重新读取。"), 409
            if row["status"] in ("recommended", "legal", "expired"):
                cur.execute(
                    "INSERT INTO station_certificate_reminder_reads(user_id,certificate_id,revision,status) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    (user["id"], identifier, row["revision"], row["status"]),
                )
            return jsonify(success=True)

        return run(operation)

    @bp.get("/storage/certificates/<int:identifier>/<int:history_id>.jpg")
    def image(identifier, history_id):
        def operation(conn, cur):
            user = file_user()
            perms = permissions(cur, user)
            area = regions(cur, user)
            cur.execute(
                "SELECT station_id FROM station_certificates WHERE id=%s", (identifier,)
            )
            row = cur.fetchone()
            if not row:
                return jsonify(error="证照不存在。"), 404
            check(cur, user, perms, area, row["station_id"])
            cur.execute(
                "SELECT photo_path FROM station_certificate_history WHERE id=%s AND certificate_id=%s",
                (history_id, identifier),
            )
            item = cur.fetchone()
            if not item or not item["photo_path"]:
                return jsonify(error="证照图片不存在。"), 404
            root = (Path(storage_root) / "certificate_documents").resolve()
            path = (Path(storage_root) / item["photo_path"]).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                return jsonify(error="证照图片不存在。"), 404
            response = send_file(path, mimetype="image/jpeg", conditional=True)
            response.headers["Cache-Control"] = "private, no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response

        return run(operation)

    app.register_blueprint(bp)
