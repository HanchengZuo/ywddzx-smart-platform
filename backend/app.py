from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os
import uuid
from datetime import date, datetime
from io import BytesIO
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.utils import secure_filename
from PIL import Image

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(__file__)
STORAGE_ROOT = os.path.join(BASE_DIR, "storage")
MAX_IMAGE_BYTES = 500 * 1024
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
ISSUES_STORAGE_DIR = os.path.join(STORAGE_ROOT, "issues")
RECTIFICATIONS_STORAGE_DIR = os.path.join(STORAGE_ROOT, "rectifications")

os.makedirs(ISSUES_STORAGE_DIR, exist_ok=True)
os.makedirs(RECTIFICATIONS_STORAGE_DIR, exist_ok=True)


def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        port=os.environ.get("DB_PORT", 5432),
        dbname=os.environ.get("DB_NAME", "ywddzx"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "postgres"),
        cursor_factory=RealDictCursor,
    )


def close_db_resources(cur=None, conn=None):
    if cur:
        cur.close()
    if conn:
        conn.close()


def ensure_storage_subdir(base_dir):
    now = datetime.now()
    year_dir = os.path.join(base_dir, now.strftime("%Y"))
    month_dir = os.path.join(year_dir, now.strftime("%m"))
    os.makedirs(month_dir, exist_ok=True)
    return month_dir, now


def save_uploaded_file(file_storage, category):
    if not file_storage or not file_storage.filename:
        return None

    if category == "issues":
        base_dir = ISSUES_STORAGE_DIR
        prefix = "issue"
    elif category == "rectifications":
        base_dir = RECTIFICATIONS_STORAGE_DIR
        prefix = "rectification"
    else:
        raise ValueError("不支持的上传分类。")

    original_name = secure_filename(file_storage.filename)
    ext = os.path.splitext(original_name)[1].lower()
    if ext and ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("仅支持上传 JPG、JPEG、PNG、WEBP、HEIC、HEIF 格式图片。")

    target_dir, now = ensure_storage_subdir(base_dir)
    filename = f"{prefix}_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex}.jpg"
    save_path = os.path.join(target_dir, filename)

    image_bytes = file_storage.read()
    if not image_bytes:
        raise ValueError("上传图片内容为空。")

    try:
        image = Image.open(BytesIO(image_bytes))
    except Exception as exc:
        raise ValueError("上传文件不是可识别的图片。") from exc

    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    elif image.mode == "L":
        image = image.convert("RGB")

    max_width = 1600
    if image.width > max_width:
        ratio = max_width / float(image.width)
        new_size = (max_width, max(1, int(image.height * ratio)))
        image = image.resize(new_size, Image.LANCZOS)

    quality = 82
    output = BytesIO()
    image.save(output, format="JPEG", quality=quality, optimize=True)

    while output.tell() > MAX_IMAGE_BYTES and quality > 42:
        quality -= 6
        output = BytesIO()
        image.save(output, format="JPEG", quality=quality, optimize=True)

    if output.tell() > MAX_IMAGE_BYTES:
        temp_image = image
        while output.tell() > MAX_IMAGE_BYTES and temp_image.width > 960:
            new_width = int(temp_image.width * 0.9)
            new_height = max(1, int(temp_image.height * 0.9))
            temp_image = temp_image.resize((new_width, new_height), Image.LANCZOS)
            output = BytesIO()
            temp_image.save(output, format="JPEG", quality=70, optimize=True)
        image = temp_image

    with open(save_path, "wb") as f:
        f.write(output.getvalue())

    relative_dir = os.path.relpath(target_dir, STORAGE_ROOT).replace("\\", "/")
    return f"/{relative_dir}/{filename}"


def get_or_create_inspection(cur, station_id, inspector_id):
    today = date.today()

    cur.execute(
        """
        INSERT INTO inspections (
            station_id,
            inspector_id,
            inspection_date
        )
        VALUES (%s, %s, %s)
        RETURNING id;
        """,
        (station_id, inspector_id, today),
    )
    new_row = cur.fetchone()
    return new_row["id"]


def get_category_record(cur, inspection_id, category_id):
    cur.execute(
        """
        SELECT id, result, summary
        FROM inspection_category_records
        WHERE inspection_id = %s AND category_id = %s
        LIMIT 1;
        """,
        (inspection_id, category_id),
    )
    return cur.fetchone()


def create_or_update_category_record(cur, inspection_id, category_id, result, summary):
    existing = get_category_record(cur, inspection_id, category_id)

    if existing:
        cur.execute(
            """
            UPDATE inspection_category_records
            SET result = %s,
                summary = %s
            WHERE id = %s
            RETURNING id;
            """,
            (result, summary, existing["id"]),
        )
        updated = cur.fetchone()
        return updated["id"]

    cur.execute(
        """
        INSERT INTO inspection_category_records (
            inspection_id,
            category_id,
            result,
            summary
        )
        VALUES (%s, %s, %s, %s)
        RETURNING id;
        """,
        (inspection_id, category_id, result, summary),
    )
    new_row = cur.fetchone()
    return new_row["id"]


@app.route("/api/inspection-categories")
def get_inspection_categories():
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id,
                name,
                sort_order
            FROM inspection_categories
            ORDER BY sort_order ASC, id ASC;
            """
        )
        rows = cur.fetchall()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/")
def home():
    return jsonify({"message": "业务督导中心数智管理平台后端运行中"})


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/db-test")
def db_test():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT current_database() AS db_name, version() AS version;")
        row = cur.fetchone()
        cur.close()
        conn.close()
        return jsonify(
            {
                "success": True,
                "database": row["db_name"],
                "version": row["version"],
            }
        )
    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                }
            ),
            500,
        )


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", "")).strip()

    if not username or not password:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "用户名和密码不能为空。",
                }
            ),
            400,
        )

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                u.id,
                u.username,
                u.role,
                u.real_name,
                u.phone,
                u.station_id,
                s.station_name,
                s.region,
                s.address
            FROM users u
            LEFT JOIN stations s ON u.station_id = s.id
            WHERE u.username = %s AND u.password = %s
            LIMIT 1;
        """,
            (username, password),
        )
        user = cur.fetchone()

        if not user:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "用户名或密码错误。",
                    }
                ),
                401,
            )

        return jsonify(
            {
                "success": True,
                "user": {
                    "id": user["id"],
                    "username": user["username"],
                    "role": user["role"],
                    "real_name": user["real_name"],
                    "phone": user["phone"],
                    "station_id": user["station_id"],
                    "station_name": user["station_name"],
                    "region": user["region"],
                    "address": user["address"],
                },
            }
        )
    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                }
            ),
            500,
        )
    finally:
        close_db_resources(cur, conn)


@app.route("/api/stations")
def get_stations():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id,
                station_name,
                region,
                address,
                longitude,
                latitude,
                station_manager_name,
                station_manager_phone,
                asset_type,
                status
            FROM stations
            ORDER BY id;
        """
        )
        rows = cur.fetchall()
        return jsonify(rows)
    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                }
            ),
            500,
        )
    finally:
        close_db_resources(cur, conn)


@app.route("/api/station-map")
def get_station_map():
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                s.id AS station_id,
                s.station_name,
                s.region,
                s.address,
                s.longitude,
                s.latitude,
                s.station_manager_name,
                s.station_manager_phone,
                s.asset_type,
                s.status,
                COALESCE(SUM(CASE WHEN i.status = '待整改' THEN 1 ELSE 0 END), 0) AS pending_rectification_count,
                COALESCE(SUM(CASE WHEN i.status = '待复核' THEN 1 ELSE 0 END), 0) AS pending_review_count,
                COALESCE(SUM(CASE WHEN i.status = '已闭环' THEN 1 ELSE 0 END), 0) AS closed_count,
                MAX(ins.inspection_date) AS latest_inspection_date
            FROM stations s
            LEFT JOIN issues i ON i.station_id = s.id
            LEFT JOIN inspections ins ON ins.station_id = s.id
            WHERE s.longitude IS NOT NULL
              AND s.latitude IS NOT NULL
            GROUP BY
                s.id,
                s.station_name,
                s.region,
                s.address,
                s.longitude,
                s.latitude,
                s.station_manager_name,
                s.station_manager_phone,
                s.asset_type,
                s.status
            ORDER BY s.id;
            """
        )
        rows = cur.fetchall()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/event-feed")
def get_event_feed():
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM (
                SELECT
                    CONCAT('issue-create-', i.id) AS id,
                    s.station_name AS "stationName",
                    CASE
                        WHEN i.status = '待整改' THEN '新提交问题，当前状态：待整改。'
                        WHEN i.status = '待复核' THEN '新提交问题，当前状态：待复核。'
                        WHEN i.status = '已闭环' THEN '新提交问题，当前状态：已闭环。'
                        ELSE '新提交巡检问题。'
                    END AS text,
                    TO_CHAR(COALESCE(i.created_at, NOW()), 'HH24:MI') AS time,
                    CASE
                        WHEN i.status = '待整改' THEN 'danger'
                        WHEN i.status = '待复核' THEN 'warning'
                        ELSE 'info'
                    END AS level,
                    COALESCE(i.created_at, NOW()) AS sort_time
                FROM issues i
                JOIN stations s ON s.id = i.station_id

                UNION ALL

                SELECT
                    CONCAT('category-record-', icr.id) AS id,
                    s.station_name AS "stationName",
                    CASE
                        WHEN icr.result = '正常' THEN CONCAT('完成', c.name, '检查：未发现问题。')
                        ELSE CONCAT('完成', c.name, '检查：发现问题。')
                    END AS text,
                    TO_CHAR(icr.created_at, 'HH24:MI') AS time,
                    CASE
                        WHEN icr.result = '异常' THEN 'warning'
                        ELSE 'info'
                    END AS level,
                    icr.created_at AS sort_time
                FROM inspection_category_records icr
                JOIN inspections ins ON icr.inspection_id = ins.id
                JOIN stations s ON ins.station_id = s.id
                JOIN inspection_categories c ON icr.category_id = c.id
                WHERE icr.created_at IS NOT NULL
            ) feed
            ORDER BY sort_time DESC
            LIMIT 5;
            """
        )
        rows = cur.fetchall()
        response = jsonify(rows)
        response.headers["Cache-Control"] = "no-store"
        return response
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/users")
def get_users():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                u.id,
                u.username,
                u.role,
                u.real_name,
                u.phone,
                u.station_id,
                s.station_name
            FROM users u
            LEFT JOIN stations s ON u.station_id = s.id
            ORDER BY u.id;
        """
        )
        rows = cur.fetchall()
        return jsonify(rows)
    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                }
            ),
            500,
        )
    finally:
        close_db_resources(cur, conn)


@app.route("/api/inspection-standards")
def get_inspection_standards():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id,
                code,
                business_process,
                check_item,
                check_content,
                requirement,
                check_method
            FROM inspection_standards
            ORDER BY CAST(code AS INTEGER);
        """
        )
        rows = cur.fetchall()
        return jsonify(rows)
    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                }
            ),
            500,
        )
    finally:
        close_db_resources(cur, conn)


@app.route("/api/inspection-register", methods=["POST"])
def inspection_register():
    inspector_id = str(request.form.get("inspector_id", "")).strip()
    station_id = str(request.form.get("station_id", "")).strip()
    category_id = str(request.form.get("category_id", "")).strip()
    has_issue = str(request.form.get("has_issue", "")).strip()
    standard_id = str(request.form.get("standard_id", "")).strip()
    description = str(request.form.get("description", "")).strip()
    photo = request.files.get("photo")

    if not inspector_id:
        return jsonify({"success": False, "error": "缺少巡检人信息。"}), 400

    if not station_id:
        return jsonify({"success": False, "error": "请选择站点名称。"}), 400

    if not category_id:
        return jsonify({"success": False, "error": "请选择巡检大类。"}), 400

    if has_issue not in ["yes", "no"]:
        return jsonify({"success": False, "error": "请选择是否发现问题。"}), 400

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT id, username, role, real_name
            FROM users
            WHERE id = %s
            LIMIT 1;
            """,
            (inspector_id,),
        )
        inspector = cur.fetchone()

        if not inspector:
            return jsonify({"success": False, "error": "巡检人不存在。"}), 404

        if inspector["role"] != "supervisor":
            return (
                jsonify(
                    {"success": False, "error": "只有督导组账号可以提交巡检登记。"}
                ),
                403,
            )

        cur.execute(
            """
            SELECT id, station_name
            FROM stations
            WHERE id = %s
            LIMIT 1;
            """,
            (station_id,),
        )
        station = cur.fetchone()

        if not station:
            return jsonify({"success": False, "error": "站点不存在。"}), 404

        cur.execute(
            """
            SELECT id, name
            FROM inspection_categories
            WHERE id = %s
            LIMIT 1;
            """,
            (category_id,),
        )
        category = cur.fetchone()

        if not category:
            return jsonify({"success": False, "error": "巡检大类不存在。"}), 404

        if has_issue == "no":
            cur.execute(
                """
                SELECT icr.id
                FROM inspection_category_records icr
                JOIN inspections ins ON icr.inspection_id = ins.id
                WHERE ins.station_id = %s
                  AND ins.inspection_date = %s
                  AND icr.category_id = %s
                  AND icr.result = '异常'
                LIMIT 1;
                """,
                (station_id, date.today(), category_id),
            )
            existing_abnormal = cur.fetchone()

            if existing_abnormal:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "该站本日该巡检大类下已登记发现问题，不能再登记为未发现问题。",
                        }
                    ),
                    400,
                )

            inspection_id = get_or_create_inspection(cur, station_id, inspector_id)
            category_record_id = create_or_update_category_record(
                cur,
                inspection_id,
                category_id,
                "正常",
                f"本次{category['name']}检查未发现问题",
            )

            conn.commit()
            return jsonify(
                {
                    "success": True,
                    "message": "未发现问题巡检登记成功。",
                    "inspection_id": inspection_id,
                    "category_record_id": category_record_id,
                }
            )

        if not standard_id:
            return jsonify({"success": False, "error": "请选择规范引用。"}), 400

        if not description:
            return jsonify({"success": False, "error": "请填写实际问题描述。"}), 400

        if not photo or not photo.filename:
            return jsonify({"success": False, "error": "请上传问题照片。"}), 400

        cur.execute(
            """
            SELECT id
            FROM inspection_standards
            WHERE id = %s
            LIMIT 1;
            """,
            (standard_id,),
        )
        standard = cur.fetchone()

        if not standard:
            return jsonify({"success": False, "error": "规范引用不存在。"}), 404

        inspection_id = get_or_create_inspection(cur, station_id, inspector_id)
        category_record_id = create_or_update_category_record(
            cur,
            inspection_id,
            category_id,
            "异常",
            f"本次{category['name']}检查发现问题",
        )

        photo_path = save_uploaded_file(photo, "issues")

        cur.execute(
            """
            INSERT INTO issues (
                inspection_id,
                category_record_id,
                station_id,
                standard_id,
                description,
                photo_path,
                status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (
                inspection_id,
                category_record_id,
                station_id,
                standard_id,
                description,
                photo_path,
                "待整改",
            ),
        )
        issue = cur.fetchone()

        conn.commit()
        return jsonify(
            {
                "success": True,
                "message": "发现问题巡检登记成功。",
                "inspection_id": inspection_id,
                "category_record_id": category_record_id,
                "issue_id": issue["id"],
            }
        )
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


# ===== 新增：我的待整改/待复核问题相关API =====


@app.route("/api/my-issues")
def get_my_issues():
    user_id = str(request.args.get("user_id", "")).strip()

    if not user_id:
        return jsonify({"success": False, "error": "缺少用户信息。"}), 400

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT id, role, station_id
            FROM users
            WHERE id = %s
            LIMIT 1;
            """,
            (user_id,),
        )
        user = cur.fetchone()

        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        if user["role"] == "station_manager":
            if not user["station_id"]:
                return jsonify([])

            cur.execute(
                """
                SELECT
                    i.id,
                    s.station_name AS station,
                    std.code,
                    std.business_process,
                    c.name AS category_name,
                    std.check_item,
                    i.description,
                    i.photo_path AS issue_photo,
                    i.rectification_result,
                    i.rectification_note,
                    i.rectification_photo_path AS rectification_photo,
                    i.review_result,
                    i.review_note,
                    i.status
                FROM issues i
                JOIN stations s ON i.station_id = s.id
                JOIN inspection_standards std ON i.standard_id = std.id
                JOIN inspection_category_records icr ON i.category_record_id = icr.id
                JOIN inspection_categories c ON icr.category_id = c.id
                WHERE i.station_id = %s
                  AND i.status = '待整改'
                ORDER BY i.id DESC;
                """,
                (user["station_id"],),
            )
            rows = cur.fetchall()
            return jsonify(rows)

        if user["role"] == "supervisor":
            cur.execute(
                """
                SELECT
                    i.id,
                    s.station_name AS station,
                    std.code,
                    std.business_process,
                    c.name AS category_name,
                    std.check_item,
                    i.description,
                    i.photo_path AS issue_photo,
                    i.rectification_result,
                    i.rectification_note,
                    i.rectification_photo_path AS rectification_photo,
                    i.review_result,
                    i.review_note,
                    i.status
                FROM issues i
                JOIN stations s ON i.station_id = s.id
                JOIN inspection_standards std ON i.standard_id = std.id
                JOIN inspection_category_records icr ON i.category_record_id = icr.id
                JOIN inspection_categories c ON icr.category_id = c.id
                WHERE i.status = '待复核'
                ORDER BY i.id DESC;
                """
            )
            rows = cur.fetchall()
            return jsonify(rows)

        return jsonify([])
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


# ===== 新增：巡检问题列表API =====


@app.route("/api/issues")
def get_issues():
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                i.id,
                TO_CHAR(i.created_at, 'YYYY-MM') AS month,
                TO_CHAR(i.created_at, 'YYYY-MM-DD HH24:MI') AS time,
                s.region,
                s.station_name AS station,
                s.station_manager_name AS station_manager,
                s.station_manager_phone AS station_manager_phone,
                inspector.real_name AS inspector,
                inspector.phone AS inspector_phone,
                std.code,
                std.business_process,
                c.name AS category_name,
                std.check_item,
                std.requirement,
                std.check_method,
                i.description,
                i.photo_path AS issue_photo,
                i.rectification_result,
                i.rectification_note,
                i.rectification_photo_path AS rectification_photo,
                i.review_result,
                i.review_note,
                i.status
            FROM issues i
            JOIN inspections ins ON i.inspection_id = ins.id
            JOIN inspection_category_records icr ON i.category_record_id = icr.id
            JOIN inspection_categories c ON icr.category_id = c.id
            JOIN stations s ON i.station_id = s.id
            JOIN inspection_standards std ON i.standard_id = std.id
            JOIN users inspector ON ins.inspector_id = inspector.id
            ORDER BY i.id DESC;
            """
        )
        rows = cur.fetchall()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


# 新增巡检记录接口
@app.route("/api/inspections")
def get_inspections():
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                MIN(ins.id) AS id,
                TO_CHAR(ins.inspection_date, 'YYYY-MM-DD') AS date,
                s.station_name AS station,
                COALESCE(
                    STRING_AGG(DISTINCT c.name, '、' ORDER BY c.name),
                    '暂无'
                ) AS categories,
                CASE
                    WHEN COUNT(DISTINCT CASE WHEN icr.result = '异常' THEN icr.id END) > 0 THEN '异常'
                    ELSE '正常'
                END AS result,
                COUNT(DISTINCT i.id) AS issue_count
            FROM inspections ins
            JOIN stations s ON ins.station_id = s.id
            LEFT JOIN inspection_category_records icr ON ins.id = icr.inspection_id
            LEFT JOIN inspection_categories c ON icr.category_id = c.id
            LEFT JOIN issues i ON ins.id = i.inspection_id
            GROUP BY ins.inspection_date, s.id, s.station_name
            ORDER BY ins.inspection_date DESC, MIN(ins.id) DESC;
            """
        )
        rows = cur.fetchall()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/issues/<int:issue_id>/rectification", methods=["POST"])
def submit_rectification(issue_id):
    user_id = str(request.form.get("user_id", "")).strip()
    rectification_result = str(request.form.get("rectification_result", "")).strip()
    rectification_note = str(request.form.get("rectification_note", "")).strip()
    rectification_photo = request.files.get("rectification_photo")

    if not user_id:
        return jsonify({"success": False, "error": "缺少用户信息。"}), 400

    if not rectification_result:
        return jsonify({"success": False, "error": "请选择整改结果。"}), 400

    if not rectification_note:
        return jsonify({"success": False, "error": "请填写整改说明。"}), 400

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT id, role, station_id
            FROM users
            WHERE id = %s
            LIMIT 1;
            """,
            (user_id,),
        )
        user = cur.fetchone()

        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        if user["role"] != "station_manager":
            return (
                jsonify({"success": False, "error": "只有站点账号可以提交整改。"}),
                403,
            )

        cur.execute(
            """
            SELECT id, station_id, status
            FROM issues
            WHERE id = %s
            LIMIT 1;
            """,
            (issue_id,),
        )
        issue = cur.fetchone()

        if not issue:
            return jsonify({"success": False, "error": "问题不存在。"}), 404

        if issue["station_id"] != user["station_id"]:
            return (
                jsonify({"success": False, "error": "只能整改本账号所属站点的问题。"}),
                403,
            )

        rectification_photo_path = None
        if rectification_photo and rectification_photo.filename:
            rectification_photo_path = save_uploaded_file(
                rectification_photo, "rectifications"
            )

        if rectification_photo_path:
            cur.execute(
                """
                UPDATE issues
                SET rectification_result = %s,
                    rectification_note = %s,
                    rectification_photo_path = %s,
                    status = '待复核'
                WHERE id = %s;
                """,
                (
                    rectification_result,
                    rectification_note,
                    rectification_photo_path,
                    issue_id,
                ),
            )
        else:
            cur.execute(
                """
                UPDATE issues
                SET rectification_result = %s,
                    rectification_note = %s,
                    status = '待复核'
                WHERE id = %s;
                """,
                (
                    rectification_result,
                    rectification_note,
                    issue_id,
                ),
            )

        conn.commit()
        return jsonify({"success": True, "message": "整改提交成功，已转入待复核。"})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/issues/<int:issue_id>/review", methods=["POST"])
def submit_review(issue_id):
    user_id = str(request.form.get("user_id", "")).strip()
    review_result = str(request.form.get("review_result", "")).strip()
    review_note = str(request.form.get("review_note", "")).strip()

    if not user_id:
        return jsonify({"success": False, "error": "缺少用户信息。"}), 400

    if not review_result:
        return jsonify({"success": False, "error": "请选择督导组复核结果。"}), 400

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT id, role
            FROM users
            WHERE id = %s
            LIMIT 1;
            """,
            (user_id,),
        )
        user = cur.fetchone()

        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        if user["role"] != "supervisor":
            return (
                jsonify({"success": False, "error": "只有督导组账号可以提交复核。"}),
                403,
            )

        cur.execute(
            """
            SELECT id, status
            FROM issues
            WHERE id = %s
            LIMIT 1;
            """,
            (issue_id,),
        )
        issue = cur.fetchone()

        if not issue:
            return jsonify({"success": False, "error": "问题不存在。"}), 404

        new_status = "已闭环" if review_result == "已整改" else "待整改"

        cur.execute(
            """
            UPDATE issues
            SET review_result = %s,
                review_note = %s,
                status = %s
            WHERE id = %s;
            """,
            (
                review_result,
                review_note,
                new_status,
                issue_id,
            ),
        )

        conn.commit()
        return jsonify({"success": True, "message": "督导组复核提交成功。"})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


# ===== 原有静态文件上传API =====


@app.route("/storage/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(STORAGE_ROOT, filename)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
