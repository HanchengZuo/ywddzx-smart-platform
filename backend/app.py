from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from io import BytesIO
import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from werkzeug.utils import secure_filename
from PIL import Image

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(__file__)
STORAGE_ROOT = os.path.join(BASE_DIR, "storage")
MAX_IMAGE_BYTES = 500 * 1024
MAX_PDF_BYTES = 50 * 1024 * 1024
MAX_VIDEO_BYTES = 500 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
ALLOWED_TRAINING_MATERIAL_EXTENSIONS = {".pdf", ".mp4", ".mov", ".m4v", ".webm"}

ISSUES_STORAGE_DIR = os.path.join(STORAGE_ROOT, "issues")
RECTIFICATIONS_STORAGE_DIR = os.path.join(STORAGE_ROOT, "rectifications")
SIGNATURES_STORAGE_DIR = os.path.join(STORAGE_ROOT, "signatures")
INSPECTION_ORIGINALS_STORAGE_DIR = os.path.join(STORAGE_ROOT, "inspection_originals")
TRAINING_MATERIALS_STORAGE_DIR = os.path.join(STORAGE_ROOT, "training_materials")
BEIJING_TZ = ZoneInfo("Asia/Shanghai")


TABLE_CODE_TO_PHYSICAL_TABLE = {
    "quality_check": "inspection_table_quality_check",
    "service_hygiene_check": "inspection_table_service_hygiene_check",
}

# === Inspection Plan Config constants ===
PLAN_MANAGER_USERNAMES = {"kongdechen", "supervisor"}
CHECKLIST_ORIGINAL_MANAGER_USERNAMES = {"kongdechen", "supervisor"}
TRAINING_MATERIAL_ADMIN_USERNAMES = {"supervisor", "superviosr"}
COVERAGE_TYPE_LABELS = {
    "monthly": "月度覆盖",
    "quarterly": "季度覆盖",
    "yearly": "年度覆盖",
}

CERTIFICATE_TYPES = [
    {
        "code": "dangerous_chemicals_permit",
        "name": "危险化学品经营许可证",
        "note": "危化证继续经营应在有效期满90天前申请延期。",
        "recommended_reminder_days": 150,
        "legal_reminder_days": 90,
        "recommended_label": "到期前 150天",
        "legal_label": "到期前 90天",
        "rule": "150天进入推荐提醒；90天内进入法定提醒。危化证继续经营应在有效期满90天前申请延期。",
    },
    {
        "code": "oil_retail_permit",
        "name": "成品油零售经营批准证书",
        "note": "成品油零售经营批准证书继续经营应在届满30日前申请延续。",
        "recommended_reminder_days": 90,
        "legal_reminder_days": 30,
        "recommended_label": "到期前 90天",
        "legal_label": "到期前 30天",
        "rule": "90天进入推荐提醒；30天内进入法定提醒。成品油零售经营批准证书继续经营应在届满30日前申请延续。",
    },
    {
        "code": "pollutant_discharge_permit",
        "name": "排污许可证",
        "note": "排污许可证继续排污应在届满60日前申请延续。",
        "recommended_reminder_days": 120,
        "legal_reminder_days": 60,
        "recommended_label": "到期前 120天",
        "legal_label": "到期前 60天",
        "rule": "120天进入推荐提醒；60天内进入法定提醒。排污许可证继续排污应在届满60日前申请延续。",
    },
    {
        "code": "lightning_protection_report",
        "name": "防雷检测报告",
        "note": "加油站等爆炸、火灾危险环境场所防雷装置一般每半年检测一次。",
        "recommended_reminder_days": 30,
        "legal_reminder_days": 7,
        "recommended_label": "到期前 30天",
        "legal_label": "到期前 7天",
        "rule": "30天进入推荐提醒；7天内进入法定提醒。加油站等爆炸、火灾危险环境场所防雷装置一般每半年检测一次。",
    },
    {
        "code": "tobacco_monopoly_permit",
        "name": "烟草专卖零售许可证",
        "note": "烟草专卖许可证继续经营应在届满30日前申请延续。",
        "recommended_reminder_days": 60,
        "legal_reminder_days": 30,
        "recommended_label": "到期前 60天",
        "legal_label": "到期前 30天",
        "rule": "60天进入推荐提醒；30天内进入法定提醒。烟草专卖许可证继续经营应在届满30日前申请延续。",
    },
    {
        "code": "business_license",
        "name": "工商营业执照",
        "note": "只有存在经营期限时才提醒。",
        "recommended_reminder_days": 90,
        "legal_reminder_days": 30,
        "recommended_label": "到期前 90天",
        "legal_label": "到期前 30天",
        "rule": "新版营业执照照面通常不再记载营业期限，但电子营业执照或企业信用公示系统可能仍显示经营期限；因此只有存在经营期限时才提醒。",
    },
]

CERTIFICATE_TYPE_BY_CODE = {item["code"]: item for item in CERTIFICATE_TYPES}


def beijing_now():
    return datetime.now(BEIJING_TZ)


def beijing_today():
    return beijing_now().date()


os.makedirs(ISSUES_STORAGE_DIR, exist_ok=True)
os.makedirs(RECTIFICATIONS_STORAGE_DIR, exist_ok=True)
os.makedirs(SIGNATURES_STORAGE_DIR, exist_ok=True)
os.makedirs(INSPECTION_ORIGINALS_STORAGE_DIR, exist_ok=True)
os.makedirs(TRAINING_MATERIALS_STORAGE_DIR, exist_ok=True)


def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        port=os.environ.get("DB_PORT", 5432),
        dbname=os.environ.get("DB_NAME", "ywddzx"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "postgres"),
        cursor_factory=RealDictCursor,
        options="-c timezone=Asia/Shanghai",
    )


def close_db_resources(cur=None, conn=None):
    if cur:
        cur.close()
    if conn:
        conn.close()


def ensure_storage_subdir(base_dir):
    now = beijing_now()
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


# Helper for saving signature PNGs
def save_signature_file(file_storage):
    if not file_storage or not file_storage.filename:
        return None

    target_dir, now = ensure_storage_subdir(SIGNATURES_STORAGE_DIR)
    filename = f"signature_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex}.png"
    save_path = os.path.join(target_dir, filename)

    image_bytes = file_storage.read()
    if not image_bytes:
        raise ValueError("签名图片内容为空。")

    try:
        image = Image.open(BytesIO(image_bytes))
    except Exception as exc:
        raise ValueError("上传文件不是可识别的签名图片。") from exc

    if image.mode not in ("RGBA", "LA"):
        image = image.convert("RGBA")
    else:
        image = image.convert("RGBA")

    max_width = 800
    max_height = 320
    if image.width > max_width or image.height > max_height:
        ratio = min(max_width / float(image.width), max_height / float(image.height))
        new_size = (
            max(1, int(image.width * ratio)),
            max(1, int(image.height * ratio)),
        )
        image = image.resize(new_size, Image.LANCZOS)

    image.save(save_path, format="PNG", optimize=True)

    relative_dir = os.path.relpath(target_dir, STORAGE_ROOT).replace("\\", "/")
    return f"/{relative_dir}/{filename}"


def normalize_upload_display_name(filename):
    raw_name = str(filename or "").replace("\\", "/").split("/")[-1].strip()
    return raw_name[:180] or "检查表原件.pdf"


def save_inspection_original_pdf(file_storage):
    if not file_storage or not file_storage.filename:
        raise ValueError("请选择需要上传的 PDF 文件。")

    original_name = normalize_upload_display_name(file_storage.filename)
    ext = os.path.splitext(original_name)[1].lower()
    if ext != ".pdf":
        raise ValueError("仅支持上传 PDF 文件。")

    pdf_bytes = file_storage.read()
    if not pdf_bytes:
        raise ValueError("上传 PDF 内容为空。")

    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise ValueError("PDF 文件不能超过 50MB。")

    if not pdf_bytes.startswith(b"%PDF"):
        raise ValueError("上传文件不是有效的 PDF 文件。")

    target_dir, now = ensure_storage_subdir(INSPECTION_ORIGINALS_STORAGE_DIR)
    filename = f"checklist_original_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex}.pdf"
    save_path = os.path.join(target_dir, filename)

    with open(save_path, "wb") as f:
        f.write(pdf_bytes)

    relative_dir = os.path.relpath(target_dir, STORAGE_ROOT).replace("\\", "/")
    return f"/{relative_dir}/{filename}", original_name, len(pdf_bytes)


def get_training_material_file_type(extension):
    return "pdf" if extension == ".pdf" else "video"


def save_training_material_file(file_storage):
    if not file_storage or not file_storage.filename:
        raise ValueError("请选择需要上传的培训材料。")

    original_name = normalize_upload_display_name(file_storage.filename)
    ext = os.path.splitext(original_name)[1].lower()
    if ext not in ALLOWED_TRAINING_MATERIAL_EXTENSIONS:
        raise ValueError("仅支持上传 PDF 或 MP4、MOV、M4V、WEBM 视频文件。")

    file_bytes = file_storage.read()
    if not file_bytes:
        raise ValueError("上传文件内容为空。")

    file_type = get_training_material_file_type(ext)
    max_size = MAX_PDF_BYTES if file_type == "pdf" else MAX_VIDEO_BYTES
    if len(file_bytes) > max_size:
        size_label = "50MB" if file_type == "pdf" else "500MB"
        raise ValueError(f"{'PDF' if file_type == 'pdf' else '视频'}文件不能超过 {size_label}。")

    if file_type == "pdf" and not file_bytes.startswith(b"%PDF"):
        raise ValueError("上传文件不是有效的 PDF 文件。")

    target_dir, now = ensure_storage_subdir(TRAINING_MATERIALS_STORAGE_DIR)
    filename = (
        f"training_material_{now.strftime('%Y%m%d_%H%M%S')}_"
        f"{uuid.uuid4().hex}{ext}"
    )
    save_path = os.path.join(target_dir, filename)

    with open(save_path, "wb") as f:
        f.write(file_bytes)

    relative_dir = os.path.relpath(target_dir, STORAGE_ROOT).replace("\\", "/")
    return f"/{relative_dir}/{filename}", original_name, len(file_bytes), file_type


def resolve_storage_abs_path(relative_path):
    value = str(relative_path or "").strip()
    if value.startswith("/storage/"):
        value = value[len("/storage/") :]
    elif value.startswith("/"):
        value = value[1:]

    storage_root_abs = os.path.abspath(STORAGE_ROOT)
    target_path = os.path.abspath(os.path.join(storage_root_abs, value))
    if os.path.commonpath([storage_root_abs, target_path]) != storage_root_abs:
        return None
    return target_path


def remove_storage_file(relative_path):
    target_path = resolve_storage_abs_path(relative_path)
    try:
        if target_path and os.path.isfile(target_path):
            os.remove(target_path)
    except OSError:
        pass


def get_checklist_field_meta(cur, inspection_table_id):
    cur.execute(
        """
        SELECT field_key, field_label
        FROM inspection_table_fields
        WHERE inspection_table_id = %s
        ORDER BY sort_order ASC, id ASC;
        """,
        (inspection_table_id,),
    )
    rows = cur.fetchall()
    return [(row["field_key"], row["field_label"]) for row in rows]


def build_standard_detail_text(field_meta, row):
    lines = []
    for field_key, field_label in field_meta:
        value = row.get(field_key)
        if value is None:
            continue
        value_text = str(value).strip()
        if not value_text:
            continue
        lines.append(f"{field_label}：{value_text}")
    return "\n".join(lines)


def get_physical_table_name_by_code(table_code):
    return TABLE_CODE_TO_PHYSICAL_TABLE.get(str(table_code or "").strip())


def get_inspection_table_record(cur, inspection_table_id):
    cur.execute(
        """
        SELECT
            id,
            table_code,
            table_name,
            description,
            is_active
        FROM inspection_tables
        WHERE id = %s
        LIMIT 1;
        """,
        (inspection_table_id,),
    )
    return cur.fetchone()


def fetch_standard_from_table(cur, physical_table_name, standard_id):
    cur.execute(
        sql.SQL("SELECT * FROM {} WHERE standard_id = %s LIMIT 1;").format(
            sql.Identifier(physical_table_name)
        ),
        (standard_id,),
    )
    return cur.fetchone()


def create_inspection_record(
    cur, station_id, inspector_id, inspection_table_id, batch_id
):
    today = beijing_today()
    cur.execute(
        """
        INSERT INTO inspections (
            station_id,
            inspector_id,
            inspection_table_id,
            inspection_date,
            batch_id
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
        """,
        (station_id, inspector_id, inspection_table_id, today, batch_id),
    )
    row = cur.fetchone()
    return row["id"]


# === Inspection Plan Configs helpers ===
def get_user_by_id(cur, user_id):
    cur.execute(
        """
        SELECT id, username, role, real_name, station_id
        FROM users
        WHERE id = %s
        LIMIT 1;
        """,
        (user_id,),
    )
    return cur.fetchone()


# 当前阶段先沿用前端约定：只有指定督导账号可以管理巡检计划
# 后续建议改为 users 表中的独立权限字段（如 can_manage_plan）
def can_manage_plan(user):
    if not user:
        return False
    return (
        user.get("role") == "supervisor"
        and user.get("username") in PLAN_MANAGER_USERNAMES
    )


def can_manage_certificates(user):
    return bool(user and user.get("role") == "supervisor")


def can_manage_checklist_originals(user):
    return bool(user and user.get("username") in CHECKLIST_ORIGINAL_MANAGER_USERNAMES)


def can_upload_training_materials(user):
    return bool(user and user.get("role") == "supervisor")


def can_delete_any_training_material(user):
    return bool(user and user.get("username") in TRAINING_MATERIAL_ADMIN_USERNAMES)


def can_edit_training_material(user, material_row):
    if not user or not material_row:
        return False
    return str(material_row.get("uploaded_by") or "") == str(user.get("id") or "")


def can_delete_training_material(user, material_row):
    return can_edit_training_material(user, material_row) or can_delete_any_training_material(user)


def ensure_training_materials_table(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS training_materials (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_path TEXT NOT NULL,
            original_filename TEXT,
            file_size BIGINT,
            uploaded_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cur.execute(
        """
        ALTER TABLE training_materials
        ADD COLUMN IF NOT EXISTS title TEXT;
        """
    )
    cur.execute(
        """
        ALTER TABLE training_materials
        ADD COLUMN IF NOT EXISTS file_type TEXT;
        """
    )
    cur.execute(
        """
        ALTER TABLE training_materials
        ADD COLUMN IF NOT EXISTS original_filename TEXT;
        """
    )
    cur.execute(
        """
        ALTER TABLE training_materials
        ADD COLUMN IF NOT EXISTS file_size BIGINT;
        """
    )
    cur.execute(
        """
        ALTER TABLE training_materials
        ADD COLUMN IF NOT EXISTS uploaded_by INTEGER REFERENCES users(id) ON DELETE SET NULL;
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_training_materials_updated_at
        ON training_materials (updated_at DESC);
        """
    )


def ensure_inspection_table_original_files_table(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS inspection_table_original_files (
            id SERIAL PRIMARY KEY,
            inspection_table_id INTEGER NOT NULL REFERENCES inspection_tables(id) ON DELETE CASCADE,
            file_path TEXT NOT NULL,
            original_filename TEXT,
            file_size BIGINT,
            uploaded_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (inspection_table_id)
        );
        """
    )
    cur.execute(
        """
        ALTER TABLE inspection_table_original_files
        ADD COLUMN IF NOT EXISTS original_filename TEXT;
        """
    )
    cur.execute(
        """
        ALTER TABLE inspection_table_original_files
        ADD COLUMN IF NOT EXISTS file_size BIGINT;
        """
    )
    cur.execute(
        """
        ALTER TABLE inspection_table_original_files
        ADD COLUMN IF NOT EXISTS uploaded_by INTEGER REFERENCES users(id) ON DELETE SET NULL;
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_inspection_table_original_files_table_id
        ON inspection_table_original_files (inspection_table_id);
        """
    )


def ensure_station_certificates_table(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS station_certificates (
            id SERIAL PRIMARY KEY,
            station_id INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
            certificate_type TEXT NOT NULL,
            certificate_name TEXT NOT NULL,
            start_date DATE,
            expiry_date DATE NOT NULL,
            remark TEXT,
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (station_id, certificate_type)
        );
        """
    )
    cur.execute(
        """
        ALTER TABLE station_certificates
        ADD COLUMN IF NOT EXISTS remark TEXT;
        """
    )
    cur.execute(
        """
        ALTER TABLE station_certificates
        ADD COLUMN IF NOT EXISTS created_by INTEGER REFERENCES users(id) ON DELETE SET NULL;
        """
    )
    cur.execute(
        """
        ALTER TABLE station_certificates
        ADD COLUMN IF NOT EXISTS updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL;
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_station_certificates_expiry_date
        ON station_certificates (expiry_date);
        """
    )


def normalize_optional_date(value):
    value_text = str(value or "").strip()
    if not value_text:
        return None
    try:
        return datetime.strptime(value_text, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("日期格式必须为 YYYY-MM-DD。") from exc


# === Helper functions for automatic inspection-plan completion writeback ===


def get_plan_period_key_for_date(coverage_type, target_date):
    if coverage_type == "monthly":
        return f"{target_date.year}年{target_date.month}月"

    if coverage_type == "quarterly":
        quarter = ((target_date.month - 1) // 3) + 1
        quarter_label_map = {
            1: "第一季度",
            2: "第二季度",
            3: "第三季度",
            4: "第四季度",
        }
        return (
            f"{target_date.year}年{quarter_label_map.get(quarter, f'第{quarter}季度')}"
        )

    if coverage_type == "yearly":
        return f"{target_date.year}年"

    return None


def get_period_date_range(coverage_type, period_key):
    if coverage_type == "monthly":
        try:
            year_part, month_part = str(period_key).split("年", 1)
            month_text = month_part.replace("月", "").strip()
            year = int(year_part)
            month = int(month_text)
            start_date = datetime(year, month, 1).date()
            if month == 12:
                end_date = datetime(year + 1, 1, 1).date()
            else:
                end_date = datetime(year, month + 1, 1).date()
            return start_date, end_date
        except Exception:
            return None, None

    if coverage_type == "quarterly":
        try:
            year_part, quarter_part = str(period_key).split("年", 1)
            year = int(year_part)
            normalized_quarter_text = (
                quarter_part.replace("季度", "").replace("第", "").strip()
            )
            quarter_map = {
                "1": 1,
                "2": 2,
                "3": 3,
                "4": 4,
                "一": 1,
                "二": 2,
                "三": 3,
                "四": 4,
                "第一": 1,
                "第二": 2,
                "第三": 3,
                "第四": 4,
            }
            quarter = quarter_map.get(normalized_quarter_text)
            if quarter not in {1, 2, 3, 4}:
                return None, None
            start_month = (quarter - 1) * 3 + 1
            start_date = datetime(year, start_month, 1).date()
            if quarter == 4:
                end_date = datetime(year + 1, 1, 1).date()
            else:
                end_date = datetime(year, start_month + 3, 1).date()
            return start_date, end_date
        except Exception:
            return None, None

    if coverage_type == "yearly":
        try:
            year_text = str(period_key).replace("年", "").strip()
            year = int(year_text)
            start_date = datetime(year, 1, 1).date()
            end_date = datetime(year + 1, 1, 1).date()
            return start_date, end_date
        except Exception:
            return None, None

    return None, None


def sync_plan_station_items_completion_by_history(cur, plan_config_id):
    cur.execute(
        """
        SELECT id, inspection_table_id, coverage_type, period_key
        FROM inspection_plan_configs
        WHERE id = %s
        LIMIT 1;
        """,
        (plan_config_id,),
    )
    plan_config = cur.fetchone()
    if not plan_config:
        return

    start_date, end_date = get_period_date_range(
        plan_config["coverage_type"], plan_config["period_key"]
    )
    if not start_date or not end_date:
        return

    cur.execute(
        """
        UPDATE inspection_plan_station_items psi
        SET completion_status = CASE
                WHEN matched.inspection_id IS NOT NULL THEN 'completed'
                ELSE 'pending'
            END,
            completed_inspection_id = matched.inspection_id,
            completed_at = CASE
                WHEN matched.inspection_id IS NOT NULL THEN COALESCE(matched.inspection_created_at, CURRENT_TIMESTAMP)
                ELSE NULL
            END,
            updated_at = CURRENT_TIMESTAMP
        FROM (
            SELECT
                psi_inner.id AS psi_id,
                matched_ins.id AS inspection_id,
                matched_ins.created_at AS inspection_created_at
            FROM inspection_plan_station_items psi_inner
            LEFT JOIN LATERAL (
                SELECT ins.id, ins.created_at
                FROM inspections ins
                WHERE ins.station_id = psi_inner.station_id
                  AND ins.inspection_table_id = %s
                  AND ins.inspection_date >= %s
                  AND ins.inspection_date < %s
                ORDER BY ins.inspection_date DESC, ins.id DESC
                LIMIT 1
            ) AS matched_ins ON TRUE
            WHERE psi_inner.plan_config_id = %s
              AND psi_inner.is_included = TRUE
        ) AS matched
        WHERE psi.id = matched.psi_id;
        """,
        (
            plan_config["inspection_table_id"],
            start_date,
            end_date,
            plan_config_id,
        ),
    )

    cur.execute(
        """
        UPDATE inspection_plan_station_items
        SET completion_status = 'pending',
            completed_inspection_id = NULL,
            completed_at = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE plan_config_id = %s
          AND is_included = FALSE;
        """,
        (plan_config_id,),
    )


def mark_related_plan_items_completed(
    cur,
    station_id,
    inspection_table_id,
    inspection_id,
    inspection_date,
):
    coverage_types = ["monthly", "quarterly", "yearly"]

    for coverage_type in coverage_types:
        period_key = get_plan_period_key_for_date(coverage_type, inspection_date)
        if not period_key:
            continue

        cur.execute(
            """
            UPDATE inspection_plan_station_items psi
            SET completion_status = 'completed',
                completed_inspection_id = %s,
                completed_at = %s,
                updated_at = CURRENT_TIMESTAMP
            FROM inspection_plan_configs pc
            WHERE psi.plan_config_id = pc.id
              AND pc.inspection_table_id = %s
              AND pc.coverage_type = %s
              AND pc.period_key = %s
              AND psi.station_id = %s
              AND psi.is_included = TRUE;
            """,
            (
                inspection_id,
                beijing_now(),
                inspection_table_id,
                coverage_type,
                period_key,
                station_id,
            ),
        )


# === Inspection Plan Configs API ===


@app.route("/api/inspection-plan-configs")
def get_inspection_plan_configs():
    user_id = str(request.args.get("user_id", "")).strip()
    inspection_table_id = str(request.args.get("inspection_table_id", "")).strip()
    coverage_type = str(request.args.get("coverage_type", "")).strip()
    period_key = str(request.args.get("period_key", "")).strip()

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        if user_id:
            user = get_user_by_id(cur, user_id)
            if not user:
                return jsonify({"success": False, "error": "用户不存在。"}), 404

        where_clauses = []
        params = []

        if inspection_table_id:
            where_clauses.append("pc.inspection_table_id = %s")
            params.append(inspection_table_id)

        if coverage_type:
            where_clauses.append("pc.coverage_type = %s")
            params.append(coverage_type)

        if period_key:
            where_clauses.append("pc.period_key = %s")
            params.append(period_key)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        cur.execute(
            sql.SQL(
                """
                SELECT
                    pc.id,
                    pc.inspection_table_id,
                    it.table_name AS inspection_table_name,
                    pc.coverage_type,
                    pc.period_key,
                    pc.status,
                    pc.remark,
                    creator.username AS created_by_username,
                    updater.username AS updated_by_username,
                    COALESCE(SUM(CASE WHEN psi.is_included = TRUE THEN 1 ELSE 0 END), 0) AS included_station_count,
                    COALESCE(SUM(CASE WHEN psi.is_included = TRUE AND psi.completion_status = 'completed' THEN 1 ELSE 0 END), 0) AS completed_station_count,
                    COALESCE(SUM(CASE WHEN psi.is_included = TRUE AND psi.completion_status = 'pending' THEN 1 ELSE 0 END), 0) AS pending_station_count,
                    pc.created_at,
                    pc.updated_at
                FROM inspection_plan_configs pc
                JOIN inspection_tables it ON pc.inspection_table_id = it.id
                JOIN users creator ON pc.created_by = creator.id
                LEFT JOIN users updater ON pc.updated_by = updater.id
                LEFT JOIN inspection_plan_station_items psi ON psi.plan_config_id = pc.id
                {where_sql}
                GROUP BY
                    pc.id,
                    pc.inspection_table_id,
                    it.table_name,
                    pc.coverage_type,
                    pc.period_key,
                    pc.status,
                    pc.remark,
                    creator.username,
                    updater.username,
                    pc.created_at,
                    pc.updated_at
                ORDER BY pc.id DESC;
                """
            ).format(where_sql=sql.SQL(where_sql)),
            params,
        )
        rows = cur.fetchall()

        result = []
        for row in rows:
            included_count = int(row["included_station_count"] or 0)
            completed_count = int(row["completed_station_count"] or 0)
            pending_count = int(row["pending_station_count"] or 0)
            completion_rate = (
                round((completed_count / included_count) * 100)
                if included_count > 0
                else 0
            )
            result.append(
                {
                    "id": row["id"],
                    "inspection_table_id": row["inspection_table_id"],
                    "inspection_table_name": row["inspection_table_name"],
                    "coverage_type": row["coverage_type"],
                    "coverage_type_label": COVERAGE_TYPE_LABELS.get(
                        row["coverage_type"], row["coverage_type"]
                    ),
                    "period_key": row["period_key"],
                    "status": row["status"],
                    "remark": row["remark"],
                    "created_by_username": row["created_by_username"],
                    "updated_by_username": row["updated_by_username"],
                    "included_station_count": included_count,
                    "completed_station_count": completed_count,
                    "pending_station_count": pending_count,
                    "completion_rate": completion_rate,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )

        return jsonify({"success": True, "items": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/inspection-plan-configs/<int:plan_config_id>")
def get_inspection_plan_config_detail(plan_config_id):
    user_id = str(request.args.get("user_id", "")).strip()

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        if user_id:
            user = get_user_by_id(cur, user_id)
            if not user:
                return jsonify({"success": False, "error": "用户不存在。"}), 404

        cur.execute(
            """
            SELECT
                pc.id,
                pc.inspection_table_id,
                it.table_name AS inspection_table_name,
                pc.coverage_type,
                pc.period_key,
                pc.status,
                pc.remark,
                creator.username AS created_by_username,
                updater.username AS updated_by_username,
                pc.created_at,
                pc.updated_at
            FROM inspection_plan_configs pc
            JOIN inspection_tables it ON pc.inspection_table_id = it.id
            JOIN users creator ON pc.created_by = creator.id
            LEFT JOIN users updater ON pc.updated_by = updater.id
            WHERE pc.id = %s
            LIMIT 1;
            """,
            (plan_config_id,),
        )
        config_row = cur.fetchone()

        if not config_row:
            return jsonify({"success": False, "error": "巡检计划配置不存在。"}), 404

        cur.execute(
            """
            SELECT
                psi.id,
                psi.station_id,
                s.station_name,
                s.region,
                s.address,
                psi.is_included,
                psi.completion_status,
                psi.completed_inspection_id,
                TO_CHAR(psi.completed_at, 'YYYY-MM-DD HH24:MI') AS completed_at,
                psi.note
            FROM inspection_plan_station_items psi
            JOIN stations s ON psi.station_id = s.id
            WHERE psi.plan_config_id = %s
            ORDER BY s.id ASC;
            """,
            (plan_config_id,),
        )
        station_rows = cur.fetchall()

        included_count = sum(1 for row in station_rows if row["is_included"])
        completed_count = sum(
            1
            for row in station_rows
            if row["is_included"] and row["completion_status"] == "completed"
        )
        pending_count = sum(
            1
            for row in station_rows
            if row["is_included"] and row["completion_status"] == "pending"
        )
        completion_rate = (
            round((completed_count / included_count) * 100) if included_count > 0 else 0
        )

        return jsonify(
            {
                "success": True,
                "item": {
                    "id": config_row["id"],
                    "inspection_table_id": config_row["inspection_table_id"],
                    "inspection_table_name": config_row["inspection_table_name"],
                    "coverage_type": config_row["coverage_type"],
                    "coverage_type_label": COVERAGE_TYPE_LABELS.get(
                        config_row["coverage_type"], config_row["coverage_type"]
                    ),
                    "period_key": config_row["period_key"],
                    "status": config_row["status"],
                    "remark": config_row["remark"],
                    "created_by_username": config_row["created_by_username"],
                    "updated_by_username": config_row["updated_by_username"],
                    "included_station_count": included_count,
                    "completed_station_count": completed_count,
                    "pending_station_count": pending_count,
                    "completion_rate": completion_rate,
                    "created_at": config_row["created_at"],
                    "updated_at": config_row["updated_at"],
                    "stations": station_rows,
                },
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route(
    "/api/inspection-plan-configs/<int:plan_config_id>/stations", methods=["PUT"]
)
def save_inspection_plan_config_stations(plan_config_id):
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    stations = data.get("stations") or []

    if not user_id:
        return jsonify({"success": False, "error": "缺少用户信息。"}), 400

    if not isinstance(stations, list):
        return jsonify({"success": False, "error": "stations 参数格式不正确。"}), 400

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        user = get_user_by_id(cur, user_id)
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        if not can_manage_plan(user):
            return (
                jsonify({"success": False, "error": "当前账号无权维护巡检计划。"}),
                403,
            )

        cur.execute(
            """
            SELECT id, inspection_table_id
            FROM inspection_plan_configs
            WHERE id = %s
            LIMIT 1;
            """,
            (plan_config_id,),
        )
        config_row = cur.fetchone()

        if not config_row:
            return jsonify({"success": False, "error": "巡检计划配置不存在。"}), 404

        station_ids = []
        normalized_items = []
        for item in stations:
            if not isinstance(item, dict):
                return (
                    jsonify({"success": False, "error": "stations 中存在非法项。"}),
                    400,
                )

            station_id = item.get("station_id")
            is_included = bool(item.get("is_included", True))
            note = str(item.get("note", "")).strip() or None

            if not station_id:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "stations 中存在缺少 station_id 的项。",
                        }
                    ),
                    400,
                )

            station_ids.append(station_id)
            normalized_items.append(
                {
                    "station_id": station_id,
                    "is_included": is_included,
                    "note": note,
                }
            )

        if station_ids:
            cur.execute(
                """
                SELECT id
                FROM stations
                WHERE id = ANY(%s);
                """,
                (station_ids,),
            )
            existing_station_rows = cur.fetchall()
            existing_station_ids = {row["id"] for row in existing_station_rows}
            missing_station_ids = [
                sid for sid in station_ids if sid not in existing_station_ids
            ]
            if missing_station_ids:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": f"以下站点不存在：{', '.join(str(x) for x in missing_station_ids)}",
                        }
                    ),
                    400,
                )

        cur.execute(
            "DELETE FROM inspection_plan_station_items WHERE plan_config_id = %s;",
            (plan_config_id,),
        )

        for item in normalized_items:
            cur.execute(
                """
                INSERT INTO inspection_plan_station_items (
                    plan_config_id,
                    station_id,
                    is_included,
                    completion_status,
                    completed_inspection_id,
                    completed_at,
                    note,
                    updated_at
                )
                VALUES (%s, %s, %s, 'pending', NULL, NULL, %s, CURRENT_TIMESTAMP);
                """,
                (
                    plan_config_id,
                    item["station_id"],
                    item["is_included"],
                    item["note"],
                ),
            )

        cur.execute(
            """
            UPDATE inspection_plan_configs
            SET updated_by = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
            """,
            (user_id, plan_config_id),
        )

        sync_plan_station_items_completion_by_history(cur, plan_config_id)
        conn.commit()
        return jsonify({"success": True, "message": "巡检计划站点明细保存成功。"})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


# Inspection batch support
def get_or_create_inspection_batch(cur, station_id, inspector_id, batch_date):
    cur.execute(
        """
        SELECT id
        FROM inspection_batches
        WHERE station_id = %s
          AND batch_date = %s
        ORDER BY id ASC
        LIMIT 1;
        """,
        (station_id, batch_date),
    )
    existing_batch = cur.fetchone()
    if existing_batch:
        return existing_batch["id"]

    cur.execute(
        """
        INSERT INTO inspection_batches (
            station_id,
            inspector_id,
            batch_date
        )
        VALUES (%s, %s, %s)
        RETURNING id;
        """,
        (station_id, inspector_id, batch_date),
    )
    row = cur.fetchone()
    return row["id"]


def serialize_standard_row(field_meta, row):
    item = dict(row)
    item["standard_detail_text"] = build_standard_detail_text(field_meta, row)
    return item


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


# === 检查表级签名确认 API ===
@app.route("/api/inspections/<int:inspection_id>/sign", methods=["POST"])
def sign_inspection_record(inspection_id):
    user_id = str(request.form.get("user_id", "")).strip()
    signed_name = str(request.form.get("signed_name", "")).strip()
    signature_file = request.files.get("signature")

    if not user_id:
        return jsonify({"success": False, "error": "缺少用户信息。"}), 400

    if not signed_name:
        return jsonify({"success": False, "error": "请填写站经理姓名。"}), 400

    if not signature_file or not signature_file.filename:
        return jsonify({"success": False, "error": "请提交站经理签名。"}), 400

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
                jsonify(
                    {
                        "success": False,
                        "error": "只有督导组账号可以发起检查表签名确认。",
                    }
                ),
                403,
            )

        cur.execute(
            """
            SELECT
                ins.id,
                ins.station_id,
                ins.inspection_date,
                ins.sign_status,
                s.station_name,
                t.table_name
            FROM inspections ins
            JOIN stations s ON ins.station_id = s.id
            JOIN inspection_tables t ON ins.inspection_table_id = t.id
            WHERE ins.id = %s
            LIMIT 1;
            """,
            (inspection_id,),
        )
        inspection = cur.fetchone()

        if not inspection:
            return jsonify({"success": False, "error": "巡检记录不存在。"}), 404

        if inspection["sign_status"] == "已签名确认":
            return jsonify({"success": False, "error": "该检查表已完成签名确认。"}), 400

        signature_path = save_signature_file(signature_file)

        cur.execute(
            """
            UPDATE inspections
            SET sign_status = '已签名确认',
                station_manager_signed_name = %s,
                station_manager_signature_path = %s,
                station_manager_signed_at = %s
            WHERE id = %s;
            """,
            (
                signed_name,
                signature_path,
                beijing_now(),
                inspection_id,
            ),
        )

        conn.commit()
        return jsonify(
            {
                "success": True,
                "message": "本检查表签名确认成功。",
                "inspection_id": inspection_id,
                "signature_path": signature_path,
            }
        )
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
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
                station_type,
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


@app.route("/api/station-certificates", methods=["GET"])
def get_station_certificates():
    user_id = str(request.args.get("user_id", "")).strip()
    if not user_id:
        return jsonify({"success": False, "error": "缺少用户信息。"}), 400

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_station_certificates_table(cur)
        conn.commit()

        user = get_user_by_id(cur, user_id)
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        if user["role"] not in ("supervisor", "station_manager"):
            return (
                jsonify({"success": False, "error": "当前账号无权访问证照管理。"}),
                403,
            )

        station_params = []
        station_where = ""
        if user["role"] == "station_manager":
            if not user["station_id"]:
                return jsonify(
                    {
                        "success": True,
                        "certificate_types": CERTIFICATE_TYPES,
                        "stations": [],
                        "records": [],
                    }
                )
            station_where = "WHERE id = %s"
            station_params.append(user["station_id"])

        cur.execute(
            f"""
            SELECT
                id,
                station_name,
                region,
                address,
                station_type,
                asset_type,
                status
            FROM stations
            {station_where}
            ORDER BY region NULLS LAST, station_name ASC, id ASC;
            """,
            tuple(station_params),
        )
        stations = cur.fetchall()

        record_params = []
        record_where = ""
        if user["role"] == "station_manager":
            record_where = "WHERE sc.station_id = %s"
            record_params.append(user["station_id"])

        cur.execute(
            f"""
            SELECT
                sc.id,
                sc.station_id,
                s.station_name,
                s.region,
                s.asset_type,
                sc.certificate_type,
                sc.certificate_name,
                TO_CHAR(sc.start_date, 'YYYY-MM-DD') AS start_date,
                TO_CHAR(sc.expiry_date, 'YYYY-MM-DD') AS expiry_date,
                sc.remark,
                TO_CHAR(sc.created_at, 'YYYY-MM-DD HH24:MI') AS created_at,
                TO_CHAR(sc.updated_at, 'YYYY-MM-DD HH24:MI') AS updated_at
            FROM station_certificates sc
            JOIN stations s ON sc.station_id = s.id
            {record_where}
            ORDER BY sc.expiry_date ASC, s.station_name ASC, sc.certificate_name ASC;
            """,
            tuple(record_params),
        )
        records = cur.fetchall()

        for record in records:
            type_meta = CERTIFICATE_TYPE_BY_CODE.get(record["certificate_type"], {})
            if type_meta:
                record["certificate_name"] = type_meta.get(
                    "name", record["certificate_name"]
                )
            record["recommended_reminder_days"] = type_meta.get(
                "recommended_reminder_days", 30
            )
            record["legal_reminder_days"] = type_meta.get("legal_reminder_days", 7)
            record["recommended_label"] = type_meta.get("recommended_label")
            record["legal_label"] = type_meta.get("legal_label")
            record["rule"] = type_meta.get("rule")

        return jsonify(
            {
                "success": True,
                "certificate_types": CERTIFICATE_TYPES,
                "stations": stations,
                "records": records,
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/station-certificates", methods=["POST"])
def save_station_certificate():
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()

    if not user_id:
        return jsonify({"success": False, "error": "缺少用户信息。"}), 400

    station_id = data.get("station_id")
    certificate_type = str(data.get("certificate_type", "")).strip()
    remark = str(data.get("remark", "")).strip() or None

    if not station_id:
        return jsonify({"success": False, "error": "请选择站点。"}), 400

    if certificate_type not in CERTIFICATE_TYPE_BY_CODE:
        return jsonify({"success": False, "error": "请选择有效的证照类型。"}), 400

    try:
        start_date = normalize_optional_date(data.get("start_date"))
        expiry_date = normalize_optional_date(data.get("expiry_date"))
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    if not expiry_date:
        return jsonify({"success": False, "error": "到期时间必须录入。"}), 400

    if start_date and start_date > expiry_date:
        return jsonify({"success": False, "error": "起始日期不能晚于到期时间。"}), 400

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_station_certificates_table(cur)

        user = get_user_by_id(cur, user_id)
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        if not can_manage_certificates(user):
            return (
                jsonify(
                    {"success": False, "error": "只有督导组账号可以维护证照有效期。"}
                ),
                403,
            )

        cur.execute(
            """
            SELECT id
            FROM stations
            WHERE id = %s
            LIMIT 1;
            """,
            (station_id,),
        )
        if not cur.fetchone():
            return jsonify({"success": False, "error": "站点不存在。"}), 404

        type_meta = CERTIFICATE_TYPE_BY_CODE[certificate_type]
        cur.execute(
            """
            INSERT INTO station_certificates (
                station_id,
                certificate_type,
                certificate_name,
                start_date,
                expiry_date,
                remark,
                created_by,
                updated_by,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (station_id, certificate_type)
            DO UPDATE SET
                certificate_name = EXCLUDED.certificate_name,
                start_date = EXCLUDED.start_date,
                expiry_date = EXCLUDED.expiry_date,
                remark = EXCLUDED.remark,
                updated_by = EXCLUDED.updated_by,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id;
            """,
            (
                station_id,
                certificate_type,
                type_meta["name"],
                start_date,
                expiry_date,
                remark,
                user["id"],
                user["id"],
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return jsonify(
            {
                "success": True,
                "message": "证照有效期已保存。",
                "id": row["id"],
            }
        )
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/station-certificates/<int:certificate_id>", methods=["DELETE"])
def delete_station_certificate(certificate_id):
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id") or request.args.get("user_id", "")).strip()

    if not user_id:
        return jsonify({"success": False, "error": "缺少用户信息。"}), 400

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_station_certificates_table(cur)

        user = get_user_by_id(cur, user_id)
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        if not can_manage_certificates(user):
            return (
                jsonify(
                    {"success": False, "error": "只有督导组账号可以删除证照记录。"}
                ),
                403,
            )

        cur.execute(
            """
            DELETE FROM station_certificates
            WHERE id = %s
            RETURNING id;
            """,
            (certificate_id,),
        )
        deleted = cur.fetchone()
        if not deleted:
            return jsonify({"success": False, "error": "证照记录不存在。"}), 404

        conn.commit()
        return jsonify({"success": True, "message": "证照记录已删除。"})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
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
                s.station_type,
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
                s.station_type,
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
            SELECT
                CONCAT('issue-create-', i.id) AS id,
                s.id AS "stationId",
                s.station_name AS "stationName",
                CONCAT('【', t.table_name, '】新增问题，规范ID：', i.standard_id, '，当前状态：', i.status, '。') AS text,
                TO_CHAR(COALESCE(i.created_at, NOW()), 'HH24:MI') AS time,
                CASE
                    WHEN i.status = '待整改' THEN 'danger'
                    WHEN i.status = '待复核' THEN 'warning'
                    ELSE 'info'
                END AS level,
                COALESCE(i.created_at, NOW()) AS sort_time
            FROM issues i
            JOIN stations s ON s.id = i.station_id
            JOIN inspection_tables t ON t.id = i.inspection_table_id
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


@app.route("/api/training-materials", methods=["GET"])
def get_training_materials():
    user_id = str(request.args.get("user_id", "")).strip()
    if not user_id:
        return jsonify({"success": False, "error": "缺少用户信息。"}), 400

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_training_materials_table(cur)
        conn.commit()

        user = get_user_by_id(cur, user_id)
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        if user["role"] != "supervisor":
            return jsonify({"success": False, "error": "当前账号无权访问培训材料库。"}), 403

        cur.execute(
            """
            SELECT
                tm.id,
                tm.title,
                tm.file_type,
                tm.file_path,
                tm.original_filename,
                tm.file_size,
                tm.uploaded_by,
                TO_CHAR(tm.created_at, 'YYYY-MM-DD HH24:MI') AS created_at,
                TO_CHAR(tm.updated_at, 'YYYY-MM-DD HH24:MI') AS updated_at,
                uploader.username AS uploaded_by_username,
                uploader.real_name AS uploaded_by_real_name
            FROM training_materials tm
            LEFT JOIN users uploader ON uploader.id = tm.uploaded_by
            ORDER BY tm.updated_at DESC, tm.id DESC;
            """
        )
        rows = cur.fetchall()
        items = []
        for row in rows:
            file_path = row.get("file_path")
            items.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "file_type": row["file_type"],
                    "file_path": file_path,
                    "file_url": f"/storage{file_path}" if file_path else "",
                    "original_filename": row["original_filename"],
                    "file_size": row["file_size"],
                    "uploaded_by": row["uploaded_by"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "uploaded_by_username": row["uploaded_by_username"],
                    "uploaded_by_real_name": row["uploaded_by_real_name"],
                    "can_edit": can_edit_training_material(user, row),
                    "can_delete": can_delete_training_material(user, row),
                }
            )

        return jsonify(
            {
                "success": True,
                "can_upload": can_upload_training_materials(user),
                "can_delete_any": can_delete_any_training_material(user),
                "items": items,
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/training-materials", methods=["POST"])
def create_training_material():
    user_id = str(request.form.get("user_id", "")).strip()
    title = str(request.form.get("title", "")).strip()
    material_file = request.files.get("file")

    if not user_id:
        return jsonify({"success": False, "error": "缺少用户信息。"}), 400
    if not title:
        return jsonify({"success": False, "error": "请填写培训材料标题。"}), 400
    if len(title) > 120:
        return jsonify({"success": False, "error": "标题不能超过 120 个字符。"}), 400

    new_file_path = None
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_training_materials_table(cur)

        user = get_user_by_id(cur, user_id)
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404
        if not can_upload_training_materials(user):
            return jsonify({"success": False, "error": "只有督导组账号可以上传培训材料。"}), 403

        new_file_path, original_filename, file_size, file_type = save_training_material_file(material_file)
        cur.execute(
            """
            INSERT INTO training_materials (
                title,
                file_type,
                file_path,
                original_filename,
                file_size,
                uploaded_by,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id;
            """,
            (title, file_type, new_file_path, original_filename, file_size, user["id"]),
        )
        row = cur.fetchone()
        conn.commit()
        return jsonify(
            {
                "success": True,
                "message": "培训材料已上传。",
                "id": row["id"],
            }
        )
    except ValueError as exc:
        if conn:
            conn.rollback()
        if new_file_path:
            remove_storage_file(new_file_path)
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        if new_file_path:
            remove_storage_file(new_file_path)
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/training-materials/<int:material_id>", methods=["PUT"])
def update_training_material(material_id):
    user_id = str(request.form.get("user_id", "")).strip()
    title = str(request.form.get("title", "")).strip()
    material_file = request.files.get("file")

    if not user_id:
        return jsonify({"success": False, "error": "缺少用户信息。"}), 400
    if not title:
        return jsonify({"success": False, "error": "请填写培训材料标题。"}), 400
    if len(title) > 120:
        return jsonify({"success": False, "error": "标题不能超过 120 个字符。"}), 400

    new_file_path = None
    old_file_path = None
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_training_materials_table(cur)

        user = get_user_by_id(cur, user_id)
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404
        if user["role"] != "supervisor":
            return jsonify({"success": False, "error": "当前账号无权维护培训材料。"}), 403

        cur.execute(
            """
            SELECT id, uploaded_by, file_path
            FROM training_materials
            WHERE id = %s
            LIMIT 1;
            """,
            (material_id,),
        )
        material = cur.fetchone()
        if not material:
            return jsonify({"success": False, "error": "培训材料不存在。"}), 404
        if not can_edit_training_material(user, material):
            return jsonify({"success": False, "error": "只能编辑自己上传的培训材料。"}), 403

        old_file_path = material["file_path"]
        if material_file and material_file.filename:
            new_file_path, original_filename, file_size, file_type = save_training_material_file(material_file)
            cur.execute(
                """
                UPDATE training_materials
                SET title = %s,
                    file_type = %s,
                    file_path = %s,
                    original_filename = %s,
                    file_size = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s;
                """,
                (title, file_type, new_file_path, original_filename, file_size, material_id),
            )
        else:
            cur.execute(
                """
                UPDATE training_materials
                SET title = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s;
                """,
                (title, material_id),
            )

        conn.commit()
        if new_file_path and old_file_path and old_file_path != new_file_path:
            remove_storage_file(old_file_path)

        return jsonify({"success": True, "message": "培训材料已更新。"})
    except ValueError as exc:
        if conn:
            conn.rollback()
        if new_file_path:
            remove_storage_file(new_file_path)
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        if new_file_path:
            remove_storage_file(new_file_path)
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/training-materials/<int:material_id>", methods=["DELETE"])
def delete_training_material(material_id):
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id") or request.args.get("user_id", "")).strip()

    if not user_id:
        return jsonify({"success": False, "error": "缺少用户信息。"}), 400

    old_file_path = None
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_training_materials_table(cur)

        user = get_user_by_id(cur, user_id)
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404
        if user["role"] != "supervisor":
            return jsonify({"success": False, "error": "当前账号无权删除培训材料。"}), 403

        cur.execute(
            """
            SELECT id, uploaded_by, file_path
            FROM training_materials
            WHERE id = %s
            LIMIT 1;
            """,
            (material_id,),
        )
        material = cur.fetchone()
        if not material:
            return jsonify({"success": False, "error": "培训材料不存在。"}), 404
        if not can_delete_training_material(user, material):
            return jsonify({"success": False, "error": "只能删除自己上传的培训材料。"}), 403

        old_file_path = material["file_path"]
        cur.execute("DELETE FROM training_materials WHERE id = %s;", (material_id,))
        conn.commit()
        remove_storage_file(old_file_path)
        return jsonify({"success": True, "message": "培训材料已删除。"})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/inspection-table-originals", methods=["GET"])
def get_inspection_table_originals():
    user_id = str(request.args.get("user_id", "")).strip()
    if not user_id:
        return jsonify({"success": False, "error": "缺少用户信息。"}), 400

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_inspection_table_original_files_table(cur)
        conn.commit()

        user = get_user_by_id(cur, user_id)
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        cur.execute(
            """
            SELECT
                it.id AS inspection_table_id,
                it.table_code,
                it.table_name,
                it.description,
                it.is_active,
                doc.id AS document_id,
                doc.file_path,
                doc.original_filename,
                doc.file_size,
                TO_CHAR(doc.created_at, 'YYYY-MM-DD HH24:MI') AS created_at,
                TO_CHAR(doc.updated_at, 'YYYY-MM-DD HH24:MI') AS updated_at,
                uploader.username AS uploaded_by_username,
                uploader.real_name AS uploaded_by_real_name
            FROM inspection_tables it
            LEFT JOIN inspection_table_original_files doc
              ON doc.inspection_table_id = it.id
            LEFT JOIN users uploader
              ON uploader.id = doc.uploaded_by
            WHERE it.is_active = TRUE
            ORDER BY it.id ASC;
            """
        )
        rows = cur.fetchall()

        items = []
        for row in rows:
            file_path = row.get("file_path")
            items.append(
                {
                    "inspection_table_id": row["inspection_table_id"],
                    "table_code": row["table_code"],
                    "table_name": row["table_name"],
                    "description": row["description"],
                    "is_active": row["is_active"],
                    "document_id": row["document_id"],
                    "has_pdf": bool(file_path),
                    "file_path": file_path,
                    "file_url": f"/storage{file_path}" if file_path else "",
                    "original_filename": row["original_filename"],
                    "file_size": row["file_size"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "uploaded_by_username": row["uploaded_by_username"],
                    "uploaded_by_real_name": row["uploaded_by_real_name"],
                }
            )

        return jsonify(
            {
                "success": True,
                "can_manage": can_manage_checklist_originals(user),
                "items": items,
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route(
    "/api/inspection-table-originals/<int:inspection_table_id>/pdf",
    methods=["POST"],
)
def upload_inspection_table_original_pdf(inspection_table_id):
    user_id = str(request.form.get("user_id", "")).strip()
    if not user_id:
        return jsonify({"success": False, "error": "缺少用户信息。"}), 400

    pdf_file = request.files.get("pdf") or request.files.get("file")
    new_file_path = None
    old_file_path = None
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_inspection_table_original_files_table(cur)

        user = get_user_by_id(cur, user_id)
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        if not can_manage_checklist_originals(user):
            return jsonify({"success": False, "error": "当前账号无权上传检查表原件。"}), 403

        cur.execute(
            """
            SELECT id, table_name
            FROM inspection_tables
            WHERE id = %s AND is_active = TRUE
            LIMIT 1;
            """,
            (inspection_table_id,),
        )
        inspection_table = cur.fetchone()
        if not inspection_table:
            return jsonify({"success": False, "error": "检查表不存在或未启用。"}), 404

        cur.execute(
            """
            SELECT file_path
            FROM inspection_table_original_files
            WHERE inspection_table_id = %s
            LIMIT 1;
            """,
            (inspection_table_id,),
        )
        old_row = cur.fetchone()
        old_file_path = old_row["file_path"] if old_row else None

        new_file_path, original_filename, file_size = save_inspection_original_pdf(pdf_file)
        cur.execute(
            """
            INSERT INTO inspection_table_original_files (
                inspection_table_id,
                file_path,
                original_filename,
                file_size,
                uploaded_by,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (inspection_table_id)
            DO UPDATE SET
                file_path = EXCLUDED.file_path,
                original_filename = EXCLUDED.original_filename,
                file_size = EXCLUDED.file_size,
                uploaded_by = EXCLUDED.uploaded_by,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id;
            """,
            (
                inspection_table_id,
                new_file_path,
                original_filename,
                file_size,
                user["id"],
            ),
        )
        row = cur.fetchone()
        conn.commit()

        if old_file_path and old_file_path != new_file_path:
            remove_storage_file(old_file_path)

        return jsonify(
            {
                "success": True,
                "message": f"【{inspection_table['table_name']}】原件 PDF 已更新。",
                "document_id": row["id"],
                "file_path": new_file_path,
                "file_url": f"/storage{new_file_path}",
            }
        )
    except ValueError as exc:
        if conn:
            conn.rollback()
        if new_file_path:
            remove_storage_file(new_file_path)
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        if new_file_path:
            remove_storage_file(new_file_path)
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


# 新增 inspection-tables API
@app.route("/api/inspection-tables")
def get_inspection_tables():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id,
                table_code,
                table_name,
                description,
                is_active
            FROM inspection_tables
            WHERE is_active = TRUE
            ORDER BY id;
            """
        )
        rows = cur.fetchall()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/inspection-table-fields")
def get_inspection_table_fields():
    table_id = str(request.args.get("table_id", "")).strip()

    if not table_id:
        return jsonify({"success": False, "error": "缺少检查表信息。"}), 400

    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                f.id,
                f.inspection_table_id,
                f.field_key,
                f.field_label,
                f.is_filterable,
                f.sort_order
            FROM inspection_table_fields f
            JOIN inspection_tables t ON f.inspection_table_id = t.id
            WHERE f.inspection_table_id = %s
              AND t.is_active = TRUE
            ORDER BY f.sort_order ASC, f.id ASC;
            """,
            (table_id,),
        )
        rows = cur.fetchall()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


# 新增：获取检查表规范（标准）API
@app.route("/api/inspection-table-standards")
def get_inspection_table_standards():
    table_id = str(request.args.get("table_id", "")).strip()
    keyword = str(request.args.get("keyword", "")).strip().lower()

    if not table_id:
        return jsonify({"success": False, "error": "缺少检查表信息。"}), 400

    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        inspection_table = get_inspection_table_record(cur, table_id)
        if not inspection_table:
            return jsonify({"success": False, "error": "检查表不存在。"}), 404

        if not inspection_table["is_active"]:
            return jsonify({"success": False, "error": "检查表未启用。"}), 400

        physical_table_name = get_physical_table_name_by_code(
            inspection_table["table_code"]
        )
        field_meta = get_checklist_field_meta(cur, inspection_table["id"])
        if not physical_table_name:
            return jsonify({"success": False, "error": "检查表未配置物理表映射。"}), 400

        cur.execute(
            sql.SQL("SELECT * FROM {} ORDER BY standard_id ASC;").format(
                sql.Identifier(physical_table_name)
            )
        )
        rows = cur.fetchall()

        filters = {
            key: str(value).strip().lower()
            for key, value in request.args.items()
            if key not in {"table_id", "keyword"} and str(value).strip()
        }

        result = []
        for row in rows:
            item = serialize_standard_row(field_meta, row)
            haystack = "\n".join(
                [str(v).strip() for v in item.values() if v is not None]
            ).lower()
            if keyword and keyword not in haystack:
                continue

            matched = True
            for field_key, field_value in filters.items():
                raw_value = row.get(field_key)
                raw_text = "" if raw_value is None else str(raw_value).strip().lower()
                if field_value not in raw_text:
                    matched = False
                    break

            if matched:
                result.append(item)

        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/inspection-plan-overview")
def get_inspection_plan_overview():
    user_id = str(request.args.get("user_id", "")).strip()
    inspection_table_id = str(request.args.get("inspection_table_id", "")).strip()
    coverage_type = str(request.args.get("coverage_type", "")).strip()
    period_key = str(request.args.get("period_key", "")).strip()

    if not inspection_table_id:
        return jsonify({"success": False, "error": "缺少检查表信息。"}), 400

    if coverage_type not in {"monthly", "quarterly", "yearly"}:
        return jsonify({"success": False, "error": "覆盖要求参数不合法。"}), 400

    if not period_key:
        return jsonify({"success": False, "error": "缺少周期标识。"}), 400

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        if user_id:
            user = get_user_by_id(cur, user_id)
            if not user:
                return jsonify({"success": False, "error": "用户不存在。"}), 404

        cur.execute(
            """
            SELECT
                pc.id,
                pc.inspection_table_id,
                it.table_name AS inspection_table_name,
                pc.coverage_type,
                pc.period_key,
                pc.status,
                pc.remark,
                creator.username AS created_by_username,
                updater.username AS updated_by_username,
                pc.created_at,
                pc.updated_at
            FROM inspection_plan_configs pc
            JOIN inspection_tables it ON pc.inspection_table_id = it.id
            JOIN users creator ON pc.created_by = creator.id
            LEFT JOIN users updater ON pc.updated_by = updater.id
            WHERE pc.inspection_table_id = %s
              AND pc.coverage_type = %s
              AND pc.period_key = %s
            LIMIT 1;
            """,
            (inspection_table_id, coverage_type, period_key),
        )
        config_row = cur.fetchone()

        if not config_row:
            return (
                jsonify({"success": False, "error": "未找到对应的巡检计划配置。"}),
                404,
            )

        cur.execute(
            """
            SELECT
                psi.id,
                psi.station_id,
                s.station_name,
                s.region,
                s.address,
                psi.is_included,
                psi.completion_status,
                psi.completed_inspection_id,
                TO_CHAR(psi.completed_at, 'YYYY-MM-DD HH24:MI') AS completed_at,
                psi.note
            FROM inspection_plan_station_items psi
            JOIN stations s ON psi.station_id = s.id
            WHERE psi.plan_config_id = %s
            ORDER BY s.id ASC;
            """,
            (config_row["id"],),
        )
        station_rows = cur.fetchall()

        included_count = sum(1 for row in station_rows if row["is_included"])
        completed_count = sum(
            1
            for row in station_rows
            if row["is_included"] and row["completion_status"] == "completed"
        )
        pending_count = sum(
            1
            for row in station_rows
            if row["is_included"] and row["completion_status"] == "pending"
        )
        completion_rate = (
            round((completed_count / included_count) * 100) if included_count > 0 else 0
        )

        return jsonify(
            {
                "success": True,
                "item": {
                    "id": config_row["id"],
                    "inspection_table_id": config_row["inspection_table_id"],
                    "inspection_table_name": config_row["inspection_table_name"],
                    "coverage_type": config_row["coverage_type"],
                    "coverage_type_label": COVERAGE_TYPE_LABELS.get(
                        config_row["coverage_type"], config_row["coverage_type"]
                    ),
                    "period_key": config_row["period_key"],
                    "status": config_row["status"],
                    "remark": config_row["remark"],
                    "created_by_username": config_row["created_by_username"],
                    "updated_by_username": config_row["updated_by_username"],
                    "included_station_count": included_count,
                    "completed_station_count": completed_count,
                    "pending_station_count": pending_count,
                    "completion_rate": completion_rate,
                    "created_at": config_row["created_at"],
                    "updated_at": config_row["updated_at"],
                    "stations": station_rows,
                },
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/inspection-register", methods=["POST"])
def inspection_register():
    inspector_id = str(request.form.get("inspector_id", "")).strip()
    station_id = str(request.form.get("station_id", "")).strip()
    inspection_table_id = str(request.form.get("inspection_table_id", "")).strip()
    has_issue = str(request.form.get("has_issue", "yes")).strip().lower()
    standard_id = str(request.form.get("standard_id", "")).strip()
    description = str(request.form.get("description", "")).strip()
    photo = request.files.get("photo")

    if not inspector_id:
        return jsonify({"success": False, "error": "缺少巡检人信息。"}), 400

    if not station_id:
        return jsonify({"success": False, "error": "请选择站点名称。"}), 400

    if not inspection_table_id:
        return jsonify({"success": False, "error": "请选择检查表。"}), 400

    if has_issue not in {"yes", "no"}:
        return jsonify({"success": False, "error": "是否发现问题参数不合法。"}), 400

    if has_issue == "yes" and not standard_id:
        return jsonify({"success": False, "error": "请选择规范。"}), 400

    if has_issue == "yes" and not description:
        return jsonify({"success": False, "error": "请填写实际问题描述。"}), 400

    if has_issue == "yes" and (not photo or not photo.filename):
        return jsonify({"success": False, "error": "请上传问题照片。"}), 400

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

        inspection_table = get_inspection_table_record(cur, inspection_table_id)
        if not inspection_table:
            return jsonify({"success": False, "error": "检查表不存在。"}), 404

        if not inspection_table["is_active"]:
            return jsonify({"success": False, "error": "检查表未启用。"}), 400

        physical_table_name = get_physical_table_name_by_code(
            inspection_table["table_code"]
        )
        field_meta = get_checklist_field_meta(cur, inspection_table["id"])
        if not physical_table_name:
            return jsonify({"success": False, "error": "检查表未配置物理表映射。"}), 400

        today = beijing_today()

        batch_id = get_or_create_inspection_batch(cur, station_id, inspector_id, today)

        cur.execute(
            """
            SELECT ins.id, ins.sign_status
            FROM inspections ins
            WHERE ins.station_id = %s
              AND ins.inspection_table_id = %s
              AND ins.inspection_date = %s
              AND ins.batch_id = %s
            ORDER BY ins.id ASC;
            """,
            (station_id, inspection_table_id, today, batch_id),
        )
        existing_inspections = cur.fetchall()

        existing_inspection_ids = [row["id"] for row in existing_inspections]

        if existing_inspections and any(
            row.get("sign_status") == "已签名确认" for row in existing_inspections
        ):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "该站点当天该检查表已完成签名确认，不能继续登记。",
                    }
                ),
                400,
            )

        if existing_inspection_ids:
            cur.execute(
                """
                SELECT COUNT(*) AS issue_count
                FROM issues
                WHERE inspection_id = ANY(%s);
                """,
                (existing_inspection_ids,),
            )
            existing_issue_row = cur.fetchone()
            existing_issue_count = int(existing_issue_row["issue_count"] or 0)

            if has_issue == "no":
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "该站点当天该检查表已提交过巡检结果，不能重复提交“未发现问题”。",
                        }
                    ),
                    400,
                )

            if has_issue == "yes" and existing_issue_count == 0:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "该站点当天该检查表已提交“未发现问题”，不能再提交“发现问题”。",
                        }
                    ),
                    400,
                )

        if existing_inspection_ids:
            inspection_id = existing_inspection_ids[0]
        else:
            inspection_id = create_inspection_record(
                cur,
                station_id,
                inspector_id,
                inspection_table_id,
                batch_id,
            )

        if has_issue == "no":
            mark_related_plan_items_completed(
                cur,
                station_id,
                inspection_table_id,
                inspection_id,
                today,
            )
            conn.commit()
            return jsonify(
                {
                    "success": True,
                    "message": "巡检记录提交成功，未发现问题。",
                    "inspection_id": inspection_id,
                    "issue_id": None,
                }
            )

        standard = fetch_standard_from_table(
            cur,
            physical_table_name,
            standard_id,
        )
        if not standard:
            return jsonify({"success": False, "error": "所选规范不存在。"}), 404

        standard_detail_text = build_standard_detail_text(
            field_meta,
            standard,
        )
        if not standard_detail_text:
            return jsonify({"success": False, "error": "规范详情生成失败。"}), 400

        photo_path = save_uploaded_file(photo, "issues")

        cur.execute(
            """
            INSERT INTO issues (
                inspection_id,
                station_id,
                inspection_table_id,
                standard_id,
                standard_detail_text,
                description,
                photo_path,
                status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (
                inspection_id,
                station_id,
                inspection_table_id,
                standard_id,
                standard_detail_text,
                description,
                photo_path,
                "待整改",
            ),
        )
        issue = cur.fetchone()

        mark_related_plan_items_completed(
            cur,
            station_id,
            inspection_table_id,
            inspection_id,
            today,
        )
        conn.commit()
        return jsonify(
            {
                "success": True,
                "message": "巡检问题登记成功。",
                "inspection_id": inspection_id,
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
                    t.table_name AS inspection_table_name,
                    i.standard_id,
                    i.standard_detail_text,
                    i.description,
                    i.photo_path AS issue_photo,
                    i.rectification_result,
                    i.rectification_note,
                    i.rectification_photo_path AS rectification_photo,
                    i.review_result,
                    i.review_note,
                    i.review_photo_path AS review_photo,
                    i.status,
                    ins.sign_status AS inspection_sign_status
                FROM issues i
                JOIN inspections ins ON i.inspection_id = ins.id
                JOIN stations s ON i.station_id = s.id
                JOIN inspection_tables t ON i.inspection_table_id = t.id
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
                    t.table_name AS inspection_table_name,
                    i.standard_id,
                    i.standard_detail_text,
                    i.description,
                    i.photo_path AS issue_photo,
                    i.rectification_result,
                    i.rectification_note,
                    i.rectification_photo_path AS rectification_photo,
                    i.review_result,
                    i.review_note,
                    i.review_photo_path AS review_photo,
                    i.status,
                    ins.sign_status AS inspection_sign_status
                FROM issues i
                JOIN inspections ins ON i.inspection_id = ins.id
                JOIN stations s ON i.station_id = s.id
                JOIN inspection_tables t ON i.inspection_table_id = t.id
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


@app.route("/api/issues")
def get_issues():
    user_id = str(request.args.get("user_id", "")).strip()

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        user = None
        where_clause = ""
        params = []

        if user_id:
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

        if user and user["role"] == "station_manager":
            if not user["station_id"]:
                return jsonify([])
            where_clause = "WHERE i.station_id = %s"
            params.append(user["station_id"])

        cur.execute(
            sql.SQL(
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
                    t.table_name AS inspection_table_name,
                    i.standard_id,
                    i.standard_detail_text,
                    i.description,
                    i.photo_path AS issue_photo,
                    i.rectification_result,
                    i.rectification_note,
                    i.rectification_photo_path AS rectification_photo,
                    i.review_result,
                    i.review_note,
                    i.review_photo_path AS review_photo,
                    i.status
                FROM issues i
                JOIN inspections ins ON i.inspection_id = ins.id
                JOIN stations s ON i.station_id = s.id
                JOIN inspection_tables t ON i.inspection_table_id = t.id
                JOIN users inspector ON ins.inspector_id = inspector.id
                {where_clause}
                ORDER BY i.id DESC;
                """
            ).format(where_clause=sql.SQL(where_clause)),
            params,
        )
        rows = cur.fetchall()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/inspection-plan-configs", methods=["POST"])
def create_inspection_plan_config():
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    inspection_table_id = str(data.get("inspection_table_id", "")).strip()
    coverage_type = str(data.get("coverage_type", "")).strip()
    period_key = str(data.get("period_key", "")).strip()
    remark = str(data.get("remark", "")).strip() or None
    status = "active"

    if not user_id:
        return jsonify({"success": False, "error": "缺少用户信息。"}), 400

    if not inspection_table_id:
        return jsonify({"success": False, "error": "缺少检查表信息。"}), 400

    if coverage_type not in {"monthly", "quarterly", "yearly"}:
        return jsonify({"success": False, "error": "覆盖要求参数不合法。"}), 400

    if not period_key:
        return jsonify({"success": False, "error": "缺少周期标识。"}), 400

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        user = get_user_by_id(cur, user_id)
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        if not can_manage_plan(user):
            return (
                jsonify({"success": False, "error": "当前账号无权维护巡检计划。"}),
                403,
            )

        cur.execute(
            """
            SELECT id, table_name, is_active
            FROM inspection_tables
            WHERE id = %s
            LIMIT 1;
            """,
            (inspection_table_id,),
        )
        inspection_table = cur.fetchone()

        if not inspection_table:
            return jsonify({"success": False, "error": "检查表不存在。"}), 404

        if not inspection_table["is_active"]:
            return jsonify({"success": False, "error": "检查表未启用。"}), 400

        cur.execute(
            """
            DELETE FROM inspection_plan_configs
            WHERE inspection_table_id = %s
              AND coverage_type <> %s;
            """,
            (inspection_table_id, coverage_type),
        )

        cur.execute(
            """
            SELECT id
            FROM inspection_plan_configs
            WHERE inspection_table_id = %s
              AND coverage_type = %s
              AND period_key = %s
            LIMIT 1;
            """,
            (inspection_table_id, coverage_type, period_key),
        )
        existing = cur.fetchone()

        if existing:
            conn.commit()
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "该检查表在当前覆盖要求与周期下已存在计划配置。",
                        "existing_id": existing["id"],
                    }
                ),
                409,
            )

        cur.execute(
            """
            INSERT INTO inspection_plan_configs (
                inspection_table_id,
                coverage_type,
                period_key,
                created_by,
                updated_by,
                status,
                remark,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            RETURNING id;
            """,
            (
                inspection_table_id,
                coverage_type,
                period_key,
                user_id,
                user_id,
                status,
                remark,
            ),
        )
        created_row = cur.fetchone()
        sync_plan_station_items_completion_by_history(cur, created_row["id"])
        conn.commit()

        return jsonify(
            {
                "success": True,
                "message": "巡检计划配置创建成功。",
                "plan_config_id": created_row["id"],
            }
        )
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/inspection-plan-configs/<int:plan_config_id>", methods=["PUT"])
def update_inspection_plan_config(plan_config_id):
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    coverage_type = str(data.get("coverage_type", "")).strip()
    period_key = str(data.get("period_key", "")).strip()
    remark = data.get("remark")

    if not user_id:
        return jsonify({"success": False, "error": "缺少用户信息。"}), 400

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        user = get_user_by_id(cur, user_id)
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        if not can_manage_plan(user):
            return (
                jsonify({"success": False, "error": "当前账号无权维护巡检计划。"}),
                403,
            )

        cur.execute(
            """
            SELECT id, inspection_table_id, coverage_type, period_key, status, remark
            FROM inspection_plan_configs
            WHERE id = %s
            LIMIT 1;
            """,
            (plan_config_id,),
        )
        current_row = cur.fetchone()

        if not current_row:
            return jsonify({"success": False, "error": "巡检计划配置不存在。"}), 404

        new_coverage_type = coverage_type or current_row["coverage_type"]
        new_period_key = period_key or current_row["period_key"]
        new_status = "active"
        new_remark = (
            current_row["remark"] if remark is None else (str(remark).strip() or None)
        )

        if new_coverage_type not in {"monthly", "quarterly", "yearly"}:
            return jsonify({"success": False, "error": "覆盖要求参数不合法。"}), 400

        if not new_period_key:
            return jsonify({"success": False, "error": "缺少周期标识。"}), 400

        cur.execute(
            """
            SELECT id
            FROM inspection_plan_configs
            WHERE inspection_table_id = %s
              AND coverage_type = %s
              AND period_key = %s
              AND id <> %s
            LIMIT 1;
            """,
            (
                current_row["inspection_table_id"],
                new_coverage_type,
                new_period_key,
                plan_config_id,
            ),
        )
        duplicate_row = cur.fetchone()

        if duplicate_row:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "更新后会与现有计划配置重复。",
                        "existing_id": duplicate_row["id"],
                    }
                ),
                409,
            )

        cur.execute(
            """
            DELETE FROM inspection_plan_configs
            WHERE inspection_table_id = %s
              AND coverage_type <> %s
              AND id <> %s;
            """,
            (current_row["inspection_table_id"], new_coverage_type, plan_config_id),
        )

        cur.execute(
            """
            UPDATE inspection_plan_configs
            SET coverage_type = %s,
                period_key = %s,
                status = %s,
                remark = %s,
                updated_by = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
            """,
            (
                new_coverage_type,
                new_period_key,
                new_status,
                new_remark,
                user_id,
                plan_config_id,
            ),
        )

        sync_plan_station_items_completion_by_history(cur, plan_config_id)
        conn.commit()
        return jsonify({"success": True, "message": "巡检计划配置更新成功。"})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/inspection-plan-configs/<int:plan_config_id>", methods=["DELETE"])
def delete_inspection_plan_config(plan_config_id):
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id") or request.args.get("user_id", "")).strip()

    if not user_id:
        return jsonify({"success": False, "error": "缺少用户信息。"}), 400

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        user = get_user_by_id(cur, user_id)
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        if not can_manage_plan(user):
            return (
                jsonify({"success": False, "error": "当前账号无权维护巡检计划。"}),
                403,
            )

        cur.execute(
            """
            SELECT id
            FROM inspection_plan_configs
            WHERE id = %s
            LIMIT 1;
            """,
            (plan_config_id,),
        )
        current_row = cur.fetchone()

        if not current_row:
            return jsonify({"success": False, "error": "巡检计划配置不存在。"}), 404

        cur.execute(
            "DELETE FROM inspection_plan_configs WHERE id = %s;",
            (plan_config_id,),
        )

        conn.commit()
        return jsonify({"success": True, "message": "巡检计划删除成功。"})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


# 新增巡检记录接口
@app.route("/api/inspections")
def get_inspections():
    user_id = str(request.args.get("user_id", "")).strip()

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        user = None
        where_clause = ""
        params = []

        if user_id:
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

        if user and user["role"] == "station_manager":
            if not user["station_id"]:
                return jsonify([])
            where_clause = "WHERE ins.station_id = %s"
            params.append(user["station_id"])

        cur.execute(
            sql.SQL(
                """
                SELECT
                    ins.id AS id,
                    ins.batch_id AS batch_id,
                    TO_CHAR(ins.inspection_date, 'YYYY-MM-DD') AS date,
                    s.station_name AS station,
                    t.table_name AS inspection_table_name,
                    CASE
                        WHEN COUNT(i.id) > 0 THEN '异常'
                        ELSE '正常'
                    END AS result,
                    COUNT(i.id) AS issue_count,
                    ins.sign_status,
                    ins.station_manager_signed_name,
                    ins.station_manager_signature_path,
                    TO_CHAR(ins.station_manager_signed_at, 'YYYY-MM-DD HH24:MI') AS station_manager_signed_at
                FROM inspections ins
                JOIN stations s ON ins.station_id = s.id
                JOIN inspection_tables t ON ins.inspection_table_id = t.id
                LEFT JOIN issues i ON ins.id = i.inspection_id
                {where_clause}
                GROUP BY
                    ins.id,
                    ins.batch_id,
                    ins.inspection_date,
                    s.station_name,
                    t.table_name,
                    ins.sign_status,
                    ins.station_manager_signed_name,
                    ins.station_manager_signature_path,
                    ins.station_manager_signed_at
                ORDER BY ins.inspection_date DESC, ins.id DESC;
                """
            ).format(where_clause=sql.SQL(where_clause)),
            params,
        )
        rows = cur.fetchall()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    finally:
        close_db_resources(cur, conn)


# === 新增：本检查表录入问题简要信息 API ===
@app.route("/api/inspections/<int:inspection_id>/issues")
def get_inspection_issues(inspection_id):
    user_id = str(request.args.get("user_id", "")).strip()

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        user = None
        if user_id:
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

        cur.execute(
            """
            SELECT
                ins.id,
                ins.station_id,
                ins.batch_id,
                ins.inspection_date,
                ins.sign_status,
                ins.station_manager_signed_name,
                ins.station_manager_signature_path,
                TO_CHAR(ins.station_manager_signed_at, 'YYYY-MM-DD HH24:MI') AS station_manager_signed_at,
                s.station_name,
                t.table_name AS inspection_table_name
            FROM inspections ins
            JOIN stations s ON ins.station_id = s.id
            JOIN inspection_tables t ON ins.inspection_table_id = t.id
            WHERE ins.id = %s
            LIMIT 1;
            """,
            (inspection_id,),
        )
        inspection = cur.fetchone()

        if not inspection:
            return jsonify({"success": False, "error": "巡检记录不存在。"}), 404

        if (
            user
            and user["role"] == "station_manager"
            and inspection["station_id"] != user["station_id"]
        ):
            return jsonify({"success": False, "error": "无权查看该检查表内容。"}), 403

        cur.execute(
            """
            SELECT
                i.id,
                t.table_name AS inspection_table_name,
                i.description,
                i.photo_path AS issue_photo
            FROM issues i
            JOIN inspection_tables t ON i.inspection_table_id = t.id
            WHERE i.inspection_id = %s
            ORDER BY i.id ASC;
            """,
            (inspection_id,),
        )
        issues = cur.fetchall()

        return jsonify(
            {
                "success": True,
                "inspection": inspection,
                "issues": issues,
            }
        )
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
            SELECT
                i.id,
                i.station_id,
                i.status,
                i.inspection_id,
                ins.sign_status AS inspection_sign_status
            FROM issues i
            JOIN inspections ins ON i.inspection_id = ins.id
            WHERE i.id = %s
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

        if issue["inspection_sign_status"] != "已签名确认":
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "当前问题所属检查表尚未完成站经理签名确认，暂不可提交整改。",
                    }
                ),
                400,
            )

        if issue["status"] != "待整改":
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "当前问题状态不是待整改，不能重复提交整改。",
                    }
                ),
                400,
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
    review_photo = request.files.get("review_photo")

    if not user_id:
        return jsonify({"success": False, "error": "缺少用户信息。"}), 400

    if not review_result:
        return jsonify({"success": False, "error": "请选择督导组复核结果。"}), 400

    if not review_note:
        return jsonify({"success": False, "error": "请填写复核说明。"}), 400

    if not review_photo or not review_photo.filename:
        return jsonify({"success": False, "error": "请上传复核照片。"}), 400

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

        if issue["status"] != "待复核":
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "当前问题状态不是待复核，不能提交复核。",
                    }
                ),
                400,
            )

        new_status = "已闭环" if review_result == "已整改" else "待整改"
        review_photo_path = save_uploaded_file(review_photo, "rectifications")

        cur.execute(
            """
            UPDATE issues
            SET review_result = %s,
                review_note = %s,
                review_photo_path = %s,
                status = %s
            WHERE id = %s;
            """,
            (
                review_result,
                review_note,
                review_photo_path,
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
