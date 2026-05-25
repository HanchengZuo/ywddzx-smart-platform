from flask import Flask, g, jsonify, request, send_file, send_from_directory
from flask_cors import CORS
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
import zipfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from io import BytesIO
from xml.sax.saxutils import escape as xml_escape
import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from itsdangerous import BadSignature, URLSafeTimedSerializer
from werkzeug.utils import secure_filename
from PIL import Image
from ai_utils import generate_feedback_title, generate_standard_recommendations
from ai_usage import get_ai_pricing_table

try:
    from qcloud_cos import CosConfig, CosS3Client
except Exception:
    CosConfig = None
    CosS3Client = None

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "APP_SECRET_KEY",
    os.environ.get("SECRET_KEY", "ywddzx-smart-platform-dev-secret"),
)
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
FEEDBACK_SCREENSHOTS_STORAGE_DIR = os.path.join(STORAGE_ROOT, "feedback_screenshots")
ISSUE_EXPORTS_STORAGE_DIR = os.path.join(STORAGE_ROOT, "issue_exports")
BACKUP_CONFIG_PATH = os.path.join(STORAGE_ROOT, "backup_config.json")
DEFAULT_BACKUP_DIR = os.path.join(STORAGE_ROOT, "backups")
BACKUP_PREFIX = "ywddzx_full_backup"
LOCAL_BACKUP_FILENAME = f"{BACKUP_PREFIX}_latest.zip"
AUTO_BACKUP_FILENAME = LOCAL_BACKUP_FILENAME
COS_BACKUP_PREFIX = os.environ.get("COS_BACKUP_PREFIX", "ywddzx-full-backups/").strip().strip("/")
COS_BACKUP_RETENTION_COUNT = 3
BEIJING_TZ = ZoneInfo("Asia/Shanghai")
DEFAULT_INITIAL_PASSWORD = "123456"
ISSUE_EXPORT_RETENTION_DAYS = 7
ISSUE_EXPORT_CLEANUP_INTERVAL_SECONDS = 60 * 60
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 32
AUTH_TOKEN_NORMAL_MAX_AGE_SECONDS = int(
    os.environ.get("AUTH_TOKEN_NORMAL_MAX_AGE_SECONDS", str(8 * 60 * 60))
)
AUTH_TOKEN_PRIVILEGED_MAX_AGE_SECONDS = int(
    os.environ.get("AUTH_TOKEN_PRIVILEGED_MAX_AGE_SECONDS", str(4 * 60 * 60))
)
AUTH_TOKEN_SALT = "ywddzx-auth-token-v1"
PRIVILEGED_AUTH_ROLES = {"root", "supervisor"}


CHECKLIST_PHYSICAL_TABLE_PREFIX = "inspection_table_"
CHECKLIST_FIELD_KEY_MAX_LENGTH = 63
CHECKLIST_STANDARD_ID_BLOCK_SIZE = 1000
SCHEMA_MIGRATION_LOCK_KEY = 2026051601
RESERVED_CHECKLIST_FIELD_KEYS = {
    "id",
    "standard_id",
    "created_at",
    "updated_at",
}


def acquire_schema_migration_lock(cur):
    cur.execute("SELECT pg_advisory_xact_lock(%s);", (SCHEMA_MIGRATION_LOCK_KEY,))

# === Permission constants ===
ROLE_OPTIONS = {"root", "supervisor", "station_manager"}
PERMISSION_CATALOG = [
    {
        "key": "view_station_map",
        "name": "查看页面",
        "category": "站点地图",
        "description": "访问地图中心的站点地图页面。",
        "defaults": {"root": True, "supervisor": True, "station_manager": False},
    },
    {
        "key": "submit_inspections",
        "name": "录入巡检问题",
        "category": "巡检登记",
        "description": "访问巡检登记页面，并提交巡检记录和问题。",
        "defaults": {"root": True, "supervisor": True, "station_manager": False},
    },
    {
        "key": "view_inspection_standards",
        "name": "查看页面",
        "category": "巡检规范库",
        "description": "访问业务督导中心自建的内部巡检规范库。",
        "defaults": {"root": True, "supervisor": True, "station_manager": True},
    },
    {
        "key": "view_checklist_originals",
        "name": "查看页面",
        "category": "检查表原件库",
        "description": "查看各检查表原始 PDF 文件。",
        "defaults": {"root": True, "supervisor": True, "station_manager": True},
    },
    {
        "key": "manage_checklist_originals",
        "name": "上传/更新 PDF",
        "category": "检查表原件库",
        "description": "上传检查表原始 PDF，或替换为新版 PDF。",
        "defaults": {"root": True, "supervisor": False, "station_manager": False},
    },
    {
        "key": "view_own_inspection_issues",
        "name": "查看本站数据",
        "category": "巡检问题列表",
        "description": "只查看当前账号所属站点的巡检问题数据。",
        "defaults": {"root": True, "supervisor": False, "station_manager": True},
    },
    {
        "key": "view_all_inspection_issues",
        "name": "查看全部站点数据",
        "category": "巡检问题列表",
        "description": "查看所有站点的巡检问题数据。与“查看本站数据”二选一。",
        "defaults": {"root": True, "supervisor": True, "station_manager": False},
    },
    {
        "key": "edit_inspection_issues",
        "name": "编辑所选范围内问题",
        "category": "巡检问题列表",
        "description": "在已选择的本站/全部站点范围内，编辑巡检问题；已闭环问题仍只有 root 可改。",
        "defaults": {"root": True, "supervisor": False, "station_manager": False},
    },
    {
        "key": "delete_inspection_issues",
        "name": "删除所选范围内问题",
        "category": "巡检问题列表",
        "description": "在已选择的本站/全部站点范围内删除巡检问题，并自动回算关联记录与计划状态。",
        "defaults": {"root": True, "supervisor": False, "station_manager": False},
    },
    {
        "key": "audit_inspection_issues",
        "name": "审核巡检问题",
        "category": "巡检问题列表",
        "description": "对巡检问题判定审核通过或否决；否决后不参与巡检记录统计和问题流转。",
        "defaults": {"root": True, "supervisor": False, "station_manager": False},
    },
    {
        "key": "view_own_inspection_records",
        "name": "查看本站数据",
        "category": "巡检记录",
        "description": "只查看当前账号所属站点的巡检记录数据。",
        "defaults": {"root": True, "supervisor": False, "station_manager": True},
    },
    {
        "key": "view_all_inspection_records",
        "name": "查看全部站点数据",
        "category": "巡检记录",
        "description": "查看所有站点的巡检记录数据。与“查看本站数据”二选一。",
        "defaults": {"root": True, "supervisor": True, "station_manager": False},
    },
    {
        "key": "delete_inspection_records",
        "name": "删除巡检记录",
        "category": "巡检记录",
        "description": "在已选择的站点范围内删除巡检记录，并同步删除本记录下的问题。",
        "defaults": {"root": True, "supervisor": False, "station_manager": False},
    },
    {
        "key": "reset_inspection_signature",
        "name": "重置站经理签名",
        "category": "巡检记录",
        "description": "重置已完成的站经理签名，并将本记录下的问题退回待审核。",
        "defaults": {"root": True, "supervisor": False, "station_manager": False},
    },
    {
        "key": "view_inspection_plans",
        "name": "查看页面",
        "category": "巡检计划",
        "description": "访问巡检计划页面和计划完成情况。",
        "defaults": {"root": True, "supervisor": True, "station_manager": False},
    },
    {
        "key": "manage_inspection_plans",
        "name": "管理巡检计划",
        "category": "巡检计划",
        "description": "新建、编辑、删除检查表巡检计划。",
        "defaults": {"root": True, "supervisor": False, "station_manager": False},
    },
    {
        "key": "view_own_certificates",
        "name": "查看本站数据",
        "category": "站点证照有效期管理",
        "description": "查看当前账号所属站点的证照有效期和到期提醒。",
        "defaults": {"root": True, "supervisor": False, "station_manager": True},
    },
    {
        "key": "edit_own_certificates",
        "name": "编辑本站证照",
        "category": "站点证照有效期管理",
        "description": "仅在选择“查看本站数据”时可用，用于录入、修改、删除当前账号所属站点证照。",
        "defaults": {"root": True, "supervisor": False, "station_manager": True},
    },
    {
        "key": "view_all_certificates",
        "name": "查看全部站点数据",
        "category": "站点证照有效期管理",
        "description": "查看所有站点的证照有效期和到期提醒。与“查看本站数据”二选一。",
        "defaults": {"root": True, "supervisor": True, "station_manager": False},
    },
    {
        "key": "view_assessment",
        "name": "查看页面",
        "category": "考核系统",
        "description": "访问考核系统页面。",
        "defaults": {"root": True, "supervisor": True, "station_manager": False},
    },
    {
        "key": "view_training",
        "name": "查看页面",
        "category": "督导组内部培训系统",
        "description": "访问督导组内部培训系统页面。",
        "defaults": {"root": True, "supervisor": True, "station_manager": False},
    },
    {
        "key": "view_training_materials",
        "name": "查看页面",
        "category": "培训材料库",
        "description": "访问培训材料库并查看材料目录与预览。",
        "defaults": {"root": True, "supervisor": True, "station_manager": False},
    },
    {
        "key": "upload_training_materials",
        "name": "上传/更新自己的材料",
        "category": "培训材料库",
        "description": "上传培训材料，并编辑或删除自己上传的材料。",
        "defaults": {"root": True, "supervisor": True, "station_manager": False},
    },
    {
        "key": "manage_stations",
        "name": "管理站点数据",
        "category": "站点数据管理",
        "description": "访问站点数据管理页面，并新增、编辑、删除、导入导出站点主数据。",
        "defaults": {"root": True, "supervisor": False, "station_manager": False},
    },
    {
        "key": "manage_checklists",
        "name": "管理检查表数据",
        "category": "检查表数据管理",
        "description": "访问检查表数据管理页面，并维护外部检查表、字段结构和外部规范数据。",
        "defaults": {"root": True, "supervisor": False, "station_manager": False},
    },
    {
        "key": "manage_internal_standards",
        "name": "管理内部巡检规范",
        "category": "巡检规范库数据管理",
        "description": "访问巡检规范库数据管理页面，并维护内部规范字段配置和外部规范挂载关系。",
        "defaults": {"root": True, "supervisor": False, "station_manager": False},
    },
    {
        "key": "manage_ai_usage",
        "name": "查看 AI 调用统计",
        "category": "AI调用统计",
        "description": "查看系统内 DeepSeek AI 调用次数、使用位置、字符量、估算 token 和费用。",
        "defaults": {"root": True, "supervisor": False, "station_manager": False},
    },
]
PERMISSION_KEYS = {item["key"] for item in PERMISSION_CATALOG}
PERMISSION_EXCLUSIVE_GROUPS = [
    ("view_own_inspection_issues", "view_all_inspection_issues"),
    ("view_own_inspection_records", "view_all_inspection_records"),
    ("view_own_certificates", "view_all_certificates"),
]
PERMISSION_DEPENDENCIES = {
    "edit_own_certificates": "view_own_certificates",
}
PERMISSION_ANY_DEPENDENCIES = {
    "edit_inspection_issues": (
        "view_all_inspection_issues",
    ),
    "delete_inspection_issues": (
        "view_all_inspection_issues",
    ),
    "audit_inspection_issues": (
        "view_all_inspection_issues",
    ),
    "delete_inspection_records": (
        "view_all_inspection_records",
    ),
    "reset_inspection_signature": (
        "view_all_inspection_records",
    ),
}
STATION_TYPE_OPTIONS = {"加油站", "充电站"}
STATION_ASSET_TYPE_OPTIONS = {"全资", "股权"}
STATION_CONSOLIDATED_OPTIONS = {"是", "否"}
STATION_ONLINE_3_STATUS_OPTIONS = {"上线", "上线参股模式", "未上线"}
STATION_STATUS_OPTIONS = {"营业中", "停业"}
INSPECTION_COMPLETION_PENDING = "待检查人确认"
INSPECTION_COMPLETION_DONE = "已确认完成"
INSPECTION_COMPLETION_SOURCES = {"manual", "auto", "admin", "signature", "admin_reopen"}
DEFAULT_INSPECTION_AUTO_COMPLETE_DAYS = 7
DEFAULT_INSPECTION_RECORD_UNIQUENESS_PERIOD = "month"
INSPECTION_RECORD_UNIQUENESS_PERIODS = {"week", "month", "quarter", "year"}
ISSUE_INSPECTOR_SCHEMA_READY = False
INSPECTION_COMPLETION_SCHEMA_READY = False
ISSUE_STATUS_OPTIONS = {"待整改", "待复核", "已闭环", "站经无法整改"}
ISSUE_RESULT_OPTIONS = {"已整改", "站经无法整改"}
ISSUE_AUDIT_STATUS_OPTIONS = {"pending", "approved", "rejected"}
ISSUE_AUDIT_STATUS_LABELS = {
    "pending": "待审核",
    "approved": "审核通过",
    "rejected": "审核否决",
}
ISSUE_STATUS_ALIASES = {"已整改": "已闭环"}
ISSUE_RESULT_ALIASES = {
    "站级无法完成整改": "站经无法整改",
    "站经理无法整改": "站经无法整改",
}
FEEDBACK_TYPE_OPTIONS = {"功能建议", "Bug反馈", "界面优化", "流程建议", "其他"}
FEEDBACK_MODULE_OPTIONS = {
    "巡检系统",
    "巡检规范库",
    "检查表原件库",
    "巡检计划",
    "考核系统",
    "培训系统",
    "培训材料库",
    "证照管理",
    "车辆管理系统",
    "数据备份管理",
    "用户数据管理",
    "站点数据管理",
    "检查表数据管理",
    "巡检规范库数据管理",
    "AI调用统计",
    "管理系统",
    "公共功能",
    "登录与账号",
    "其他",
}
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
os.makedirs(FEEDBACK_SCREENSHOTS_STORAGE_DIR, exist_ok=True)
os.makedirs(DEFAULT_BACKUP_DIR, exist_ok=True)


def get_db_config():
    return {
        "host": os.environ.get("DB_HOST", "db"),
        "port": str(os.environ.get("DB_PORT", 5432)),
        "dbname": os.environ.get("DB_NAME", "ywddzx"),
        "user": os.environ.get("DB_USER", "postgres"),
        "password": os.environ.get("DB_PASSWORD", "postgres"),
    }


def get_db_connection():
    db_config = get_db_config()
    return psycopg2.connect(
        host=db_config["host"],
        port=db_config["port"],
        dbname=db_config["dbname"],
        user=db_config["user"],
        password=db_config["password"],
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
    elif category == "feedback_screenshots":
        base_dir = FEEDBACK_SCREENSHOTS_STORAGE_DIR
        prefix = "feedback"
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


def normalize_upload_display_name(filename, fallback="检查表原件.pdf"):
    raw_name = str(filename or "").replace("\\", "/").split("/")[-1].strip()
    return raw_name[:180] or fallback


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


BACKUP_FREQUENCY_INTERVALS = {
    "off": None,
    "hourly": timedelta(hours=1),
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
    "monthly": timedelta(days=30),
}
backup_scheduler_started = False
backup_scheduler_lock = threading.Lock()
backup_job_lock = threading.Lock()
issue_export_cleanup_lock = threading.Lock()
issue_export_cleanup_last_run = 0


def isoformat_or_none(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.astimezone(BEIJING_TZ).isoformat()
    return str(value)


def parse_backup_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def normalize_backup_scheduled_time(value):
    text = str(value or "").strip()
    if not text:
        return "02:00"
    matched = re.fullmatch(r"(\d{1,2}):([0-5]\d)", text)
    if not matched:
        raise ValueError("自动备份执行时间必须是 HH:MM 格式。")
    hour = int(matched.group(1))
    if hour > 23:
        raise ValueError("自动备份执行时间小时必须在 00-23 之间。")
    return f"{hour:02d}:{matched.group(2)}"


def parse_backup_scheduled_time(value):
    scheduled_time = normalize_backup_scheduled_time(value)
    hour, minute = scheduled_time.split(":")
    return int(hour), int(minute)


def normalize_backup_destination_path(value):
    raw_value = str(value or "").strip()
    if not raw_value:
        return os.path.abspath(DEFAULT_BACKUP_DIR)
    if os.path.isabs(raw_value):
        return os.path.abspath(raw_value)
    return os.path.abspath(os.path.join(DEFAULT_BACKUP_DIR, raw_value))


def get_default_backup_config():
    return {
        "destination_path": os.path.abspath(DEFAULT_BACKUP_DIR),
        "frequency": "off",
        "scheduled_time": "02:00",
        "next_auto_run_at": None,
        "last_auto_export_at": None,
        "last_backup_path": None,
        "last_backup_size": None,
        "last_cos_status": "not_configured",
        "last_cos_key": None,
        "last_cos_uploaded_at": None,
        "last_cos_retained_count": 0,
        "last_cos_error": "",
        "last_status": "idle",
        "last_error": "",
        "updated_at": None,
    }


def read_backup_config():
    config = get_default_backup_config()
    if os.path.isfile(BACKUP_CONFIG_PATH):
        try:
            with open(BACKUP_CONFIG_PATH, "r", encoding="utf-8") as f:
                saved_config = json.load(f)
            if isinstance(saved_config, dict):
                config.update(saved_config)
        except (OSError, json.JSONDecodeError):
            pass

    config["destination_path"] = normalize_backup_destination_path(
        config.get("destination_path")
    )
    if config.get("frequency") not in BACKUP_FREQUENCY_INTERVALS:
        config["frequency"] = "off"
    config["scheduled_time"] = normalize_backup_scheduled_time(config.get("scheduled_time"))
    if config.get("frequency") == "off":
        config["next_auto_run_at"] = None
    return config


def write_backup_config(config):
    next_config = get_default_backup_config()
    next_config.update(config or {})
    next_config["destination_path"] = normalize_backup_destination_path(
        next_config.get("destination_path")
    )
    if next_config.get("frequency") not in BACKUP_FREQUENCY_INTERVALS:
        next_config["frequency"] = "off"
    next_config["scheduled_time"] = normalize_backup_scheduled_time(next_config.get("scheduled_time"))
    if next_config.get("frequency") == "off":
        next_config["next_auto_run_at"] = None
    next_config["updated_at"] = beijing_now().isoformat()
    os.makedirs(os.path.dirname(BACKUP_CONFIG_PATH), exist_ok=True)
    with open(BACKUP_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(next_config, f, ensure_ascii=False, indent=2)
    return next_config


def calculate_next_auto_run_at(config, from_time=None):
    frequency = config.get("frequency")
    interval = BACKUP_FREQUENCY_INTERVALS.get(frequency)
    if not interval:
        return None
    now = (from_time or beijing_now()).astimezone(BEIJING_TZ)

    if frequency == "hourly":
        return (now + interval).replace(second=0, microsecond=0).isoformat()

    hour, minute = parse_backup_scheduled_time(config.get("scheduled_time"))
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if frequency == "daily":
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate.isoformat()

    if frequency == "weekly":
        while candidate <= now:
            candidate += timedelta(days=7)
        return candidate.isoformat()

    if frequency == "monthly":
        while candidate <= now:
            candidate += timedelta(days=30)
        return candidate.isoformat()

    return None


def get_backup_next_run_at(config):
    if config.get("frequency") == "off":
        return None
    saved_next_run = parse_backup_time(config.get("next_auto_run_at"))
    if saved_next_run:
        return saved_next_run.astimezone(BEIJING_TZ).isoformat()
    return calculate_next_auto_run_at(config)


def list_backup_files(destination_path):
    backup_dir = normalize_backup_destination_path(destination_path)
    if not os.path.isdir(backup_dir):
        return []
    rows = []
    for filename in os.listdir(backup_dir):
        if not (filename.startswith(BACKUP_PREFIX) and filename.endswith(".zip")):
            continue
        file_path = os.path.join(backup_dir, filename)
        if not os.path.isfile(file_path):
            continue
        stat = os.stat(file_path)
        rows.append(
            {
                "filename": filename,
                "path": file_path,
                "size": stat.st_size,
                "updated_at": datetime.fromtimestamp(stat.st_mtime, BEIJING_TZ).isoformat(),
            }
        )
    return sorted(rows, key=lambda item: item["updated_at"], reverse=True)[:20]


def get_cos_env_config():
    secret_id = os.environ.get("COS_SECRET_ID", "").strip()
    secret_key = os.environ.get("COS_SECRET_KEY", "").strip()
    region = os.environ.get("COS_REGION", "").strip()
    bucket = os.environ.get("COS_BUCKET", "").strip()
    prefix = f"{COS_BACKUP_PREFIX}/" if COS_BACKUP_PREFIX else ""
    configured = all((secret_id, secret_key, region, bucket))
    return {
        "secret_id": secret_id,
        "secret_key": secret_key,
        "region": region,
        "bucket": bucket,
        "prefix": prefix,
        "configured": configured,
        "sdk_available": bool(CosConfig and CosS3Client),
        "retention_count": COS_BACKUP_RETENTION_COUNT,
    }


def get_cos_public_status(config=None, error=""):
    cos_config = get_cos_env_config()
    if not cos_config["configured"]:
        status = "not_configured"
        message = "未配置 COS 环境变量，当前仅保留本地备份。"
    elif not cos_config["sdk_available"]:
        status = "error"
        message = "后端缺少腾讯云 COS Python SDK，请重新安装依赖。"
    elif error:
        status = "error"
        message = error
    else:
        status = "ready"
        message = "COS 环境变量已配置，备份会自动上传对象存储。"

    return {
        "status": status,
        "message": message,
        "configured": cos_config["configured"],
        "sdk_available": cos_config["sdk_available"],
        "bucket": cos_config["bucket"] if cos_config["configured"] else "",
        "region": cos_config["region"] if cos_config["configured"] else "",
        "prefix": cos_config["prefix"],
        "retention_count": cos_config["retention_count"],
        "last_cos_status": (config or {}).get("last_cos_status"),
        "last_cos_key": (config or {}).get("last_cos_key"),
        "last_cos_uploaded_at": (config or {}).get("last_cos_uploaded_at"),
        "last_cos_error": (config or {}).get("last_cos_error") or "",
        "last_cos_retained_count": (config or {}).get("last_cos_retained_count") or 0,
    }


def get_cos_client():
    cos_config = get_cos_env_config()
    if not cos_config["configured"]:
        raise RuntimeError("未配置 COS_SECRET_ID、COS_SECRET_KEY、COS_REGION 或 COS_BUCKET。")
    if not cos_config["sdk_available"]:
        raise RuntimeError("后端缺少腾讯云 COS Python SDK，请重新安装依赖。")
    config = CosConfig(
        Region=cos_config["region"],
        SecretId=cos_config["secret_id"],
        SecretKey=cos_config["secret_key"],
        Scheme="https",
    )
    return CosS3Client(config), cos_config


def parse_cos_last_modified(value):
    text = str(value or "").strip()
    if not text:
        return datetime.min.replace(tzinfo=BEIJING_TZ)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(BEIJING_TZ)
    except ValueError:
        try:
            return datetime.strptime(text, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=ZoneInfo("UTC")).astimezone(BEIJING_TZ)
        except ValueError:
            return datetime.min.replace(tzinfo=BEIJING_TZ)


def list_cos_backup_objects():
    client, cos_config = get_cos_client()
    rows = []
    marker = ""
    while True:
        response = client.list_objects(
            Bucket=cos_config["bucket"],
            Prefix=cos_config["prefix"],
            Marker=marker,
            MaxKeys=1000,
        )
        contents = response.get("Contents") or []
        if isinstance(contents, dict):
            contents = [contents]
        for item in contents:
            key = item.get("Key") or ""
            filename = os.path.basename(key)
            if not (filename.startswith(BACKUP_PREFIX) and filename.endswith(".zip")):
                continue
            last_modified = item.get("LastModified") or ""
            rows.append(
                {
                    "key": key,
                    "filename": filename,
                    "size": int(item.get("Size") or 0),
                    "updated_at": parse_cos_last_modified(last_modified).isoformat(),
                    "etag": str(item.get("ETag") or "").strip('"'),
                }
            )
        if str(response.get("IsTruncated", "")).lower() not in {"true", "1"}:
            break
        marker = response.get("NextMarker") or response.get("Marker") or ""
        if not marker:
            break
    return sorted(rows, key=lambda item: item["updated_at"], reverse=True)


def prune_cos_backup_objects(objects=None):
    client, cos_config = get_cos_client()
    rows = objects if objects is not None else list_cos_backup_objects()
    stale_objects = rows[COS_BACKUP_RETENTION_COUNT:]
    for item in stale_objects:
        client.delete_object(Bucket=cos_config["bucket"], Key=item["key"])
    return rows[:COS_BACKUP_RETENTION_COUNT], stale_objects


def upload_backup_archive_to_cos(local_path, object_filename):
    cos_config = get_cos_env_config()
    if not cos_config["configured"]:
        return {
            "status": "not_configured",
            "message": "未配置 COS 环境变量，已跳过云端上传。",
        }
    if not cos_config["sdk_available"]:
        return {
            "status": "error",
            "message": "后端缺少腾讯云 COS Python SDK，请重新安装依赖。",
        }

    try:
        client, cos_config = get_cos_client()
        object_key = f"{cos_config['prefix']}{object_filename}"
        client.put_object_from_local_file(
            Bucket=cos_config["bucket"],
            Key=object_key,
            LocalFilePath=local_path,
        )
        retained, removed = prune_cos_backup_objects()
        return {
            "status": "success",
            "message": f"COS 上传成功，云端已保留最近 {len(retained)} 个备份。",
            "key": object_key,
            "bucket": cos_config["bucket"],
            "region": cos_config["region"],
            "uploaded_at": beijing_now().isoformat(),
            "retained_count": len(retained),
            "removed_count": len(removed),
        }
    except Exception as exc:
        return {
            "status": "error",
            "message": f"COS 上传失败：{str(exc)}",
        }


def get_cos_backup_overview(config=None):
    status = get_cos_public_status(config)
    backups = []
    if status["configured"] and status["sdk_available"]:
        try:
            backups = list_cos_backup_objects()[:COS_BACKUP_RETENTION_COUNT]
        except Exception as exc:
            status = get_cos_public_status(config, f"COS 备份列表读取失败：{str(exc)}")
    return status, backups


def build_pg_environment():
    db_config = get_db_config()
    env = os.environ.copy()
    env["PGPASSWORD"] = db_config["password"]
    return db_config, env


def run_backup_subprocess(command, env):
    try:
        subprocess.run(command, env=env, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "数据库备份工具未安装，请确认后端环境已安装 postgresql-client。"
        ) from exc
    except subprocess.CalledProcessError as exc:
        error_text = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(error_text or "数据库备份工具执行失败。") from exc


def get_database_backup_member_name(names):
    if "database.dump" in names:
        return "database.dump"
    if "database.sql" in names:
        return "database.sql"
    raise ValueError("备份文件缺少 database.dump 或 database.sql。")


def should_skip_storage_backup_path(path, excluded_dirs):
    abs_path = os.path.abspath(path)
    for excluded_dir in excluded_dirs:
        try:
            if os.path.commonpath([excluded_dir, abs_path]) == excluded_dir:
                return True
        except ValueError:
            continue
    return False


def get_storage_backup_excluded_dirs(destination_path):
    storage_root_abs = os.path.abspath(STORAGE_ROOT)
    excluded_dirs = []
    for candidate in (destination_path, DEFAULT_BACKUP_DIR):
        candidate_abs = os.path.abspath(candidate)
        try:
            if (
                candidate_abs != storage_root_abs
                and os.path.commonpath([storage_root_abs, candidate_abs]) == storage_root_abs
                and candidate_abs not in excluded_dirs
            ):
                excluded_dirs.append(candidate_abs)
        except ValueError:
            continue
    return excluded_dirs


def add_storage_to_backup(zip_file, destination_path):
    storage_root_abs = os.path.abspath(STORAGE_ROOT)
    excluded_dirs = get_storage_backup_excluded_dirs(destination_path)
    for root, dirs, files in os.walk(storage_root_abs):
        dirs[:] = [
            name
            for name in dirs
            if not should_skip_storage_backup_path(os.path.join(root, name), excluded_dirs)
        ]
        if should_skip_storage_backup_path(root, excluded_dirs):
            continue
        for filename in files:
            file_path = os.path.join(root, filename)
            if file_path == os.path.abspath(BACKUP_CONFIG_PATH):
                continue
            if (
                os.path.abspath(root) == storage_root_abs
                and filename.startswith(BACKUP_PREFIX)
                and filename.endswith(".zip")
            ):
                continue
            if should_skip_storage_backup_path(file_path, excluded_dirs):
                continue
            relative_path = os.path.relpath(file_path, storage_root_abs).replace("\\", "/")
            zip_file.write(file_path, f"storage/{relative_path}")


def publish_backup_archive(temp_zip_path, final_path):
    final_dir = os.path.dirname(final_path)
    os.makedirs(final_dir, exist_ok=True)
    staging_path = os.path.join(
        final_dir,
        f".{os.path.basename(final_path)}.{uuid.uuid4().hex}.tmp",
    )

    try:
        shutil.copy2(temp_zip_path, staging_path)
        os.replace(staging_path, final_path)
    finally:
        if os.path.exists(staging_path):
            os.remove(staging_path)


def cleanup_local_backup_files(backup_dir, keep_path=None):
    backup_dir = normalize_backup_destination_path(backup_dir)
    keep_abs = os.path.abspath(keep_path) if keep_path else ""
    if not os.path.isdir(backup_dir):
        return
    for filename in os.listdir(backup_dir):
        if not (filename.startswith(BACKUP_PREFIX) and filename.endswith(".zip")):
            continue
        file_path = os.path.abspath(os.path.join(backup_dir, filename))
        try:
            if os.path.commonpath([backup_dir, file_path]) != backup_dir:
                continue
        except ValueError:
            continue
        if keep_abs and file_path == keep_abs:
            continue
        if os.path.isfile(file_path):
            os.remove(file_path)


def create_full_backup_archive(destination_path=None, reason="manual"):
    backup_dir = normalize_backup_destination_path(destination_path)
    os.makedirs(backup_dir, exist_ok=True)

    now = beijing_now()
    filename = LOCAL_BACKUP_FILENAME
    download_filename = f"{BACKUP_PREFIX}_{reason}_{now.strftime('%Y%m%d_%H%M%S')}.zip"
    final_path = os.path.join(backup_dir, filename)

    db_config, env = build_pg_environment()
    with tempfile.TemporaryDirectory() as temp_dir:
        database_dump_path = os.path.join(temp_dir, "database.dump")
        pg_dump_command = [
            "pg_dump",
            "-h",
            db_config["host"],
            "-p",
            db_config["port"],
            "-U",
            db_config["user"],
            "-d",
            db_config["dbname"],
            "-Fc",
            "--no-owner",
            "--no-acl",
            "-f",
            database_dump_path,
        ]
        run_backup_subprocess(pg_dump_command, env)

        manifest = {
            "backup_type": "ywddzx_full_backup",
            "version": 2,
            "created_at": now.isoformat(),
            "reason": reason,
            "database": db_config["dbname"],
            "database_member": "database.dump",
            "database_format": "custom",
            "restore_strategy": "drop_user_schemas_then_restore_sql",
            "storage_root": STORAGE_ROOT,
        }

        temp_zip_path = os.path.join(temp_dir, filename)
        with zipfile.ZipFile(temp_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            zip_file.write(database_dump_path, "database.dump")
            add_storage_to_backup(zip_file, backup_dir)

        publish_backup_archive(temp_zip_path, final_path)
        cleanup_local_backup_files(backup_dir, keep_path=final_path)
        if os.path.abspath(DEFAULT_BACKUP_DIR) != os.path.abspath(backup_dir):
            cleanup_local_backup_files(DEFAULT_BACKUP_DIR)

    cos_result = upload_backup_archive_to_cos(final_path, download_filename)
    return {
        "path": final_path,
        "filename": filename,
        "download_filename": download_filename,
        "size": os.path.getsize(final_path),
        "created_at": now.isoformat(),
        "cos": cos_result,
    }


def validate_backup_archive(zip_path):
    try:
        with zipfile.ZipFile(zip_path, "r") as zip_file:
            names = set(zip_file.namelist())
            if "manifest.json" not in names:
                raise ValueError("备份文件缺少 manifest.json。")
            database_member_name = get_database_backup_member_name(names)
            manifest = json.loads(zip_file.read("manifest.json").decode("utf-8"))
            if manifest.get("backup_type") != "ywddzx_full_backup":
                raise ValueError("备份文件类型不正确。")
            manifest["database_member"] = database_member_name
            return manifest
    except zipfile.BadZipFile as exc:
        raise ValueError("备份文件不是有效的 ZIP 文件。") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("备份文件清单格式不正确。") from exc


def should_skip_restore_sql_line(line):
    normalized = line.strip().lower()
    return (
        normalized.startswith("set transaction_timeout ")
        or normalized == "create schema public;"
        or normalized == "create schema if not exists public;"
    )


def build_restore_sql_file(source_sql_path, restore_sql_path):
    with open(source_sql_path, "r", encoding="utf-8", errors="replace") as source:
        with open(restore_sql_path, "w", encoding="utf-8") as target:
            target.write("BEGIN;\n")
            target.write(
                """
DO $ywddzx_restore$
DECLARE
    schema_record RECORD;
BEGIN
    FOR schema_record IN
        SELECT nspname
        FROM pg_namespace
        WHERE nspname NOT LIKE 'pg_%'
          AND nspname <> 'information_schema'
    LOOP
        EXECUTE format('DROP SCHEMA IF EXISTS %I CASCADE', schema_record.nspname);
    END LOOP;
END
$ywddzx_restore$;
CREATE SCHEMA IF NOT EXISTS public;
GRANT ALL ON SCHEMA public TO PUBLIC;
"""
            )
            for line in source:
                if should_skip_restore_sql_line(line):
                    continue
                target.write(line)
            target.write("\nCOMMIT;\n")


def convert_database_backup_to_sql(database_backup_path, database_member_name, temp_dir):
    _db_config, env = build_pg_environment()
    if database_member_name == "database.sql":
        return database_backup_path

    database_sql_path = os.path.join(temp_dir, "database.sql")
    pg_restore_command = [
        "pg_restore",
        "--no-owner",
        "--no-acl",
        "-f",
        database_sql_path,
        database_backup_path,
    ]
    run_backup_subprocess(pg_restore_command, env)
    return database_sql_path


def restore_database_from_backup(database_backup_path, database_member_name, temp_dir):
    db_config, env = build_pg_environment()
    database_sql_path = convert_database_backup_to_sql(
        database_backup_path,
        database_member_name,
        temp_dir,
    )
    restore_sql_path = os.path.join(temp_dir, "restore.sql")
    build_restore_sql_file(database_sql_path, restore_sql_path)
    psql_command = [
        "psql",
        "-h",
        db_config["host"],
        "-p",
        db_config["port"],
        "-U",
        db_config["user"],
        "-d",
        db_config["dbname"],
        "-v",
        "ON_ERROR_STOP=1",
        "-q",
        "-f",
        restore_sql_path,
    ]
    run_backup_subprocess(psql_command, env)


def get_required_storage_dirs():
    return (
        ISSUES_STORAGE_DIR,
        RECTIFICATIONS_STORAGE_DIR,
        SIGNATURES_STORAGE_DIR,
        INSPECTION_ORIGINALS_STORAGE_DIR,
        TRAINING_MATERIALS_STORAGE_DIR,
        FEEDBACK_SCREENSHOTS_STORAGE_DIR,
        ISSUE_EXPORTS_STORAGE_DIR,
        DEFAULT_BACKUP_DIR,
    )


def ensure_required_storage_dirs():
    for directory in get_required_storage_dirs():
        os.makedirs(directory, exist_ok=True)


def clear_storage_root_for_restore():
    storage_root_abs = os.path.abspath(STORAGE_ROOT)
    os.makedirs(storage_root_abs, exist_ok=True)
    for name in os.listdir(storage_root_abs):
        target_path = os.path.abspath(os.path.join(storage_root_abs, name))
        if os.path.commonpath([storage_root_abs, target_path]) != storage_root_abs:
            raise ValueError("storage 目录中存在非法路径，无法安全清空。")
        if os.path.isdir(target_path) and not os.path.islink(target_path):
            shutil.rmtree(target_path)
        else:
            os.remove(target_path)
    ensure_required_storage_dirs()


def validate_storage_backup_members(zip_file):
    storage_root_abs = os.path.abspath(STORAGE_ROOT)
    for member in zip_file.infolist():
        name = member.filename
        if not name.startswith("storage/") or name.endswith("/"):
            continue
        relative_path = name[len("storage/") :]
        if not relative_path:
            continue
        target_path = os.path.abspath(os.path.join(storage_root_abs, relative_path))
        if os.path.commonpath([storage_root_abs, target_path]) != storage_root_abs:
            raise ValueError("备份文件中存在非法 storage 路径。")


def restore_storage_from_backup(zip_path):
    storage_root_abs = os.path.abspath(STORAGE_ROOT)
    with zipfile.ZipFile(zip_path, "r") as zip_file:
        validate_storage_backup_members(zip_file)
        clear_storage_root_for_restore()
        for member in zip_file.infolist():
            name = member.filename
            if not name.startswith("storage/") or name.endswith("/"):
                continue
            relative_path = name[len("storage/") :]
            target_path = os.path.abspath(os.path.join(storage_root_abs, relative_path))
            if os.path.commonpath([storage_root_abs, target_path]) != storage_root_abs:
                raise ValueError("备份文件中存在非法 storage 路径。")
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with zip_file.open(member) as source, open(target_path, "wb") as target:
                shutil.copyfileobj(source, target)
        ensure_required_storage_dirs()


def restore_full_backup_archive(file_storage):
    if not file_storage or not file_storage.filename:
        raise ValueError("请选择需要导入的完整备份文件。")
    if not str(file_storage.filename).lower().endswith(".zip"):
        raise ValueError("完整备份只支持导入 ZIP 文件。")

    with tempfile.TemporaryDirectory() as temp_dir:
        backup_path = os.path.join(temp_dir, "backup.zip")
        file_storage.save(backup_path)
        manifest = validate_backup_archive(backup_path)
        with zipfile.ZipFile(backup_path, "r") as zip_file:
            database_member_name = manifest.get("database_member") or get_database_backup_member_name(
                set(zip_file.namelist())
            )
            database_backup_path = os.path.join(temp_dir, os.path.basename(database_member_name))
            with zip_file.open(database_member_name) as source, open(database_backup_path, "wb") as target:
                shutil.copyfileobj(source, target)
            validate_storage_backup_members(zip_file)
        restore_database_from_backup(database_backup_path, database_member_name, temp_dir)
        restore_storage_from_backup(backup_path)
        return manifest


def mark_auto_backup_result(success, result=None, error=""):
    config = read_backup_config()
    next_auto_run_at = calculate_next_auto_run_at(config)
    if success:
        cos_result = (result or {}).get("cos") or {}
        cos_status = cos_result.get("status") or "not_configured"
        config.update(
            {
                "last_auto_export_at": beijing_now().isoformat(),
                "next_auto_run_at": next_auto_run_at,
                "last_backup_path": result.get("path") if result else None,
                "last_backup_size": result.get("size") if result else None,
                "last_cos_status": cos_status,
                "last_cos_key": cos_result.get("key"),
                "last_cos_uploaded_at": cos_result.get("uploaded_at"),
                "last_cos_retained_count": cos_result.get("retained_count") or 0,
                "last_cos_error": cos_result.get("message") if cos_status == "error" else "",
                "last_status": "warning" if cos_status == "error" else "success",
                "last_error": cos_result.get("message") if cos_status == "error" else "",
            }
        )
    else:
        config.update(
            {
                "next_auto_run_at": next_auto_run_at,
                "last_status": "error",
                "last_error": str(error or "自动备份失败。")[:500],
            }
        )
    write_backup_config(config)


def maybe_run_scheduled_backup():
    config = read_backup_config()
    frequency = config.get("frequency")
    interval = BACKUP_FREQUENCY_INTERVALS.get(frequency)
    if not interval:
        return

    next_run_at = parse_backup_time(config.get("next_auto_run_at"))
    if not next_run_at:
        config["next_auto_run_at"] = calculate_next_auto_run_at(config)
        write_backup_config(config)
        return

    if beijing_now() < next_run_at.astimezone(BEIJING_TZ):
        return

    if not backup_job_lock.acquire(blocking=False):
        return
    try:
        try:
            result = create_full_backup_archive(config.get("destination_path"), reason="auto")
            mark_auto_backup_result(True, result=result)
        except Exception as exc:
            mark_auto_backup_result(False, error=exc)
    finally:
        backup_job_lock.release()


def backup_scheduler_loop():
    while True:
        try:
            maybe_run_scheduled_backup()
            maybe_cleanup_expired_issue_exports()
        except Exception:
            pass
        time.sleep(60)


def start_backup_scheduler_once():
    global backup_scheduler_started
    if backup_scheduler_started:
        return
    with backup_scheduler_lock:
        if backup_scheduler_started:
            return
        thread = threading.Thread(target=backup_scheduler_loop, daemon=True)
        thread.start()
        backup_scheduler_started = True


def get_auth_serializer():
    return URLSafeTimedSerializer(app.config["SECRET_KEY"], salt=AUTH_TOKEN_SALT)


def get_password_fingerprint(password):
    return hashlib.sha256(str(password or "").encode("utf-8")).hexdigest()[:24]


def get_auth_token_ttl_seconds(user):
    if str(user.get("role") or "") in PRIVILEGED_AUTH_ROLES:
        return AUTH_TOKEN_PRIVILEGED_MAX_AGE_SECONDS
    return AUTH_TOKEN_NORMAL_MAX_AGE_SECONDS


def current_epoch_seconds():
    return int(time.time())


def fetch_auth_user_by_id(cur, user_id):
    cur.execute(
        """
        SELECT
            u.id,
            u.username,
            u.password,
            u.role,
            u.real_name,
            u.phone,
            u.station_id,
            s.station_name,
            s.region,
            s.address
        FROM users u
        LEFT JOIN stations s ON u.station_id = s.id
        WHERE u.id = %s
        LIMIT 1;
        """,
        (user_id,),
    )
    return cur.fetchone()


def create_auth_token(user):
    issued_at = current_epoch_seconds()
    expires_at = issued_at + get_auth_token_ttl_seconds(user)
    payload = {
        "uid": int(user["id"]),
        "username": user["username"],
        "role": user["role"],
        "pwd": get_password_fingerprint(user.get("password")),
        "iat": issued_at,
        "exp": expires_at,
    }
    return get_auth_serializer().dumps(payload)


def get_auth_payload_expires_in(payload):
    try:
        expires_at = int(payload.get("exp") or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, expires_at - current_epoch_seconds())


def build_auth_user_payload(cur, user):
    permissions = get_effective_permissions(cur, user)
    return {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "real_name": user["real_name"],
        "phone": user["phone"],
        "station_id": user["station_id"],
        "station_name": user.get("station_name"),
        "region": user.get("region"),
        "address": user.get("address"),
        "permissions": permissions,
        "must_change_password": user.get("password") == DEFAULT_INITIAL_PASSWORD,
    }


def extract_bearer_token():
    header = str(request.headers.get("Authorization", "")).strip()
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return ""


def verify_auth_token(token):
    try:
        payload = get_auth_serializer().loads(token)
    except BadSignature as exc:
        raise PermissionError("登录已过期，请重新登录。") from exc

    user_id = payload.get("uid")
    if not user_id:
        raise PermissionError("登录已过期，请重新登录。")

    try:
        expires_at = int(payload.get("exp") or 0)
    except (TypeError, ValueError) as exc:
        raise PermissionError("登录已过期，请重新登录。") from exc

    if expires_at <= current_epoch_seconds():
        raise PermissionError("登录已过期，请重新登录。")

    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        user = fetch_auth_user_by_id(cur, user_id)
    finally:
        close_db_resources(cur, conn)

    if not user:
        raise PermissionError("登录已过期，请重新登录。")
    if payload.get("username") != user["username"]:
        raise PermissionError("登录已过期，请重新登录。")
    if payload.get("role") != user["role"]:
        raise PermissionError("登录已过期，请重新登录。")
    if payload.get("pwd") != get_password_fingerprint(user.get("password")):
        raise PermissionError("登录已过期，请重新登录。")
    return user, payload


def normalize_identity_for_compare(value):
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = int(text)
    except (TypeError, ValueError):
        return text
    return str(parsed) if parsed > 0 else text


def get_authenticated_request_user_id(fallback=None):
    current_user = getattr(g, "current_user", None)
    if current_user:
        return str(current_user["id"])
    return str(fallback or "").strip()


def iter_request_identity_values():
    for key in ("user_id", "inspector_id"):
        for value in request.args.getlist(key):
            yield key, value
        for value in request.form.getlist(key):
            yield key, value

    data = request.get_json(silent=True) if request.is_json else None
    if isinstance(data, dict):
        for key in ("user_id", "inspector_id"):
            if key in data:
                yield key, data.get(key)


def is_public_api_path(path):
    if not path.startswith("/api/"):
        return True
    return path in {
        "/api/health",
        "/api/db-test",
        "/api/login",
    }


@app.before_request
def require_signed_api_token():
    if request.method == "OPTIONS":
        return None
    if not request.path.startswith("/api/"):
        return None
    if is_public_api_path(request.path):
        return None

    token = extract_bearer_token()
    if not token:
        return jsonify({"success": False, "error": "请先登录。"}), 401

    try:
        user, payload = verify_auth_token(token)
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 401

    g.current_user = user
    g.auth_payload = payload
    current_user_id = normalize_identity_for_compare(user["id"])
    for key, value in iter_request_identity_values():
        requested_user_id = normalize_identity_for_compare(value)
        if requested_user_id and requested_user_id != current_user_id:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"请求中的{key}与当前登录账号不一致，已拒绝操作。",
                    }
                ),
                403,
            )

    return None


@app.before_request
def ensure_backup_scheduler_started():
    start_backup_scheduler_once()


def get_checklist_field_meta(cur, inspection_table_id):
    rows = get_management_checklist_fields(cur, inspection_table_id, include_public=True)
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


def normalize_boolean_flag(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"false", "0", "no", "否"}
    return bool(value)


def build_register_display_field_meta(fields):
    return [
        (field["field_key"], field["field_label"])
        for field in fields
        if normalize_boolean_flag(field.get("is_register_visible"), True)
    ]


def normalize_checklist_code(value):
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9_]+", "_", text).strip("_")
    text = re.sub(r"_+", "_", text)
    if not text:
        raise ValueError("请填写检查表编码。")
    if not re.match(r"^[a-z][a-z0-9_]{1,41}$", text):
        raise ValueError("检查表编码只能使用小写英文字母、数字和下划线，且必须以字母开头，长度 2-42 位。")
    return text


def normalize_checklist_mode(value):
    text = str(value or "online").strip().lower()
    if text not in {"online", "offline"}:
        raise ValueError("检查表模式只能选择线上或线下。")
    return text


def normalize_checklist_field_key(value):
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9_]+", "_", text).strip("_")
    text = re.sub(r"_+", "_", text)
    if not text:
        raise ValueError("字段系统标识缺失，请重新保存。")
    if not re.match(rf"^[a-z][a-z0-9_]{{1,{CHECKLIST_FIELD_KEY_MAX_LENGTH - 1}}}$", text):
        raise ValueError(
            f"字段系统标识只能使用小写英文字母、数字和下划线，且必须以字母开头，长度 2-{CHECKLIST_FIELD_KEY_MAX_LENGTH} 位。"
        )
    if text in RESERVED_CHECKLIST_FIELD_KEYS:
        raise ValueError(f"字段系统标识 {text} 为系统保留字段，不能使用。")
    return text


def generate_checklist_field_key(table_code, sort_order, existing_keys=None):
    normalized_code = normalize_checklist_code(table_code)
    occupied_keys = set(existing_keys or [])
    order_text = str(max(int(sort_order or 1), 1)).zfill(3)
    for _ in range(20):
        candidate = f"f_{normalized_code}_{order_text}_{uuid.uuid4().hex[:6]}"
        if len(candidate) > CHECKLIST_FIELD_KEY_MAX_LENGTH:
            raise ValueError("检查表编码过长，无法生成字段系统标识。")
        if candidate not in occupied_keys:
            return candidate
    raise ValueError("字段系统标识自动生成失败，请重试。")


def normalize_checklist_field_rows(fields, table_code=None, allow_empty=False):
    if not isinstance(fields, list) or not fields:
        if allow_empty:
            return []
        raise ValueError("请至少配置一个检查表字段。")

    normalized = []
    seen_keys = set()
    seen_labels = set()
    for index, field in enumerate(fields, start=1):
        raw_field_key = field.get("field_key") if isinstance(field, dict) else ""
        if raw_field_key:
            field_key = normalize_checklist_field_key(raw_field_key)
        elif table_code:
            field_key = generate_checklist_field_key(table_code, index, seen_keys)
        else:
            raise ValueError("字段系统标识自动生成失败，请重新进入页面后再试。")
        field_label = normalize_text(field.get("field_label") if isinstance(field, dict) else "", 80)
        if not field_label:
            raise ValueError(f"第 {index} 个字段缺少字段名称。")
        if field_key in seen_keys:
            raise ValueError(f"字段系统标识 {field_key} 重复。")
        if field_label in seen_labels:
            raise ValueError(f"字段名称【{field_label}】重复。")
        seen_keys.add(field_key)
        seen_labels.add(field_label)
        normalized.append(
            {
                "field_key": field_key,
                "field_label": field_label,
                "is_filterable": normalize_boolean_flag(field.get("is_filterable"), True) if isinstance(field, dict) else True,
                "is_register_visible": normalize_boolean_flag(field.get("is_register_visible"), True) if isinstance(field, dict) else True,
                "is_long_text": normalize_boolean_flag(field.get("is_long_text"), False) if isinstance(field, dict) else False,
                "sort_order": index,
            }
        )

    return normalized


def get_physical_table_name_by_code(table_code):
    try:
        table_code = normalize_checklist_code(table_code)
    except ValueError:
        return None
    return f"{CHECKLIST_PHYSICAL_TABLE_PREFIX}{table_code}"


def get_default_checklist_standard_id_base(inspection_table_id):
    table_id = int(inspection_table_id or 0)
    if table_id <= 0:
        raise ValueError("检查表编号异常，无法生成规范ID号段。")
    return table_id * CHECKLIST_STANDARD_ID_BLOCK_SIZE


def normalize_checklist_standard_id_base(value, fallback_table_id=None):
    if value in (None, ""):
        if fallback_table_id is None:
            raise ValueError("检查表规范ID号段缺失。")
        value = get_default_checklist_standard_id_base(fallback_table_id)
    try:
        standard_id_base = int(value)
    except (TypeError, ValueError):
        raise ValueError("检查表规范ID号段必须是整数。")
    if (
        standard_id_base < CHECKLIST_STANDARD_ID_BLOCK_SIZE
        or standard_id_base % CHECKLIST_STANDARD_ID_BLOCK_SIZE != 0
    ):
        raise ValueError("检查表规范ID号段必须从 1000、2000、3000 这样的整千数开始。")
    return standard_id_base


def get_checklist_standard_id_bounds(standard_id_base):
    start = normalize_checklist_standard_id_base(standard_id_base)
    return start, start + CHECKLIST_STANDARD_ID_BLOCK_SIZE - 1


def is_standard_id_in_checklist_range(standard_id, standard_id_base):
    start, end = get_checklist_standard_id_bounds(standard_id_base)
    try:
        value = int(standard_id)
    except (TypeError, ValueError):
        return False
    return start <= value <= end


def migrate_checklist_standard_ids_to_base(cur, checklist_row):
    physical_table_name = get_physical_table_name_by_code(checklist_row["table_code"])
    if not physical_table_name or not checklist_physical_table_exists(cur, physical_table_name):
        return

    standard_id_base = normalize_checklist_standard_id_base(
        checklist_row.get("standard_id_base"),
        checklist_row["id"],
    )
    range_start, range_end = get_checklist_standard_id_bounds(standard_id_base)

    cur.execute(
        sql.SQL("SELECT id, standard_id FROM {} ORDER BY standard_id ASC, id ASC;").format(
            sql.Identifier(physical_table_name)
        )
    )
    rows = cur.fetchall()
    if not rows:
        return
    if len(rows) > CHECKLIST_STANDARD_ID_BLOCK_SIZE:
        raise ValueError(
            f"检查表【{checklist_row['table_name']}】规范数量超过 {CHECKLIST_STANDARD_ID_BLOCK_SIZE} 条，"
            "无法按当前规范ID号段规则迁移。"
        )

    if all(range_start <= int(row["standard_id"]) <= range_end for row in rows):
        return

    mappings = []
    for index, row in enumerate(rows):
        new_standard_id = range_start + index
        mappings.append(
            {
                "row_id": row["id"],
                "old_standard_id": int(row["standard_id"]),
                "new_standard_id": new_standard_id,
                "temp_standard_id": -(range_start + index + 1000000000),
            }
        )

    for item in mappings:
        cur.execute(
            sql.SQL("UPDATE {} SET standard_id = %s WHERE id = %s;").format(
                sql.Identifier(physical_table_name)
            ),
            (item["temp_standard_id"], item["row_id"]),
        )

    cur.execute("SELECT to_regclass('public.issues') AS table_name;")
    issues_table_exists = bool(cur.fetchone().get("table_name"))
    if issues_table_exists:
        for item in mappings:
            cur.execute(
                """
                UPDATE issues
                SET standard_id = %s
                WHERE inspection_table_id = %s
                  AND standard_id = %s;
                """,
                (item["temp_standard_id"], checklist_row["id"], item["old_standard_id"]),
            )

    for item in mappings:
        cur.execute(
            sql.SQL("UPDATE {} SET standard_id = %s WHERE id = %s;").format(
                sql.Identifier(physical_table_name)
            ),
            (item["new_standard_id"], item["row_id"]),
        )

    if issues_table_exists:
        for item in mappings:
            cur.execute(
                """
                UPDATE issues
                SET standard_id = %s
                WHERE inspection_table_id = %s
                  AND standard_id = %s;
                """,
                (item["new_standard_id"], checklist_row["id"], item["temp_standard_id"]),
            )


def ensure_checklist_standard_id_bases(cur):
    cur.execute(
        """
        ALTER TABLE inspection_tables
        ADD COLUMN IF NOT EXISTS standard_id_base INTEGER;
        """
    )
    cur.execute(
        """
        UPDATE inspection_tables
        SET standard_id_base = id * %s
        WHERE standard_id_base IS NULL;
        """,
        (CHECKLIST_STANDARD_ID_BLOCK_SIZE,),
    )
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_inspection_tables_standard_id_base_unique
        ON inspection_tables (standard_id_base);
        """
    )
    cur.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'inspection_tables_standard_id_base_check'
            ) THEN
                ALTER TABLE inspection_tables
                ADD CONSTRAINT inspection_tables_standard_id_base_check
                CHECK (
                    standard_id_base >= 1000
                    AND standard_id_base % 1000 = 0
                );
            END IF;
        END $$;
        """
    )
    cur.execute(
        """
        SELECT id, table_code, table_name, standard_id_base
        FROM inspection_tables
        ORDER BY id ASC;
        """
    )
    for row in cur.fetchall():
        migrate_checklist_standard_ids_to_base(cur, row)


def ensure_inspection_checklist_management_schema(cur):
    acquire_schema_migration_lock(cur)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS inspection_tables (
            id SERIAL PRIMARY KEY,
            table_code TEXT UNIQUE NOT NULL,
            table_name TEXT UNIQUE NOT NULL,
            checklist_mode TEXT NOT NULL DEFAULT 'online',
            standard_id_base INTEGER UNIQUE,
            description TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cur.execute(
        """
        ALTER TABLE inspection_tables
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
        """
    )
    cur.execute(
        """
        ALTER TABLE inspection_tables
        ADD COLUMN IF NOT EXISTS checklist_mode TEXT NOT NULL DEFAULT 'online';
        """
    )
    ensure_checklist_standard_id_bases(cur)
    cur.execute(
        """
        UPDATE inspection_tables
        SET checklist_mode = 'online'
        WHERE checklist_mode IS NULL OR checklist_mode NOT IN ('online', 'offline');
        """
    )
    cur.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'inspection_tables_checklist_mode_check'
            ) THEN
                ALTER TABLE inspection_tables
                ADD CONSTRAINT inspection_tables_checklist_mode_check
                CHECK (checklist_mode IN ('online', 'offline'));
            END IF;
        END $$;
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS inspection_table_fields (
            id SERIAL PRIMARY KEY,
            inspection_table_id INTEGER NOT NULL REFERENCES inspection_tables(id) ON DELETE CASCADE,
            field_key TEXT NOT NULL,
            field_label TEXT NOT NULL,
            is_filterable BOOLEAN DEFAULT TRUE,
            is_register_visible BOOLEAN DEFAULT TRUE,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS inspection_standard_export_templates (
            id INTEGER PRIMARY KEY DEFAULT 1,
            template_config JSONB NOT NULL DEFAULT '{}'::jsonb,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT inspection_standard_export_templates_singleton CHECK (id = 1)
        );
        """
    )
    cur.execute(
        """
        ALTER TABLE inspection_table_fields
        ADD COLUMN IF NOT EXISTS is_filterable BOOLEAN DEFAULT TRUE;
        """
    )
    cur.execute(
        """
        ALTER TABLE inspection_table_fields
        ADD COLUMN IF NOT EXISTS is_register_visible BOOLEAN DEFAULT TRUE;
        """
    )
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_inspection_table_fields_table_key_unique
        ON inspection_table_fields (inspection_table_id, field_key);
        """
    )
    cur.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname = 'idx_inspection_table_fields_key_unique'
            )
            AND NOT EXISTS (
                SELECT 1
                FROM inspection_table_fields
                GROUP BY field_key
                HAVING COUNT(*) > 1
            ) THEN
                CREATE UNIQUE INDEX idx_inspection_table_fields_key_unique
                ON inspection_table_fields (field_key);
            END IF;
        END $$;
        """
    )


def ensure_checklist_physical_table(cur, physical_table_name):
    cur.execute(
        sql.SQL(
            """
            CREATE TABLE IF NOT EXISTS {} (
                id SERIAL PRIMARY KEY,
                standard_id BIGINT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        ).format(sql.Identifier(physical_table_name))
    )


def ensure_checklist_field_columns(cur, physical_table_name, fields):
    ensure_checklist_physical_table(cur, physical_table_name)
    for field in fields:
        cur.execute(
            sql.SQL("ALTER TABLE {} ADD COLUMN IF NOT EXISTS {} TEXT;").format(
                sql.Identifier(physical_table_name),
                sql.Identifier(field["field_key"]),
            )
        )


def checklist_physical_table_exists(cur, physical_table_name):
    cur.execute("SELECT to_regclass(%s) AS table_name;", (f"public.{physical_table_name}",))
    row = cur.fetchone()
    return bool(row and row.get("table_name"))


def get_checklist_row_count(cur, physical_table_name):
    if not physical_table_name or not checklist_physical_table_exists(cur, physical_table_name):
        return 0
    cur.execute(
        sql.SQL("SELECT COUNT(*) AS total FROM {};").format(sql.Identifier(physical_table_name))
    )
    row = cur.fetchone()
    return int(row["total"] or 0)


def get_management_checklist_fields(cur, inspection_table_id, include_public=False):
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'inspection_table_fields'
              AND column_name = 'is_register_visible'
        ) AS has_column;
        """
    )
    has_register_visible_column = bool(cur.fetchone().get("has_column"))
    register_visible_select = "is_register_visible" if has_register_visible_column else "TRUE AS is_register_visible"
    cur.execute(
        f"""
        SELECT
            id,
            inspection_table_id,
            field_key,
            field_label,
            is_filterable,
            {register_visible_select},
            sort_order,
            FALSE AS is_public
        FROM inspection_table_fields
        WHERE inspection_table_id = %s
        ORDER BY sort_order ASC, id ASC;
        """,
        (inspection_table_id,),
    )
    return cur.fetchall()


def normalize_standard_export_template_config(cur, raw_config):
    config = raw_config if isinstance(raw_config, dict) else {}
    cur.execute(
        """
        SELECT id
        FROM inspection_tables
        WHERE is_active = TRUE
        ORDER BY id ASC;
        """
    )
    normalized = {}
    for table in cur.fetchall():
        table_key = str(table["id"])
        allowed_keys = {
            str(field["field_key"])
            for field in get_management_checklist_fields(cur, table["id"], include_public=True)
        }
        incoming_keys = config.get(table_key, config.get(table["id"], []))
        if not isinstance(incoming_keys, list):
            incoming_keys = []
        normalized[table_key] = []
        seen = set()
        for field_key in incoming_keys:
            text = str(field_key or "").strip()
            if not text or text in seen or text not in allowed_keys:
                continue
            normalized[table_key].append(text)
            seen.add(text)
    return normalized


def get_standard_export_template_config(cur):
    cur.execute(
        """
        SELECT template_config
        FROM inspection_standard_export_templates
        WHERE id = 1;
        """
    )
    row = cur.fetchone()
    if not row:
        return {"has_saved": False, "tables": {}}
    return {
        "has_saved": True,
        "tables": normalize_standard_export_template_config(
            cur, row.get("template_config") or {}
        ),
    }


def save_standard_export_template_config(cur, template_config):
    normalized = normalize_standard_export_template_config(cur, template_config)
    cur.execute(
        """
        INSERT INTO inspection_standard_export_templates (
            id,
            template_config,
            updated_at
        )
        VALUES (1, %s::jsonb, CURRENT_TIMESTAMP)
        ON CONFLICT (id) DO UPDATE
        SET template_config = EXCLUDED.template_config,
            updated_at = CURRENT_TIMESTAMP;
        """,
        (json.dumps(normalized, ensure_ascii=False),),
    )
    return normalized


def upsert_checklist_fields(cur, inspection_table_id, fields):
    incoming_keys = [field["field_key"] for field in fields]
    cur.execute(
        """
        DELETE FROM inspection_table_fields
        WHERE inspection_table_id = %s
          AND field_key <> ALL(%s::text[]);
        """,
        (inspection_table_id, incoming_keys),
    )
    for field in fields:
        cur.execute(
            """
            INSERT INTO inspection_table_fields (
                inspection_table_id,
                field_key,
                field_label,
                is_filterable,
                is_register_visible,
                sort_order
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (inspection_table_id, field_key)
            DO UPDATE SET
                field_label = EXCLUDED.field_label,
                is_filterable = EXCLUDED.is_filterable,
                is_register_visible = EXCLUDED.is_register_visible,
                sort_order = EXCLUDED.sort_order;
            """,
            (
                inspection_table_id,
                field["field_key"],
                field["field_label"],
                field["is_filterable"],
                field["is_register_visible"],
                field["sort_order"],
            ),
        )


def ensure_unique_checklist_field_keys(cur, fields, inspection_table_id=None):
    incoming_keys = [field["field_key"] for field in fields]
    if not incoming_keys:
        return
    cur.execute(
        """
        SELECT field_key, inspection_table_id
        FROM inspection_table_fields
        WHERE field_key = ANY(%s::text[])
          AND (%s::integer IS NULL OR inspection_table_id <> %s::integer)
        LIMIT 1;
        """,
        (incoming_keys, inspection_table_id, inspection_table_id),
    )
    conflict = cur.fetchone()
    if conflict:
        raise ValueError("字段系统标识已被其他检查表使用，请重新保存生成新的字段键。")


def serialize_management_checklist(cur, row):
    physical_table_name = get_physical_table_name_by_code(row["table_code"])
    local_fields = [dict(field) for field in get_management_checklist_fields(cur, row["id"])]
    return {
        "id": row["id"],
        "table_code": row["table_code"],
        "table_name": row["table_name"],
        "checklist_mode": normalize_checklist_mode(row.get("checklist_mode")),
        "standard_id_base": normalize_checklist_standard_id_base(
            row.get("standard_id_base"),
            row["id"],
        ),
        "description": row["description"],
        "is_active": row["is_active"],
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "physical_table_name": physical_table_name,
        "fields": local_fields,
        "local_fields": local_fields,
        "standard_count": get_checklist_row_count(cur, physical_table_name),
    }


def fetch_management_checklist(cur, inspection_table_id):
    cur.execute(
        """
        SELECT
            id,
            table_code,
            table_name,
            checklist_mode,
            standard_id_base,
            description,
            is_active,
            TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI') AS created_at,
            TO_CHAR(updated_at, 'YYYY-MM-DD HH24:MI') AS updated_at
        FROM inspection_tables
        WHERE id = %s
        LIMIT 1;
        """,
        (inspection_table_id,),
    )
    return cur.fetchone()


def normalize_import_standard_id(value):
    text = str(value or "").strip()
    if not text:
        raise ValueError("请填写外部规范ID。")
    if re.match(r"^\d+\.0$", text):
        text = text[:-2]
    if not re.match(r"^-?\d+$", text):
        raise ValueError(f"外部规范ID【{text}】不是有效整数。")
    return int(text)


def get_import_value(row, field):
    for key in (field["field_key"], field["field_label"]):
        if key in row:
            return row.get(key)
    return ""


def normalize_checklist_import_rows(raw_rows, fields, standard_id_base=None, allow_reassign=False):
    if not raw_rows:
        raise ValueError("导入文件没有可导入的数据行。")
    range_start = range_end = None
    if standard_id_base is not None:
        range_start, range_end = get_checklist_standard_id_bounds(standard_id_base)
    if len(raw_rows) > CHECKLIST_STANDARD_ID_BLOCK_SIZE:
        raise ValueError(f"单张检查表最多导入 {CHECKLIST_STANDARD_ID_BLOCK_SIZE} 条规范。")

    normalized = []
    seen_ids = set()
    for index, row in enumerate(raw_rows):
        raw_standard_id = (
            row.get("standard_id")
            or row.get("规范ID")
            or row.get("标准ID")
            or row.get("id")
        )
        if raw_standard_id in (None, "") and standard_id_base is not None:
            standard_id = range_start + index
        else:
            standard_id = normalize_import_standard_id(raw_standard_id)
        if standard_id_base is not None and not (range_start <= standard_id <= range_end):
            if not allow_reassign:
                raise ValueError(
                    f"外部规范ID【{standard_id}】不在当前检查表号段 {range_start}-{range_end} 内。"
                )
            standard_id = range_start + index
        if standard_id in seen_ids:
            raise ValueError(f"导入文件内外部规范ID【{standard_id}】重复。")
        seen_ids.add(standard_id)
        item = {"standard_id": standard_id}
        for field in fields:
            item[field["field_key"]] = str(get_import_value(row, field) or "").strip()
        normalized.append(item)
    return normalized


def rebase_checklist_standard_rows(rows, source_base, target_base):
    source_start, source_end = get_checklist_standard_id_bounds(source_base)
    target_start, target_end = get_checklist_standard_id_bounds(target_base)
    if source_start == target_start:
        return [dict(row) for row in rows]

    rebased_rows = []
    for index, row in enumerate(sorted(rows, key=lambda item: int(item.get("standard_id") or 0))):
        old_standard_id = int(row.get("standard_id") or 0)
        if source_start <= old_standard_id <= source_end:
            offset = old_standard_id - source_start
        else:
            offset = index
        new_standard_id = target_start + offset
        if new_standard_id > target_end:
            raise ValueError(
                f"检查表规范数量超过号段 {target_start}-{target_end} 可容纳范围，无法导入。"
            )
        item = dict(row)
        item["standard_id"] = new_standard_id
        rebased_rows.append(item)
    return rebased_rows


def fetch_checklist_standard_rows(cur, physical_table_name, fields):
    if not checklist_physical_table_exists(cur, physical_table_name):
        return []
    columns = ["standard_id", *[field["field_key"] for field in fields]]
    cur.execute(
        sql.SQL("SELECT {} FROM {} ORDER BY standard_id ASC;").format(
            sql.SQL(", ").join(sql.Identifier(column) for column in columns),
            sql.Identifier(physical_table_name),
        )
    )
    return [dict(row) for row in cur.fetchall()]


def insert_checklist_standard_rows(cur, physical_table_name, fields, rows):
    columns = ["standard_id", *[field["field_key"] for field in fields]]
    update_columns = [field["field_key"] for field in fields]
    if not update_columns:
        return
    insert_sql = sql.SQL(
        """
        INSERT INTO {} ({})
        VALUES ({})
        ON CONFLICT (standard_id)
        DO UPDATE SET {};
        """
    ).format(
        sql.Identifier(physical_table_name),
        sql.SQL(", ").join(sql.Identifier(column) for column in columns),
        sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        sql.SQL(", ").join(
            sql.SQL("{} = EXCLUDED.{}").format(
                sql.Identifier(column),
                sql.Identifier(column),
            )
            for column in update_columns
        ),
    )
    for row in rows:
        cur.execute(insert_sql, [row.get(column) for column in columns])


def normalize_checklist_standard_payload(data, fields):
    if not isinstance(data, dict):
        raise ValueError("规范数据格式不正确。")

    values = data.get("values") if isinstance(data.get("values"), dict) else data
    row = {}
    for field in fields:
        row[field["field_key"]] = normalize_text(values.get(field["field_key"], ""), 3000)
    if not any(value for value in row.values()):
        raise ValueError("请至少填写一项规范内容。")
    return row


def get_next_checklist_standard_id(cur, checklist, physical_table_name):
    cur.execute(
        """
        SELECT id, standard_id_base
        FROM inspection_tables
        WHERE id = %s
        FOR UPDATE;
        """,
        (checklist["id"],),
    )
    locked_checklist = cur.fetchone()
    if not locked_checklist:
        raise LookupError("检查表不存在。")

    standard_id_base = normalize_checklist_standard_id_base(
        locked_checklist.get("standard_id_base"),
        locked_checklist["id"],
    )
    range_start, range_end = get_checklist_standard_id_bounds(standard_id_base)

    if not checklist_physical_table_exists(cur, physical_table_name):
        return range_start

    cur.execute(
        sql.SQL("LOCK TABLE {} IN SHARE ROW EXCLUSIVE MODE;").format(
            sql.Identifier(physical_table_name)
        )
    )
    cur.execute(
        sql.SQL(
            """
            SELECT COALESCE(MAX(standard_id), %s - 1) AS max_standard_id
            FROM {}
            WHERE standard_id BETWEEN %s AND %s;
            """
        ).format(sql.Identifier(physical_table_name)),
        (range_start, range_start, range_end),
    )
    row = cur.fetchone()
    next_standard_id = int(row["max_standard_id"] or (range_start - 1)) + 1
    if next_standard_id > range_end:
        raise ValueError(
            f"该检查表外部规范ID号段 {range_start}-{range_end} 已用完，"
            f"单张检查表最多维护 {CHECKLIST_STANDARD_ID_BLOCK_SIZE} 条规范。"
        )
    return next_standard_id


def get_checklist_standard_reference_counts(cur, inspection_table_id, standard_id):
    cur.execute(
        """
        SELECT COUNT(*) AS total
        FROM issues
        WHERE inspection_table_id = %s
          AND standard_id = %s;
        """,
        (inspection_table_id, standard_id),
    )
    issue_count = int(cur.fetchone()["total"] or 0)
    return {"issue_count": issue_count}


def format_checklist_standard_reference_message(counts):
    parts = []
    if counts.get("issue_count", 0) > 0:
        parts.append(f"巡检问题 {counts['issue_count']} 条")
    return "、".join(parts)


def sync_referenced_standard_detail_text(cur, inspection_table_id, standard_id, detail_text):
    cur.execute(
        """
        UPDATE issues
        SET standard_detail_text = %s
        WHERE inspection_table_id = %s
          AND standard_id = %s;
        """,
        (detail_text, inspection_table_id, standard_id),
    )
    return cur.rowcount


def sync_referenced_internal_standard_detail_text(cur, internal_standard_id, detail_text):
    cur.execute(
        """
        UPDATE issues
        SET internal_standard_detail_text = %s
        WHERE UPPER(COALESCE(internal_standard_id, '')) = %s;
        """,
        (detail_text, str(internal_standard_id or "").upper()),
    )
    return cur.rowcount


def get_management_checklist_standard_context(cur, inspection_table_id, require_fields=True):
    checklist = fetch_management_checklist(cur, inspection_table_id)
    if not checklist:
        raise LookupError("检查表不存在。")

    fields = [dict(field) for field in get_management_checklist_fields(cur, inspection_table_id, include_public=True)]
    if require_fields and not fields:
        raise ValueError("请先配置检查表字段，再维护规范数据。")

    physical_table_name = get_physical_table_name_by_code(checklist["table_code"])
    if not physical_table_name:
        raise ValueError("检查表物理表名生成失败。")
    ensure_checklist_field_columns(cur, physical_table_name, fields)
    return checklist, fields, physical_table_name


def build_standard_search_sql(fields, keyword):
    keyword = normalize_text(keyword, 120)
    if not keyword:
        return sql.SQL(""), []

    search_columns = [
        sql.SQL("standard_id::text"),
        *[
            sql.SQL("COALESCE({}, '')").format(sql.Identifier(field["field_key"]))
            for field in fields
        ],
    ]
    return (
        sql.SQL(" WHERE CONCAT_WS(' ', {}) ILIKE %s").format(
            sql.SQL(", ").join(search_columns)
        ),
        [f"%{keyword}%"],
    )


def normalize_page_args(page_value, page_size_value):
    try:
        page = max(int(page_value or 1), 1)
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(page_size_value or 10)
    except (TypeError, ValueError):
        page_size = 10
    page_size = min(max(page_size, 5), 100)
    return page, page_size


def normalize_checklist_backup_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("备份文件格式不正确：根内容必须是对象。")
    if payload.get("backup_type") != "ywddzx_checklists":
        raise ValueError("备份文件类型不匹配，请选择巡检表数据备份文件。")
    checklists = payload.get("checklists")
    if not isinstance(checklists, list):
        raise ValueError("备份文件缺少 checklists 数组。")

    normalized = []
    seen_codes = set()
    seen_names = set()
    seen_field_keys = set()
    seen_standard_id_bases = set()
    for index, item in enumerate(checklists, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"第 {index} 张检查表数据格式不正确。")
        table_code = normalize_checklist_code(item.get("table_code"))
        table_name = normalize_text(item.get("table_name"), 120)
        checklist_mode = normalize_checklist_mode(item.get("checklist_mode"))
        standard_id_base = normalize_checklist_standard_id_base(
            item.get("standard_id_base"),
            index,
        )
        if not table_name:
            raise ValueError(f"第 {index} 张检查表缺少名称。")
        if table_code in seen_codes:
            raise ValueError(f"备份文件内检查表编码 {table_code} 重复。")
        if table_name in seen_names:
            raise ValueError(f"备份文件内检查表名称【{table_name}】重复。")
        if standard_id_base in seen_standard_id_bases:
            raise ValueError(f"备份文件内外部规范ID号段【{standard_id_base}】重复。")
        seen_codes.add(table_code)
        seen_names.add(table_name)
        seen_standard_id_bases.add(standard_id_base)
        fields = normalize_checklist_field_rows(item.get("fields"), table_code)
        for field in fields:
            field_key = field["field_key"]
            if field_key in seen_field_keys:
                raise ValueError(f"备份文件内字段系统标识 {field_key} 重复。")
            seen_field_keys.add(field_key)
        standards = (
            normalize_checklist_import_rows(
                item.get("standards") or [],
                fields,
                standard_id_base,
                allow_reassign=True,
            )
            if item.get("standards")
            else []
        )
        normalized.append(
            {
                "table_code": table_code,
                "table_name": table_name,
                "checklist_mode": checklist_mode,
                "standard_id_base": standard_id_base,
                "description": normalize_text(item.get("description"), 300),
                "is_active": bool(item.get("is_active", True)),
                "fields": fields,
                "standards": standards,
            }
        )
    return {
        "checklists": normalized,
    }


def parse_checklist_backup_file(file_storage):
    if not file_storage or not file_storage.filename:
        raise ValueError("请选择需要导入的巡检表备份文件。")
    if not file_storage.filename.lower().endswith(".json"):
        raise ValueError("巡检表备份文件只能导入 JSON 格式。")
    file_bytes = file_storage.read()
    if not file_bytes:
        raise ValueError("备份文件内容为空。")
    try:
        payload = json.loads(file_bytes.decode("utf-8-sig"))
    except Exception as exc:
        raise ValueError("备份文件 JSON 解析失败，请检查文件是否损坏。") from exc
    return normalize_checklist_backup_payload(payload)


def get_blocking_checklist_references(cur, inspection_table_ids):
    ids = [int(value) for value in inspection_table_ids if value]
    if not ids:
        return []
    reference_tables = [
        ("inspections", "巡检记录"),
        ("issues", "巡检问题"),
        ("inspection_plan_configs", "巡检计划"),
        ("inspection_table_original_files", "检查表原件"),
    ]
    blockers = []
    for table_name, label in reference_tables:
        cur.execute("SELECT to_regclass(%s) AS table_name;", (f"public.{table_name}",))
        if not cur.fetchone().get("table_name"):
            continue
        cur.execute(
            sql.SQL("SELECT COUNT(*) AS total FROM {} WHERE inspection_table_id = ANY(%s);").format(
                sql.Identifier(table_name)
            ),
            (ids,),
        )
        total = int(cur.fetchone()["total"] or 0)
        if total:
            blockers.append(f"{label} {total} 条")
    return blockers


def get_inspection_table_record(cur, inspection_table_id):
    cur.execute(
        """
        SELECT
            id,
            table_code,
            table_name,
            standard_id_base,
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


def ensure_issue_inspector_schema(cur):
    global ISSUE_INSPECTOR_SCHEMA_READY
    if ISSUE_INSPECTOR_SCHEMA_READY:
        return
    acquire_schema_migration_lock(cur)
    cur.execute("SELECT to_regclass('public.issues') AS table_name;")
    if not cur.fetchone().get("table_name"):
        return

    cur.execute(
        """
        ALTER TABLE issues
        ADD COLUMN IF NOT EXISTS inspector_id INTEGER REFERENCES users(id) ON DELETE RESTRICT;
        """
    )
    cur.execute(
        """
        ALTER TABLE issues
        ADD COLUMN IF NOT EXISTS internal_standard_id TEXT;
        """
    )
    cur.execute(
        """
        ALTER TABLE issues
        ADD COLUMN IF NOT EXISTS internal_standard_detail_text TEXT;
        """
    )
    cur.execute(
        """
        ALTER TABLE issues
        ADD COLUMN IF NOT EXISTS audit_status TEXT NOT NULL DEFAULT 'pending';
        """
    )
    cur.execute(
        """
        ALTER TABLE issues
        ADD COLUMN IF NOT EXISTS audited_by INTEGER REFERENCES users(id) ON DELETE SET NULL;
        """
    )
    cur.execute(
        """
        ALTER TABLE issues
        ADD COLUMN IF NOT EXISTS audited_at TIMESTAMP;
        """
    )
    cur.execute(
        """
        ALTER TABLE issues
        ADD COLUMN IF NOT EXISTS is_excellent BOOLEAN NOT NULL DEFAULT FALSE;
        """
    )
    cur.execute(
        """
        UPDATE issues
        SET is_excellent = FALSE
        WHERE is_excellent IS NULL
           OR COALESCE(audit_status, 'pending') = 'rejected';
        """
    )
    cur.execute("SELECT to_regclass('public.inspections') AS table_name;")
    if cur.fetchone().get("table_name"):
        cur.execute(
            """
            UPDATE issues i
            SET inspector_id = ins.inspector_id
            FROM inspections ins
            WHERE i.inspection_id = ins.id
              AND i.inspector_id IS NULL;
            """
        )
        cur.execute(
            """
            UPDATE issues i
            SET audit_status = 'approved',
                audited_at = COALESCE(ins.station_manager_signed_at, i.audited_at, i.created_at, CURRENT_TIMESTAMP)
            FROM inspections ins
            WHERE i.inspection_id = ins.id
              AND (
                  COALESCE(ins.sign_status, '') = '已签名确认'
                  OR ins.station_manager_signed_at IS NOT NULL
                  OR NULLIF(ins.station_manager_signature_path, '') IS NOT NULL
                  OR NULLIF(ins.station_manager_signed_name, '') IS NOT NULL
              )
              AND COALESCE(i.audit_status, 'pending') = 'pending';
            """
        )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_issues_inspector_id
        ON issues (inspector_id);
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_issues_internal_standard_id
        ON issues (internal_standard_id);
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_issues_audit_status
        ON issues (audit_status);
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_issues_is_excellent
        ON issues (is_excellent);
        """
    )
    ISSUE_INSPECTOR_SCHEMA_READY = True


def create_inspection_record(
    cur, station_id, inspector_id, inspection_table_id, batch_id, inspection_date=None
):
    target_date = inspection_date or beijing_today()
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
        (station_id, inspector_id, inspection_table_id, target_date, batch_id),
    )
    row = cur.fetchone()
    return row["id"]


def ensure_inspection_completion_schema(cur):
    global INSPECTION_COMPLETION_SCHEMA_READY
    if INSPECTION_COMPLETION_SCHEMA_READY:
        return
    acquire_schema_migration_lock(cur)
    cur.execute(
        """
        ALTER TABLE inspections
        ADD COLUMN IF NOT EXISTS inspector_completion_status TEXT NOT NULL DEFAULT '待检查人确认';
        """
    )
    cur.execute(
        """
        ALTER TABLE inspections
        ADD COLUMN IF NOT EXISTS inspector_completed_by INTEGER REFERENCES users(id) ON DELETE SET NULL;
        """
    )
    cur.execute(
        """
        ALTER TABLE inspections
        ADD COLUMN IF NOT EXISTS inspector_completed_at TIMESTAMP;
        """
    )
    cur.execute(
        """
        ALTER TABLE inspections
        ADD COLUMN IF NOT EXISTS inspector_completion_source TEXT;
        """
    )
    cur.execute(
        """
        ALTER TABLE inspections
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
        """
    )
    cur.execute(
        """
        UPDATE inspections
        SET inspector_completion_status = '待检查人确认'
        WHERE inspector_completion_status IS NULL
           OR inspector_completion_status NOT IN ('待检查人确认', '已确认完成');
        """
    )
    cur.execute(
        """
        UPDATE inspections
        SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
        WHERE updated_at IS NULL;
        """
    )
    cur.execute(
        """
        UPDATE inspections
        SET sign_status = '已签名确认',
            station_manager_signed_at = COALESCE(
                station_manager_signed_at,
                updated_at,
                created_at,
                CURRENT_TIMESTAMP
            ),
            updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)
        WHERE COALESCE(sign_status, '') <> '已签名确认'
          AND (
              station_manager_signed_at IS NOT NULL
              OR NULLIF(station_manager_signature_path, '') IS NOT NULL
              OR NULLIF(station_manager_signed_name, '') IS NOT NULL
          );
        """
    )
    cur.execute(
        """
        UPDATE inspections
        SET inspector_completion_status = '已确认完成',
            inspector_completed_at = COALESCE(
                inspector_completed_at,
                station_manager_signed_at,
                updated_at,
                created_at,
                CURRENT_TIMESTAMP
            ),
            inspector_completion_source = COALESCE(NULLIF(inspector_completion_source, ''), 'signature'),
            updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)
        WHERE sign_status = '已签名确认'
          AND inspector_completion_status <> '已确认完成';
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_inspections_station_table_month
        ON inspections (station_id, inspection_table_id, inspection_date);
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_inspections_completion_status
        ON inspections (inspector_completion_status, inspection_date);
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS inspection_completion_settings (
            singleton BOOLEAN PRIMARY KEY DEFAULT TRUE,
            auto_complete_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            auto_complete_days INTEGER NOT NULL DEFAULT 7,
            record_uniqueness_period TEXT NOT NULL DEFAULT 'month',
            updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT chk_inspection_completion_singleton CHECK (singleton = TRUE),
            CONSTRAINT chk_inspection_completion_days CHECK (auto_complete_days BETWEEN 1 AND 31)
        );
        """
    )
    cur.execute(
        """
        ALTER TABLE inspection_completion_settings
        ADD COLUMN IF NOT EXISTS record_uniqueness_period TEXT NOT NULL DEFAULT 'month';
        """
    )
    cur.execute(
        """
        UPDATE inspection_completion_settings
        SET record_uniqueness_period = 'month'
        WHERE record_uniqueness_period IS NULL
           OR record_uniqueness_period NOT IN ('week', 'month', 'quarter', 'year');
        """
    )
    cur.execute(
        """
        INSERT INTO inspection_completion_settings (
            singleton,
            auto_complete_enabled,
            auto_complete_days,
            record_uniqueness_period
        )
        VALUES (TRUE, TRUE, %s, %s)
        ON CONFLICT (singleton) DO NOTHING;
        """,
        (DEFAULT_INSPECTION_AUTO_COMPLETE_DAYS, DEFAULT_INSPECTION_RECORD_UNIQUENESS_PERIOD),
    )
    connection = getattr(cur, "connection", None)
    if connection:
        connection.commit()
    INSPECTION_COMPLETION_SCHEMA_READY = True


def serialize_inspection_completion_config(row=None):
    period = str(row.get("record_uniqueness_period") if row else "").strip() or DEFAULT_INSPECTION_RECORD_UNIQUENESS_PERIOD
    if period not in INSPECTION_RECORD_UNIQUENESS_PERIODS:
        period = DEFAULT_INSPECTION_RECORD_UNIQUENESS_PERIOD
    return {
        "auto_complete_enabled": bool(row.get("auto_complete_enabled")) if row else True,
        "auto_complete_days": int(row.get("auto_complete_days") or DEFAULT_INSPECTION_AUTO_COMPLETE_DAYS)
        if row
        else DEFAULT_INSPECTION_AUTO_COMPLETE_DAYS,
        "record_uniqueness_period": period,
        "record_uniqueness_period_label": inspection_period_label(period),
        "updated_by": row.get("updated_by") if row else None,
        "updated_by_username": row.get("updated_by_username") if row else "",
        "updated_by_name": row.get("updated_by_name") if row else "",
        "updated_at": row.get("updated_at") if row else "",
    }


def get_inspection_completion_config(cur):
    ensure_inspection_completion_schema(cur)
    cur.execute(
        """
        SELECT
            s.auto_complete_enabled,
            s.auto_complete_days,
            s.record_uniqueness_period,
            s.updated_by,
            COALESCE(u.username, '') AS updated_by_username,
            COALESCE(u.real_name, '') AS updated_by_name,
            TO_CHAR(s.updated_at, 'YYYY-MM-DD HH24:MI') AS updated_at
        FROM inspection_completion_settings s
        LEFT JOIN users u ON u.id = s.updated_by
        WHERE s.singleton = TRUE
        LIMIT 1;
        """
    )
    return serialize_inspection_completion_config(cur.fetchone())


def save_inspection_completion_config(cur, data, user_id):
    enabled = bool(data.get("auto_complete_enabled", True))
    period = str(
        data.get("record_uniqueness_period") or DEFAULT_INSPECTION_RECORD_UNIQUENESS_PERIOD
    ).strip()
    if period not in INSPECTION_RECORD_UNIQUENESS_PERIODS:
        raise ValueError("巡检记录唯一周期参数不合法。")
    try:
        days = int(data.get("auto_complete_days", DEFAULT_INSPECTION_AUTO_COMPLETE_DAYS))
    except (TypeError, ValueError):
        raise ValueError("自动确认天数必须是数字。")
    if days < 1 or days > 31:
        raise ValueError("自动确认天数需设置为 1-31 天。")

    ensure_inspection_completion_schema(cur)
    cur.execute(
        """
        INSERT INTO inspection_completion_settings (
            singleton,
            auto_complete_enabled,
            auto_complete_days,
            record_uniqueness_period,
            updated_by,
            updated_at
        )
        VALUES (TRUE, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (singleton)
        DO UPDATE SET
            auto_complete_enabled = EXCLUDED.auto_complete_enabled,
            auto_complete_days = EXCLUDED.auto_complete_days,
            record_uniqueness_period = EXCLUDED.record_uniqueness_period,
            updated_by = EXCLUDED.updated_by,
            updated_at = CURRENT_TIMESTAMP;
        """,
        (enabled, days, period, user_id or None),
    )
    return get_inspection_completion_config(cur)


def auto_complete_overdue_inspections(cur):
    config = get_inspection_completion_config(cur)
    if not config["auto_complete_enabled"]:
        return 0

    cutoff_date = beijing_today() - timedelta(days=config["auto_complete_days"])
    cur.execute(
        """
        UPDATE inspections
        SET inspector_completion_status = %s,
            inspector_completed_by = NULL,
            inspector_completed_at = COALESCE(inspector_completed_at, CURRENT_TIMESTAMP),
            inspector_completion_source = 'auto',
            updated_at = CURRENT_TIMESTAMP
        WHERE inspector_completion_status <> %s
          AND inspection_date <= %s
          AND COALESCE(sign_status, '') <> '已签名确认'
          AND COALESCE(inspector_completion_source, '') <> 'admin_reopen';
        """,
        (INSPECTION_COMPLETION_DONE, INSPECTION_COMPLETION_DONE, cutoff_date),
    )
    return cur.rowcount


def normalize_inspection_period(value):
    period = str(value or DEFAULT_INSPECTION_RECORD_UNIQUENESS_PERIOD).strip()
    if period not in INSPECTION_RECORD_UNIQUENESS_PERIODS:
        return DEFAULT_INSPECTION_RECORD_UNIQUENESS_PERIOD
    return period


def inspection_period_label(period):
    return {
        "week": "自然周",
        "month": "自然月",
        "quarter": "自然季度",
        "year": "自然年",
    }.get(normalize_inspection_period(period), "自然月")


def inspection_period_scope_text(period):
    return {
        "week": "本自然周",
        "month": "本自然月",
        "quarter": "本自然季度",
        "year": "本自然年",
    }.get(normalize_inspection_period(period), "本自然月")


def get_inspection_period_range(target_date, period=None):
    period = normalize_inspection_period(period)
    if isinstance(target_date, str):
        target_date = datetime.strptime(target_date, "%Y-%m-%d").date()
    if period == "week":
        period_start = target_date - timedelta(days=target_date.weekday())
        period_end = period_start + timedelta(days=7)
    elif period == "quarter":
        start_month = ((target_date.month - 1) // 3) * 3 + 1
        period_start = target_date.replace(month=start_month, day=1)
        if start_month == 10:
            period_end = period_start.replace(year=period_start.year + 1, month=1)
        else:
            period_end = period_start.replace(month=start_month + 3)
    elif period == "year":
        period_start = target_date.replace(month=1, day=1)
        period_end = period_start.replace(year=period_start.year + 1)
    else:
        period_start = target_date.replace(day=1)
        if period_start.month == 12:
            period_end = period_start.replace(year=period_start.year + 1, month=1)
        else:
            period_end = period_start.replace(month=period_start.month + 1)
    return period_start, period_end


def format_inspection_period_key(target_date, period=None):
    period = normalize_inspection_period(period)
    if isinstance(target_date, str):
        target_date = datetime.strptime(target_date, "%Y-%m-%d").date()
    period_start, _ = get_inspection_period_range(target_date, period)
    if period == "week":
        iso_year, iso_week, _ = target_date.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    if period == "quarter":
        quarter = ((target_date.month - 1) // 3) + 1
        return f"{target_date.year}-Q{quarter}"
    if period == "year":
        return str(target_date.year)
    return period_start.strftime("%Y-%m")


def format_inspection_period_label(target_date, period=None):
    period = normalize_inspection_period(period)
    if isinstance(target_date, str):
        target_date = datetime.strptime(target_date, "%Y-%m-%d").date()
    if period == "week":
        period_start, period_end = get_inspection_period_range(target_date, period)
        return f"{period_start.strftime('%Y-%m-%d')}至{(period_end - timedelta(days=1)).strftime('%Y-%m-%d')}"
    if period == "quarter":
        quarter = ((target_date.month - 1) // 3) + 1
        return f"{target_date.year}年第{quarter}季度"
    if period == "year":
        return f"{target_date.year}年"
    return f"{target_date.year}年{target_date.month}月"


def lock_inspection_period_scope(cur, station_id, inspection_table_id, target_date, period=None):
    period = normalize_inspection_period(period)
    period_start, _ = get_inspection_period_range(target_date, period)
    lock_seed = f"inspection-period:{period}:{station_id}:{inspection_table_id}:{period_start.isoformat()}"
    lock_key = int.from_bytes(
        hashlib.blake2b(lock_seed.encode("utf-8"), digest_size=8).digest(),
        byteorder="big",
        signed=True,
    )
    cur.execute("SELECT pg_advisory_xact_lock(%s);", (lock_key,))


def find_period_inspection(cur, station_id, inspection_table_id, target_date, period=None):
    period_start, period_end = get_inspection_period_range(target_date, period)
    cur.execute(
        """
        SELECT
            id,
            batch_id,
            inspection_date,
            inspector_completion_status,
            inspector_completed_at
        FROM inspections
        WHERE station_id = %s
          AND inspection_table_id = %s
          AND inspection_date >= %s
          AND inspection_date < %s
        ORDER BY
            CASE WHEN inspector_completion_status = %s THEN 1 ELSE 0 END ASC,
            inspection_date ASC,
            id ASC
        LIMIT 1;
        """,
        (
            station_id,
            inspection_table_id,
            period_start,
            period_end,
            INSPECTION_COMPLETION_DONE,
        ),
    )
    return cur.fetchone()


def get_or_create_period_inspection(
    cur,
    station_id,
    inspector_id,
    inspection_table_id,
    target_date,
):
    period = get_inspection_completion_config(cur)["record_uniqueness_period"]
    lock_inspection_period_scope(cur, station_id, inspection_table_id, target_date, period)
    inspection = find_period_inspection(cur, station_id, inspection_table_id, target_date, period)
    if inspection:
        if inspection.get("inspector_completion_status") == INSPECTION_COMPLETION_DONE:
            raise ValueError(f"该站点{inspection_period_scope_text(period)}已完成确认该检查表，不能继续登记。")
        return inspection["id"]

    batch_id = get_or_create_inspection_batch(cur, station_id, inspector_id, target_date)
    return create_inspection_record(
        cur,
        station_id,
        inspector_id,
        inspection_table_id,
        batch_id,
        target_date,
    )


def inspection_completion_source_label(value):
    return {
        "manual": "检查人手动确认",
        "auto": "系统自动确认",
        "admin": "后台管理确认",
        "signature": "站经理签字确认",
        "admin_reopen": "后台恢复未完成",
    }.get(str(value or ""), "")


def sync_signed_inspections_completion(cur):
    cur.execute(
        """
        UPDATE inspections
        SET inspector_completion_status = %s,
            inspector_completed_at = COALESCE(
                inspector_completed_at,
                station_manager_signed_at,
                updated_at,
                created_at,
                CURRENT_TIMESTAMP
            ),
            inspector_completion_source = COALESCE(NULLIF(inspector_completion_source, ''), 'signature'),
            updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)
        WHERE sign_status = '已签名确认'
          AND inspector_completion_status <> %s;
        """,
        (INSPECTION_COMPLETION_DONE, INSPECTION_COMPLETION_DONE),
    )
    return cur.rowcount


def complete_inspection_record(cur, inspection_id, user_id=None, source="manual"):
    normalized_source = source if source in INSPECTION_COMPLETION_SOURCES else "manual"
    cur.execute(
        """
        UPDATE inspections
        SET inspector_completion_status = %s,
            inspector_completed_by = %s,
            inspector_completed_at = CURRENT_TIMESTAMP,
            inspector_completion_source = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
          AND inspector_completion_status <> %s;
        """,
        (
            INSPECTION_COMPLETION_DONE,
            user_id,
            normalized_source,
            inspection_id,
            INSPECTION_COMPLETION_DONE,
        ),
    )
    return cur.rowcount


def reopen_inspection_record(cur, inspection_id):
    cur.execute(
        """
        UPDATE inspections
        SET inspector_completion_status = %s,
            inspector_completed_by = NULL,
            inspector_completed_at = NULL,
            inspector_completion_source = 'admin_reopen',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
          AND COALESCE(sign_status, '') <> '已签名确认';
        """,
        (INSPECTION_COMPLETION_PENDING, inspection_id),
    )
    return cur.rowcount


def user_participated_in_inspection(cur, inspection_id, user_id):
    cur.execute(
        """
        SELECT 1
        WHERE EXISTS (
            SELECT 1
            FROM inspections ins
            WHERE ins.id = %s
              AND ins.inspector_id = %s
        )
        OR EXISTS (
            SELECT 1
            FROM issues i
            WHERE i.inspection_id = %s
              AND i.inspector_id = %s
        )
        LIMIT 1;
        """,
        (inspection_id, user_id, inspection_id, user_id),
    )
    return bool(cur.fetchone())


# === Permission helpers ===
def get_user_by_id(cur, user_id):
    cur.execute(
        """
        SELECT id, username, role, real_name, phone, station_id
        FROM users
        WHERE id = %s
        LIMIT 1;
        """,
        (user_id,),
    )
    return cur.fetchone()


def ensure_user_security_schema(cur):
    cur.execute(
        """
        INSERT INTO users (username, password, role, real_name, phone, station_id)
        VALUES ('root', %s, 'root', '系统管理员', '18801800773', NULL)
        ON CONFLICT (username) DO NOTHING;
        """,
        (DEFAULT_INITIAL_PASSWORD,),
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_permissions (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            permission_key TEXT NOT NULL,
            is_allowed BOOLEAN NOT NULL,
            updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, permission_key)
        );
        """
    )


def ensure_ai_usage_schema(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_usage_logs (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            username TEXT,
            real_name TEXT,
            role TEXT,
            usage_module TEXT NOT NULL,
            usage_action TEXT NOT NULL,
            model TEXT NOT NULL,
            base_url TEXT DEFAULT 'https://api.deepseek.com',
            ai_called BOOLEAN NOT NULL DEFAULT FALSE,
            ai_generated BOOLEAN NOT NULL DEFAULT FALSE,
            success BOOLEAN NOT NULL DEFAULT FALSE,
            fallback_used BOOLEAN NOT NULL DEFAULT FALSE,
            status_code INTEGER,
            prompt_chars INTEGER NOT NULL DEFAULT 0,
            prompt_chinese_chars INTEGER NOT NULL DEFAULT 0,
            prompt_other_chars INTEGER NOT NULL DEFAULT 0,
            completion_chars INTEGER NOT NULL DEFAULT 0,
            completion_chinese_chars INTEGER NOT NULL DEFAULT 0,
            completion_other_chars INTEGER NOT NULL DEFAULT 0,
            total_chars INTEGER NOT NULL DEFAULT 0,
            input_tokens_est NUMERIC(14, 2) NOT NULL DEFAULT 0,
            output_tokens_est NUMERIC(14, 2) NOT NULL DEFAULT 0,
            total_tokens_est NUMERIC(14, 2) NOT NULL DEFAULT 0,
            input_cost_est NUMERIC(14, 6) NOT NULL DEFAULT 0,
            output_cost_est NUMERIC(14, 6) NOT NULL DEFAULT 0,
            total_cost_est NUMERIC(14, 6) NOT NULL DEFAULT 0,
            message TEXT,
            request_summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ai_usage_logs_created_at
        ON ai_usage_logs(created_at DESC);
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ai_usage_logs_user_id
        ON ai_usage_logs(user_id);
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ai_usage_logs_module_action
        ON ai_usage_logs(usage_module, usage_action);
        """
    )


def get_number(value, default=0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def get_integer(value, default=0):
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def record_ai_usage_log(
    cur,
    user,
    ai_result,
    usage_module,
    usage_action,
    request_summary="",
):
    ensure_ai_usage_schema(cur)
    usage = (ai_result or {}).get("usage") or {}
    model = str(usage.get("model") or "deepseek-v4-pro").strip() or "deepseek-v4-pro"
    base_url = str(usage.get("base_url") or "https://api.deepseek.com").strip()
    message = str((ai_result or {}).get("message") or "")[:500]
    user = user or {}
    cur.execute(
        """
        INSERT INTO ai_usage_logs (
            user_id,
            username,
            real_name,
            role,
            usage_module,
            usage_action,
            model,
            base_url,
            ai_called,
            ai_generated,
            success,
            fallback_used,
            status_code,
            prompt_chars,
            prompt_chinese_chars,
            prompt_other_chars,
            completion_chars,
            completion_chinese_chars,
            completion_other_chars,
            total_chars,
            input_tokens_est,
            output_tokens_est,
            total_tokens_est,
            input_cost_est,
            output_cost_est,
            total_cost_est,
            message,
            request_summary
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        );
        """,
        (
            user.get("id"),
            user.get("username"),
            user.get("real_name"),
            user.get("role"),
            str(usage_module or "AI功能")[:80],
            str(usage_action or "AI调用")[:80],
            model[:80],
            base_url[:160],
            bool(usage.get("ai_called")),
            bool((ai_result or {}).get("generated")),
            bool(usage.get("success")),
            bool(usage.get("fallback_used")),
            usage.get("status_code"),
            get_integer(usage.get("prompt_chars")),
            get_integer(usage.get("prompt_chinese_chars")),
            get_integer(usage.get("prompt_other_chars")),
            get_integer(usage.get("completion_chars")),
            get_integer(usage.get("completion_chinese_chars")),
            get_integer(usage.get("completion_other_chars")),
            get_integer(usage.get("total_chars")),
            get_number(usage.get("input_tokens_est")),
            get_number(usage.get("output_tokens_est")),
            get_number(usage.get("total_tokens_est")),
            get_number(usage.get("input_cost_est")),
            get_number(usage.get("output_cost_est")),
            get_number(usage.get("total_cost_est")),
            message,
            str(request_summary or "")[:500],
        ),
    )


def serialize_ai_usage_row(row):
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "username": row["username"],
        "real_name": row["real_name"],
        "role": row["role"],
        "usage_module": row["usage_module"],
        "usage_action": row["usage_action"],
        "model": row["model"],
        "base_url": row["base_url"],
        "ai_called": bool(row["ai_called"]),
        "ai_generated": bool(row["ai_generated"]),
        "success": bool(row["success"]),
        "fallback_used": bool(row["fallback_used"]),
        "status_code": row["status_code"],
        "prompt_chars": get_integer(row["prompt_chars"]),
        "prompt_chinese_chars": get_integer(row["prompt_chinese_chars"]),
        "prompt_other_chars": get_integer(row["prompt_other_chars"]),
        "completion_chars": get_integer(row["completion_chars"]),
        "completion_chinese_chars": get_integer(row["completion_chinese_chars"]),
        "completion_other_chars": get_integer(row["completion_other_chars"]),
        "total_chars": get_integer(row["total_chars"]),
        "input_tokens_est": get_number(row["input_tokens_est"]),
        "output_tokens_est": get_number(row["output_tokens_est"]),
        "total_tokens_est": get_number(row["total_tokens_est"]),
        "input_cost_est": get_number(row["input_cost_est"]),
        "output_cost_est": get_number(row["output_cost_est"]),
        "total_cost_est": get_number(row["total_cost_est"]),
        "message": row["message"] or "",
        "request_summary": row["request_summary"] or "",
        "created_at": row["created_at"],
    }


def build_ai_usage_aggregate(rows, group_keys, label_builder):
    grouped = {}
    for row in rows:
        key = tuple(str(row.get(item) or "") for item in group_keys)
        if key not in grouped:
            grouped[key] = {
                "key": "||".join(key),
                "label": label_builder(row),
                "calls": 0,
                "ai_called": 0,
                "success": 0,
                "fallback": 0,
                "total_chars": 0,
                "total_tokens_est": 0.0,
                "total_cost_est": 0.0,
            }
        item = grouped[key]
        item["calls"] += 1
        item["ai_called"] += 1 if row.get("ai_called") else 0
        item["success"] += 1 if row.get("success") else 0
        item["fallback"] += 1 if row.get("fallback_used") else 0
        item["total_chars"] += get_integer(row.get("total_chars"))
        item["total_tokens_est"] += get_number(row.get("total_tokens_est"))
        item["total_cost_est"] += get_number(row.get("total_cost_est"))

    return sorted(
        (
            {
                **item,
                "total_tokens_est": round(item["total_tokens_est"], 2),
                "total_cost_est": round(item["total_cost_est"], 6),
            }
            for item in grouped.values()
        ),
        key=lambda item: (-item["calls"], -item["total_cost_est"], item["label"]),
    )


def build_ai_usage_summary(rows):
    return {
        "total_calls": len(rows),
        "ai_called": sum(1 for row in rows if row.get("ai_called")),
        "success": sum(1 for row in rows if row.get("success")),
        "fallback": sum(1 for row in rows if row.get("fallback_used")),
        "prompt_chars": sum(get_integer(row.get("prompt_chars")) for row in rows),
        "completion_chars": sum(get_integer(row.get("completion_chars")) for row in rows),
        "total_chars": sum(get_integer(row.get("total_chars")) for row in rows),
        "input_tokens_est": round(
            sum(get_number(row.get("input_tokens_est")) for row in rows),
            2,
        ),
        "output_tokens_est": round(
            sum(get_number(row.get("output_tokens_est")) for row in rows),
            2,
        ),
        "total_tokens_est": round(
            sum(get_number(row.get("total_tokens_est")) for row in rows),
            2,
        ),
        "input_cost_est": round(
            sum(get_number(row.get("input_cost_est")) for row in rows),
            6,
        ),
        "output_cost_est": round(
            sum(get_number(row.get("output_cost_est")) for row in rows),
            6,
        ),
        "total_cost_est": round(
            sum(get_number(row.get("total_cost_est")) for row in rows),
            6,
        ),
    }


def is_root_user(user):
    return bool(user and user.get("role") == "root")


def is_supervisor_like(user):
    return bool(user and user.get("role") in ("root", "supervisor"))


def is_station_manager(user):
    return bool(user and user.get("role") == "station_manager")


def role_default_permission(role, permission_key):
    for item in PERMISSION_CATALOG:
        if item["key"] == permission_key:
            return bool(item.get("defaults", {}).get(role, False))
    return False


def enforce_exclusive_permissions(permission_map, role=None):
    normalized = dict(permission_map or {})
    for own_key, all_key in PERMISSION_EXCLUSIVE_GROUPS:
        if not normalized.get(own_key) or not normalized.get(all_key):
            continue

        prefer_all = role_default_permission(role, all_key) and not role_default_permission(role, own_key)
        if prefer_all:
            normalized[own_key] = False
        else:
            normalized[all_key] = False

    for child_key, parent_key in PERMISSION_DEPENDENCIES.items():
        if normalized.get(child_key) and not normalized.get(parent_key):
            normalized[child_key] = False

    for child_key, parent_keys in PERMISSION_ANY_DEPENDENCIES.items():
        if normalized.get(child_key) and not any(normalized.get(parent_key) for parent_key in parent_keys):
            normalized[child_key] = False

    return normalized


def get_permission_overrides(cur, user_id):
    ensure_user_security_schema(cur)
    cur.execute(
        """
        SELECT permission_key, is_allowed
        FROM user_permissions
        WHERE user_id = %s;
        """,
        (user_id,),
    )
    return {row["permission_key"]: bool(row["is_allowed"]) for row in cur.fetchall()}


def get_effective_permissions(cur, user):
    if not user:
        return {}

    if is_root_user(user):
        return {item["key"]: True for item in PERMISSION_CATALOG}

    overrides = get_permission_overrides(cur, user["id"])
    role = user.get("role")
    permissions = {
        item["key"]: overrides.get(item["key"], role_default_permission(role, item["key"]))
        for item in PERMISSION_CATALOG
    }
    return enforce_exclusive_permissions(permissions, role)


def has_permission(cur, user, permission_key):
    if permission_key not in PERMISSION_KEYS:
        return False
    if is_root_user(user):
        return True
    if not user:
        return False
    return bool(get_effective_permissions(cur, user).get(permission_key))


def can_manage_plan(cur, user):
    return has_permission(cur, user, "manage_inspection_plans")


def can_manage_system(cur, user, permission_key):
    return is_root_user(user) or has_permission(cur, user, permission_key)


def can_view_inspection_standards(cur, user):
    return has_permission(cur, user, "view_inspection_standards")


def can_view_checklist_originals(cur, user):
    return has_permission(cur, user, "view_checklist_originals")


def can_view_all_inspection_issues(cur, user):
    return bool(get_effective_permissions(cur, user).get("view_all_inspection_issues"))


def can_view_own_inspection_issues(cur, user):
    return bool(get_effective_permissions(cur, user).get("view_own_inspection_issues"))


def can_edit_inspection_issues(cur, user):
    return has_permission(cur, user, "edit_inspection_issues")


def can_delete_inspection_issues(cur, user):
    return has_permission(cur, user, "delete_inspection_issues")


def can_audit_inspection_issues(cur, user):
    return has_permission(cur, user, "audit_inspection_issues")


def can_change_issue_inspector(user):
    return is_root_user(user)


def normalize_issue_audit_status(value):
    status = str(value or "pending").strip().lower()
    return status if status in ISSUE_AUDIT_STATUS_OPTIONS else "pending"


def is_issue_audit_rejected(issue):
    return normalize_issue_audit_status((issue or {}).get("audit_status")) == "rejected"


def is_issue_audit_pending(issue):
    return normalize_issue_audit_status((issue or {}).get("audit_status")) == "pending"


def canonical_issue_status(value):
    normalized = str(value or "").strip()
    return ISSUE_STATUS_ALIASES.get(normalized, normalized)


def is_closed_issue_status(value):
    return canonical_issue_status(value) == "已闭环"


def canonical_issue_result(value):
    normalized = str(value or "").strip()
    return ISSUE_RESULT_ALIASES.get(normalized, normalized)


def issue_created_by_user(user, issue):
    if not user or not issue:
        return False
    return str(issue.get("inspector_id") or "") == str(user.get("id") or "")


def issue_station_rectification_started(issue):
    if not issue:
        return False
    if is_issue_audit_rejected(issue):
        return True
    return (
        canonical_issue_status(issue.get("status")) != "待整改"
        or normalize_issue_result_for_response(issue.get("rectification_result"))
        is not None
    )


def can_user_use_creator_issue_controls(user, issue):
    return issue_created_by_user(user, issue) and not issue_station_rectification_started(
        issue
    )


def can_user_update_rectification_photo(user, issue, can_explicit_edit=False):
    if not user or not issue:
        return False
    if is_issue_audit_rejected(issue):
        return False
    if not normalize_issue_result_for_response(issue.get("rectification_result")):
        return False
    if is_root_user(user):
        return True
    if is_closed_issue_status(issue.get("status")):
        return False
    if can_explicit_edit:
        return True
    return (
        is_station_manager(user)
        and str(user.get("station_id") or "") == str(issue.get("station_id") or "")
        and canonical_issue_status(issue.get("status")) == "待复核"
    )


def normalize_issue_result_for_response(value):
    normalized = canonical_issue_result(value)
    if normalized == "未整改":
        return None
    return normalized or None


def is_issue_inspection_signed(issue):
    if not issue:
        return False
    return (
        issue.get("inspection_sign_status") == "已签名确认"
        or bool(issue.get("station_manager_signed_at"))
        or bool(issue.get("station_manager_signature_path"))
        or bool(issue.get("station_manager_signed_name"))
    )


def display_issue_status(issue):
    status = canonical_issue_status((issue or {}).get("status"))
    if is_issue_audit_pending(issue):
        return "待审核"
    if status == "待整改" and not is_issue_inspection_signed(issue):
        return "待签名"
    return status


def normalize_issue_row_for_response(
    row, user=None, can_explicit_edit=False, can_explicit_delete=False, can_explicit_audit=False
):
    data = dict(row)
    data["inspector_user_id"] = data.get("inspector_id")
    data["audit_status"] = normalize_issue_audit_status(data.get("audit_status"))
    data["audit_status_label"] = ISSUE_AUDIT_STATUS_LABELS.get(
        data["audit_status"],
        "待审核",
    )
    data["is_excellent"] = bool(data.get("is_excellent")) and data["audit_status"] != "rejected"
    if "status" in data:
        data["status"] = canonical_issue_status(data.get("status"))
        data["raw_status"] = data["status"]
        data["workflow_status"] = data["status"]
    for key in ("rectification_result", "review_result"):
        if key in data:
            data[key] = normalize_issue_result_for_response(data.get(key))
    creator_can_modify = can_user_use_creator_issue_controls(user, data)
    closed = is_closed_issue_status(data.get("status"))
    inspection_signed = is_issue_inspection_signed(data)
    issue_mutation_locked = inspection_signed
    data["inspection_signed"] = bool(inspection_signed)
    data["inspection_locked"] = bool(issue_mutation_locked)
    if inspection_signed:
        data["operation_lock_reason"] = "已签字不可操作"
    else:
        data["operation_lock_reason"] = ""
    data["can_edit_issue_workflow"] = bool(
        not issue_mutation_locked and (is_root_user(user) or (can_explicit_edit and not closed))
    )
    data["can_edit_issue"] = bool(
        not issue_mutation_locked and (is_root_user(user) or ((can_explicit_edit or creator_can_modify) and not closed))
    )
    data["can_delete_issue"] = bool(
        not issue_mutation_locked
        and (
            is_root_user(user)
            or ((can_explicit_delete or creator_can_modify) and not closed)
        )
    )
    data["can_update_rectification_photo"] = can_user_update_rectification_photo(
        user, data, can_explicit_edit
    )
    data["can_change_issue_inspector"] = bool(
        not issue_mutation_locked and can_change_issue_inspector(user)
    )
    data["can_audit_issue"] = bool(can_explicit_audit and not inspection_signed)
    data["can_mark_excellent_issue"] = bool(can_explicit_audit and data["audit_status"] != "rejected")
    if "status" in data:
        data["status"] = display_issue_status(data)
    data.pop("inspector_id", None)
    return data


def ensure_issue_export_schema(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS issue_export_tasks (
            task_id TEXT PRIMARY KEY,
            created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'pending',
            selected_count INTEGER NOT NULL DEFAULT 0,
            exported_count INTEGER NOT NULL DEFAULT 0,
            filter_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
            file_path TEXT,
            download_filename TEXT,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            expires_at TIMESTAMP NOT NULL
        );
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_issue_export_tasks_created_by
        ON issue_export_tasks (created_by, created_at DESC);
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_issue_export_tasks_expires_at
        ON issue_export_tasks (expires_at);
        """
    )


def cleanup_expired_issue_exports(cur):
    ensure_issue_export_schema(cur)
    cur.execute(
        """
        SELECT file_path
        FROM issue_export_tasks
        WHERE expires_at < CURRENT_TIMESTAMP;
        """
    )
    for row in cur.fetchall():
        if row.get("file_path"):
            remove_storage_file(row["file_path"])
    cur.execute("DELETE FROM issue_export_tasks WHERE expires_at < CURRENT_TIMESTAMP;")

    os.makedirs(ISSUE_EXPORTS_STORAGE_DIR, exist_ok=True)
    cutoff = time.time() - ISSUE_EXPORT_RETENTION_DAYS * 24 * 60 * 60
    for name in os.listdir(ISSUE_EXPORTS_STORAGE_DIR):
        path = os.path.abspath(os.path.join(ISSUE_EXPORTS_STORAGE_DIR, name))
        if os.path.commonpath([os.path.abspath(ISSUE_EXPORTS_STORAGE_DIR), path]) != os.path.abspath(ISSUE_EXPORTS_STORAGE_DIR):
            continue
        if os.path.isfile(path) and path.lower().endswith(".xlsx") and os.path.getmtime(path) < cutoff:
            try:
                os.remove(path)
            except OSError:
                pass


def maybe_cleanup_expired_issue_exports():
    global issue_export_cleanup_last_run
    now = time.time()
    if now - issue_export_cleanup_last_run < ISSUE_EXPORT_CLEANUP_INTERVAL_SECONDS:
        return
    if not issue_export_cleanup_lock.acquire(blocking=False):
        return

    conn = None
    cur = None
    try:
        if now - issue_export_cleanup_last_run < ISSUE_EXPORT_CLEANUP_INTERVAL_SECONDS:
            return
        conn = get_db_connection()
        cur = conn.cursor()
        cleanup_expired_issue_exports(cur)
        conn.commit()
        issue_export_cleanup_last_run = now
    except Exception:
        if conn:
            conn.rollback()
    finally:
        close_db_resources(cur, conn)
        issue_export_cleanup_lock.release()


def normalize_issue_export_ids(raw_ids):
    if not isinstance(raw_ids, list):
        raise ValueError("导出任务缺少筛选后的问题ID列表。")
    normalized = []
    seen = set()
    for raw_id in raw_ids:
        try:
            issue_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if issue_id <= 0 or issue_id in seen:
            continue
        seen.add(issue_id)
        normalized.append(issue_id)
    if not normalized:
        raise ValueError("当前筛选结果为空，不能导出。")
    return normalized


def normalize_issue_export_filter_summary(raw_summary):
    if not isinstance(raw_summary, dict):
        return {}
    allowed_keys = {
        "month",
        "date",
        "region",
        "station",
        "stationManager",
        "inspector",
        "inspectionTableName",
        "standardId",
        "standardDetail",
        "rectificationResult",
        "reviewResult",
        "status",
    }
    return {
        key: str(value or "").strip()
        for key, value in raw_summary.items()
        if key in allowed_keys and str(value or "").strip()
    }


def get_issue_export_task_for_user(cur, task_id, user):
    cur.execute(
        """
        SELECT
            task_id,
            created_by,
            status,
            selected_count,
            exported_count,
            filter_summary,
            file_path,
            download_filename,
            error_message,
            TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI') AS created_at,
            TO_CHAR(updated_at, 'YYYY-MM-DD HH24:MI') AS updated_at,
            TO_CHAR(completed_at, 'YYYY-MM-DD HH24:MI') AS completed_at,
            TO_CHAR(expires_at, 'YYYY-MM-DD HH24:MI') AS expires_at
        FROM issue_export_tasks
        WHERE task_id = %s
        LIMIT 1;
        """,
        (task_id,),
    )
    task = cur.fetchone()
    if not task:
        raise LookupError("导出任务不存在或已过期。")
    if not is_root_user(user) and str(task["created_by"]) != str(user["id"]):
        raise PermissionError("当前账号无权查看该导出任务。")
    return task


def serialize_issue_export_task(task):
    status = task.get("status")
    task_id = task.get("task_id")
    return {
        "task_id": task_id,
        "status": status,
        "selected_count": int(task.get("selected_count") or 0),
        "exported_count": int(task.get("exported_count") or 0),
        "filter_summary": task.get("filter_summary") or {},
        "download_filename": task.get("download_filename") or "",
        "download_url": f"/api/issues/export-tasks/{task_id}/download" if status == "completed" else "",
        "error_message": task.get("error_message") or "",
        "created_at": task.get("created_at") or "",
        "updated_at": task.get("updated_at") or "",
        "completed_at": task.get("completed_at") or "",
        "expires_at": task.get("expires_at") or "",
    }


def fetch_issue_export_rows(cur, user, issue_ids):
    where_parts = ["i.id = ANY(%s)"]
    params = [issue_ids]

    can_view_all = can_view_all_inspection_issues(cur, user)
    can_view_own = can_view_own_inspection_issues(cur, user)
    if can_view_all:
        pass
    elif can_view_own:
        if not user.get("station_id"):
            where_parts.append("COALESCE(i.inspector_id, ins.inspector_id) = %s")
            params.append(user["id"])
        else:
            where_parts.append("(i.station_id = %s OR COALESCE(i.inspector_id, ins.inspector_id) = %s)")
            params.extend([user["station_id"], user["id"]])
    else:
        where_parts.append("COALESCE(i.inspector_id, ins.inspector_id) = %s")
        params.append(user["id"])

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
                issue_inspector.real_name AS inspector,
                issue_inspector.phone AS inspector_phone,
                t.table_name AS inspection_table_name,
                i.internal_standard_id,
                i.standard_id,
                i.internal_standard_detail_text,
                i.standard_detail_text,
                i.description,
                CASE
                    WHEN COALESCE(i.is_excellent, FALSE)
                         AND COALESCE(i.audit_status, 'pending') <> 'rejected'
                    THEN '★'
                    ELSE ''
                END AS is_excellent,
                i.rectification_result,
                i.rectification_note,
                i.review_result,
                i.review_note,
                CASE
                    WHEN COALESCE(i.audit_status, 'pending') = 'pending'
                    THEN '待审核'
                    WHEN i.status = '待整改'
                         AND NOT (
                             ins.sign_status = '已签名确认'
                             OR ins.station_manager_signed_at IS NOT NULL
                             OR COALESCE(ins.station_manager_signature_path, '') <> ''
                             OR COALESCE(ins.station_manager_signed_name, '') <> ''
                         )
                    THEN '待签名'
                    ELSE i.status
                END AS status
            FROM issues i
            JOIN inspections ins ON i.inspection_id = ins.id
            JOIN stations s ON i.station_id = s.id
            JOIN inspection_tables t ON i.inspection_table_id = t.id
            JOIN users issue_inspector ON COALESCE(i.inspector_id, ins.inspector_id) = issue_inspector.id
            WHERE {where_clause}
            ORDER BY i.id DESC;
            """
        ).format(where_clause=sql.SQL(" AND ").join(sql.SQL(part) for part in where_parts)),
        params,
    )
    return cur.fetchall()


ISSUE_EXPORT_COLUMNS = [
    ("ID", "id"),
    ("检查月度", "month"),
    ("检查时间", "time"),
    ("站点所属地", "region"),
    ("站点名称", "station"),
    ("站点负责人", "station_manager"),
    ("站点负责人手机号", "station_manager_phone"),
    ("检查人员", "inspector"),
    ("检查人员手机号", "inspector_phone"),
    ("检查表", "inspection_table_name"),
    ("内部规范ID", "internal_standard_id"),
    ("外部规范ID", "standard_id"),
    ("内部规范详情", "internal_standard_detail_text"),
    ("外部规范详情", "standard_detail_text"),
    ("问题描述", "description"),
    ("优秀问题", "is_excellent"),
    ("问题照片", "issue_photo"),
    ("站经理整改结果", "rectification_result"),
    ("站点反馈整改说明", "rectification_note"),
    ("站点反馈整改照片", "rectification_photo"),
    ("督导组复核结果", "review_result"),
    ("督导组复核说明", "review_note"),
    ("督导组复核照片", "review_photo"),
    ("问题状态", "status"),
]


def excel_column_name(index):
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def xlsx_text_cell(value):
    text = "" if value is None else str(value)
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", text)
    return f'<c t="inlineStr"><is><t xml:space="preserve">{xml_escape(text)}</t></is></c>'


def write_issue_export_xlsx(file_path, rows):
    headers = [column[0] for column in ISSUE_EXPORT_COLUMNS]
    now = beijing_now().replace(microsecond=0).isoformat()
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with zipfile.ZipFile(file_path, "w", zipfile.ZIP_DEFLATED) as xlsx:
        xlsx.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>""",
        )
        xlsx.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>""",
        )
        xlsx.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="巡检问题列表" sheetId="1" r:id="rId1"/></sheets>
</workbook>""",
        )
        xlsx.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>""",
        )
        xlsx.writestr(
            "xl/styles.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="1"><font><sz val="11"/><name val="Arial"/></font></fonts>
  <fills count="1"><fill><patternFill patternType="none"/></fill></fills>
  <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>
</styleSheet>""",
        )
        xlsx.writestr(
            "docProps/core.xml",
            f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>巡检问题列表导出</dc:title>
  <dc:creator>业务督导中心数智管理平台</dc:creator>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>""",
        )
        xlsx.writestr(
            "docProps/app.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
  <Application>业务督导中心数智管理平台</Application>
</Properties>""",
        )

        with xlsx.open("xl/worksheets/sheet1.xml", "w") as sheet:
            sheet.write(
                b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                b'<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
                b'<cols>'
            )
            for index, header in enumerate(headers, start=1):
                width = 18
                if header in {"内部规范详情", "外部规范详情", "问题描述", "站点反馈整改说明", "督导组复核说明"}:
                    width = 34
                sheet.write(f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>'.encode("utf-8"))
            sheet.write(b"</cols><sheetData>")
            header_cells = "".join(xlsx_text_cell(header) for header in headers)
            sheet.write(f'<row r="1">{header_cells}</row>'.encode("utf-8"))
            for row_index, row in enumerate(rows, start=2):
                cells = []
                for _header, key in ISSUE_EXPORT_COLUMNS:
                    value = "" if key in {"issue_photo", "rectification_photo", "review_photo"} else row.get(key)
                    cells.append(xlsx_text_cell(value))
                sheet.write(f'<row r="{row_index}">{"".join(cells)}</row>'.encode("utf-8"))
            sheet.write(b"</sheetData><autoFilter ref=\"A1:W1\"/></worksheet>")


def mark_issue_export_task_failed(task_id, message):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_issue_export_schema(cur)
        cur.execute(
            """
            UPDATE issue_export_tasks
            SET status = 'failed',
                error_message = %s,
                updated_at = CURRENT_TIMESTAMP,
                completed_at = CURRENT_TIMESTAMP
            WHERE task_id = %s;
            """,
            (message, task_id),
        )
        conn.commit()
    finally:
        close_db_resources(cur, conn)


def run_issue_export_task(task_id, issue_ids, user_id):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_issue_export_schema(cur)
        cur.execute(
            """
            UPDATE issue_export_tasks
            SET status = 'running',
                updated_at = CURRENT_TIMESTAMP
            WHERE task_id = %s;
            """,
            (task_id,),
        )
        conn.commit()
        user = get_user_by_id(cur, user_id)
        if not user:
            raise ValueError("导出用户不存在。")
        rows = fetch_issue_export_rows(cur, user, issue_ids)
        if not rows:
            raise ValueError("当前筛选结果中没有可导出的数据。")

        now = beijing_now()
        filename = f"巡检问题列表_{now.strftime('%Y%m%d_%H%M%S')}_{task_id[:8]}.xlsx"
        safe_filename = secure_filename(filename) or f"inspection_issues_{task_id[:8]}.xlsx"
        if not safe_filename.lower().endswith(".xlsx"):
            safe_filename = f"inspection_issues_{task_id[:8]}.xlsx"
        abs_path = os.path.join(ISSUE_EXPORTS_STORAGE_DIR, safe_filename)
        relative_path = f"issue_exports/{safe_filename}"
        write_issue_export_xlsx(abs_path, rows)
        cur.execute(
            """
            UPDATE issue_export_tasks
            SET status = 'completed',
                exported_count = %s,
                file_path = %s,
                download_filename = %s,
                updated_at = CURRENT_TIMESTAMP,
                completed_at = CURRENT_TIMESTAMP
            WHERE task_id = %s;
            """,
            (len(rows), relative_path, filename, task_id),
        )
        conn.commit()
    except Exception as exc:
        if conn:
            conn.rollback()
        mark_issue_export_task_failed(task_id, str(exc))
    finally:
        close_db_resources(cur, conn)


def start_issue_export_task(task_id, issue_ids, user_id):
    thread = threading.Thread(
        target=run_issue_export_task,
        args=(task_id, issue_ids, user_id),
        daemon=True,
    )
    thread.start()


ATTENDANCE_MODE_META = {
    "online": {
        "label": "视频检查",
        "short_label": "视频",
        "description": "统计检查表模式为线上的巡检记录。",
    },
    "offline": {
        "label": "现场检查",
        "short_label": "现场",
        "description": "统计检查表模式为线下的巡检记录。",
    },
}


def parse_attendance_month(month_value):
    month_text = str(month_value or "").strip()
    if not month_text:
        today = beijing_today()
        month_text = today.strftime("%Y-%m")
    try:
        month_start = datetime.strptime(month_text, "%Y-%m").date()
    except ValueError as exc:
        raise ValueError("月份格式必须为 YYYY-MM。") from exc
    if month_start.month == 12:
        next_month = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month = month_start.replace(month=month_start.month + 1)
    return month_text, month_start, next_month


def normalize_attendance_mode(mode_value):
    mode = str(mode_value or "all").strip().lower()
    if mode not in {"all", "online", "offline"}:
        raise ValueError("检查方式参数不合法。")
    return mode


def append_unique_item(target_map, key, item):
    if key is None or key == "":
        return
    target_map.setdefault(str(key), item)


def sorted_dict_items(item_map, name_key="name"):
    return sorted(
        item_map.values(),
        key=lambda item: str(item.get(name_key) or item.get("date") or item.get("id") or ""),
    )


def build_attendance_payload(rows, month, mode_filter):
    modes = ["online", "offline"] if mode_filter == "all" else [mode_filter]
    buckets = {
        mode: {
            "mode": mode,
            **ATTENDANCE_MODE_META[mode],
            "people_map": {},
            "groups_map": {},
            "station_ids": set(),
            "inspection_ids": set(),
            "checklist_ids": set(),
        }
        for mode in modes
    }

    for row in rows:
        mode = row.get("checklist_mode") or "online"
        if mode not in buckets:
            continue

        bucket = buckets[mode]
        inspector_id = row.get("inspector_id")
        inspection_date = row.get("inspection_date")
        station_id = row.get("station_id")
        table_id = row.get("inspection_table_id")
        inspection_id = row.get("inspection_id")

        if not inspector_id or not inspection_date:
            continue

        inspector_name = (
            row.get("inspector_name")
            or row.get("inspector_username")
            or row.get("inspector_phone")
            or str(inspector_id)
        )
        person_key = str(inspector_id)
        person = bucket["people_map"].setdefault(
            person_key,
            {
                "inspector_id": inspector_id,
                "inspector_name": inspector_name,
                "username": row.get("inspector_username") or "",
                "phone": row.get("inspector_phone") or "",
                "attendance_dates": set(),
                "inspection_ids": set(),
                "stations_map": {},
                "checklists_map": {},
                "activity_days": {},
            },
        )
        person["attendance_dates"].add(inspection_date)
        person["inspection_ids"].add(inspection_id)
        append_unique_item(
            person["stations_map"],
            station_id,
            {
                "id": station_id,
                "name": row.get("station_name") or "未命名站点",
                "region": row.get("station_region") or "",
            },
        )
        append_unique_item(
            person["checklists_map"],
            table_id,
            {
                "id": table_id,
                "name": row.get("inspection_table_name") or "未命名检查表",
            },
        )
        activity = person["activity_days"].setdefault(
            inspection_date,
            {
                "date": inspection_date,
                "stations_map": {},
                "checklists_map": {},
            },
        )
        append_unique_item(
            activity["stations_map"],
            station_id,
            {
                "id": station_id,
                "name": row.get("station_name") or "未命名站点",
                "region": row.get("station_region") or "",
            },
        )
        append_unique_item(
            activity["checklists_map"],
            table_id,
            {
                "id": table_id,
                "name": row.get("inspection_table_name") or "未命名检查表",
            },
        )

        group_key = f"{inspection_date}:{station_id}"
        group = bucket["groups_map"].setdefault(
            group_key,
            {
                "date": inspection_date,
                "station_id": station_id,
                "station_name": row.get("station_name") or "未命名站点",
                "station_region": row.get("station_region") or "",
                "inspectors_map": {},
                "checklists_map": {},
                "inspection_ids": set(),
            },
        )
        append_unique_item(
            group["inspectors_map"],
            inspector_id,
            {
                "id": inspector_id,
                "name": inspector_name,
                "username": row.get("inspector_username") or "",
                "phone": row.get("inspector_phone") or "",
            },
        )
        append_unique_item(
            group["checklists_map"],
            table_id,
            {
                "id": table_id,
                "name": row.get("inspection_table_name") or "未命名检查表",
            },
        )
        group["inspection_ids"].add(inspection_id)

        bucket["station_ids"].add(station_id)
        bucket["inspection_ids"].add(inspection_id)
        bucket["checklist_ids"].add(table_id)

    mode_payloads = []
    for mode in modes:
        bucket = buckets[mode]
        people = []
        for person in bucket["people_map"].values():
            activity_days = []
            for activity in sorted(person["activity_days"].values(), key=lambda item: item["date"]):
                activity_days.append(
                    {
                        "date": activity["date"],
                        "stations": sorted_dict_items(activity["stations_map"]),
                        "checklists": sorted_dict_items(activity["checklists_map"]),
                    }
                )
            people.append(
                {
                    "inspector_id": person["inspector_id"],
                    "inspector_name": person["inspector_name"],
                    "username": person["username"],
                    "phone": person["phone"],
                    "attendance_days": len(person["attendance_dates"]),
                    "inspection_count": len(person["inspection_ids"]),
                    "station_count": len(person["stations_map"]),
                    "checklist_count": len(person["checklists_map"]),
                    "attendance_dates": sorted(person["attendance_dates"]),
                    "stations": sorted_dict_items(person["stations_map"]),
                    "checklists": sorted_dict_items(person["checklists_map"]),
                    "activity_days": activity_days,
                }
            )
        people.sort(
            key=lambda item: (
                -item["attendance_days"],
                -item["inspection_count"],
                item["inspector_name"],
            )
        )

        groups = []
        for group in bucket["groups_map"].values():
            inspectors = sorted_dict_items(group["inspectors_map"])
            checklists = sorted_dict_items(group["checklists_map"])
            groups.append(
                {
                    "date": group["date"],
                    "station_id": group["station_id"],
                    "station_name": group["station_name"],
                    "station_region": group["station_region"],
                    "inspectors": inspectors,
                    "checklists": checklists,
                    "inspector_count": len(inspectors),
                    "checklist_count": len(checklists),
                    "inspection_count": len(group["inspection_ids"]),
                }
            )
        groups.sort(key=lambda item: (item["date"], item["station_region"], item["station_name"]))

        mode_payloads.append(
            {
                "mode": bucket["mode"],
                "label": bucket["label"],
                "short_label": bucket["short_label"],
                "description": bucket["description"],
                "summary": {
                    "inspector_count": len(people),
                    "attendance_person_days": sum(item["attendance_days"] for item in people),
                    "group_count": len(groups),
                    "station_count": len([item for item in bucket["station_ids"] if item]),
                    "inspection_count": len([item for item in bucket["inspection_ids"] if item]),
                    "checklist_count": len([item for item in bucket["checklist_ids"] if item]),
                },
                "people": people,
                "groups": groups,
            }
        )

    return {
        "month": month,
        "mode": mode_filter,
        "modes": mode_payloads,
    }


def normalize_optional_issue_result(value, field_label):
    normalized = canonical_issue_result(value)
    if not normalized:
        return None
    if normalized not in ISSUE_RESULT_OPTIONS:
        raise ValueError(f"{field_label}参数不合法。")
    return normalized


def can_view_all_inspection_records(cur, user):
    return bool(get_effective_permissions(cur, user).get("view_all_inspection_records"))


def can_view_own_inspection_records(cur, user):
    return bool(get_effective_permissions(cur, user).get("view_own_inspection_records"))


def can_delete_inspection_records(cur, user):
    return has_permission(cur, user, "delete_inspection_records")


def can_reset_inspection_signature(cur, user):
    return has_permission(cur, user, "reset_inspection_signature")


def can_sign_inspection_records(_cur, user):
    return is_station_manager(user) and bool(user.get("station_id"))


def can_view_assessment(cur, user):
    return has_permission(cur, user, "view_assessment")


def can_view_own_certificates(cur, user):
    return bool(get_effective_permissions(cur, user).get("view_own_certificates"))


def can_edit_own_certificates(cur, user):
    return bool(get_effective_permissions(cur, user).get("edit_own_certificates"))


def can_view_all_certificates(cur, user):
    return bool(get_effective_permissions(cur, user).get("view_all_certificates"))


def can_edit_all_certificates(user):
    return is_root_user(user)


def can_view_certificates(cur, user):
    return (
        can_edit_all_certificates(user)
        or can_view_all_certificates(cur, user)
        or can_view_own_certificates(cur, user)
        or can_edit_own_certificates(cur, user)
    )


def normalize_text(value, max_length=None):
    text = str(value or "").strip()
    if max_length and len(text) > max_length:
        return text[:max_length]
    return text


def ensure_feedback_schema(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS system_feedbacks (
            id SERIAL PRIMARY KEY,
            feedback_type TEXT NOT NULL,
            module TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            author_name TEXT,
            author_phone TEXT,
            author_role TEXT,
            accepted_at TIMESTAMP,
            accepted_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cur.execute(
        """
        ALTER TABLE system_feedbacks
            ADD COLUMN IF NOT EXISTS accepted_at TIMESTAMP,
            ADD COLUMN IF NOT EXISTS accepted_by INTEGER REFERENCES users(id) ON DELETE SET NULL;
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS system_feedback_screenshots (
            id SERIAL PRIMARY KEY,
            feedback_id INTEGER NOT NULL REFERENCES system_feedbacks(id) ON DELETE CASCADE,
            file_path TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS system_feedback_comments (
            id SERIAL PRIMARY KEY,
            feedback_id INTEGER NOT NULL REFERENCES system_feedbacks(id) ON DELETE CASCADE,
            comment_text TEXT NOT NULL,
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            author_name TEXT,
            author_phone TEXT,
            author_role TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS system_feedback_read_states (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            last_read_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_system_feedbacks_created_at
        ON system_feedbacks(created_at DESC);
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_system_feedbacks_accepted_at
        ON system_feedbacks(accepted_at DESC);
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_system_feedback_screenshots_feedback_id
        ON system_feedback_screenshots(feedback_id);
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_system_feedback_comments_feedback_id
        ON system_feedback_comments(feedback_id);
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_system_feedback_read_states_last_read
        ON system_feedback_read_states(last_read_at DESC);
        """
    )


def get_or_create_feedback_last_read_at(cur, user_id):
    cur.execute(
        """
        SELECT last_read_at
        FROM system_feedback_read_states
        WHERE user_id = %s
        LIMIT 1;
        """,
        (user_id,),
    )
    row = cur.fetchone()
    if row:
        return row["last_read_at"]

    cur.execute(
        """
        INSERT INTO system_feedback_read_states (user_id, last_read_at, updated_at)
        VALUES (%s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (user_id) DO NOTHING
        RETURNING last_read_at;
        """,
        (user_id,),
    )
    created = cur.fetchone()
    return created["last_read_at"] if created else datetime.now()


def get_feedback_unread_count(cur, user_id):
    last_read_at = get_or_create_feedback_last_read_at(cur, user_id)
    cur.execute(
        """
        SELECT COUNT(*) AS unread_count
        FROM system_feedbacks
        WHERE created_at > %s;
        """,
        (last_read_at,),
    )
    row = cur.fetchone()
    return int(row["unread_count"] or 0)


def mark_feedbacks_read(cur, user_id):
    cur.execute(
        """
        INSERT INTO system_feedback_read_states (user_id, last_read_at, updated_at)
        VALUES (%s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (user_id) DO UPDATE
        SET last_read_at = EXCLUDED.last_read_at,
            updated_at = CURRENT_TIMESTAMP;
        """,
        (user_id,),
    )


def get_current_request_user():
    user = getattr(g, "current_user", None)
    if not user:
        raise PermissionError("请先登录。")
    return user


def build_feedback_author_snapshot(user):
    return {
        "author_name": normalize_text(
            user.get("real_name") or user.get("username") or "未命名用户", 80
        ),
        "author_phone": normalize_text(user.get("phone"), 40),
        "author_role": normalize_text(user.get("role"), 40),
    }


def normalize_feedback_type(value):
    feedback_type = normalize_text(value, 40)
    if feedback_type not in FEEDBACK_TYPE_OPTIONS:
        raise ValueError("反馈类型不正确。")
    return feedback_type


def normalize_feedback_module(value):
    module = normalize_text(value, 40)
    if module not in FEEDBACK_MODULE_OPTIONS:
        raise ValueError("问题模块不正确。")
    return module


def collect_feedback_files(request_files):
    files = []
    for key in ("screenshots", "screenshots[]", "screenshot"):
        files.extend(request_files.getlist(key))
    return [file for file in files if file and file.filename]


def serialize_feedback_comment(row, can_delete=False):
    item = dict(row)
    item["can_delete"] = bool(can_delete)
    return item


def serialize_feedback_row(row, screenshots=None, comments=None, can_delete=False):
    item = dict(row)
    item["screenshots"] = screenshots or []
    item["comments"] = comments or []
    item["can_delete"] = bool(can_delete)
    item["can_accept"] = bool(can_delete)
    item["is_accepted"] = bool(item.get("accepted_at"))
    return item


def validate_new_login_password(username, new_password, confirm_password):
    password = normalize_text(new_password)
    confirm = normalize_text(confirm_password)
    username_text = normalize_text(username)

    if not password:
        raise ValueError("请填写新密码。")
    if len(password) < PASSWORD_MIN_LENGTH or len(password) > PASSWORD_MAX_LENGTH:
        raise ValueError(
            f"新密码长度需为 {PASSWORD_MIN_LENGTH}-{PASSWORD_MAX_LENGTH} 位。"
        )
    if re.search(r"\s", password):
        raise ValueError("新密码不能包含空格。")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise ValueError("新密码需同时包含字母和数字。")
    if password == DEFAULT_INITIAL_PASSWORD:
        raise ValueError("新密码不能继续使用初始密码 123456。")
    if username_text and password.lower() == username_text.lower():
        raise ValueError("新密码不能与用户名相同。")
    if password != confirm:
        raise ValueError("两次输入的新密码不一致。")

    return password


def normalize_decimal_text(value):
    text = normalize_text(value)
    if text == "":
        return None
    return text


def validate_option(value, options, field_label, default_value=None):
    text = normalize_text(value)
    if not text and default_value is not None:
        text = default_value
    if text not in options:
        raise ValueError(f"{field_label}只能选择：{'、'.join(options)}。")
    return text


def normalize_asset_type_option(value):
    text = normalize_text(value)
    if any(keyword in text for keyword in ("股权", "控股", "参股")):
        return "股权"
    if "全资" in text:
        return "全资"
    return text


def normalize_hos_station_code(value):
    text = normalize_text(value, 40).upper()
    if not text:
        raise ValueError("请填写 HOS加油站编码。")
    return text


def normalize_operating_hours(value):
    text = normalize_text(value, 40)
    text = re.sub(r"\s+", "", text)
    text = (
        text.replace("－", "-")
        .replace("—", "-")
        .replace("–", "-")
        .replace("至", "-")
        .replace("到", "-")
    )
    if not text or text in {"24小时", "全天", "全天营业"}:
        return "24小时"

    matched = re.fullmatch(r"(\d{1,2}):([0-5]\d)-(\d{1,2}):([0-5]\d)", text)
    if not matched:
        raise ValueError("营运时间只能选择 24小时 或 HH:MM-HH:MM 格式。")

    start_hour = int(matched.group(1))
    start_minute = matched.group(2)
    end_hour = int(matched.group(3))
    end_minute = matched.group(4)
    if start_hour > 23 or end_hour > 23:
        raise ValueError("营运时间小时必须在 00-23 之间。")

    start_time = f"{start_hour:02d}:{start_minute}"
    end_time = f"{end_hour:02d}:{end_minute}"
    if start_time == end_time:
        raise ValueError("营运时间的开始时间和结束时间不能相同。")

    return f"{start_time}-{end_time}"


def ensure_station_management_columns(cur):
    cur.execute(
        """
        ALTER TABLE stations
        ADD COLUMN IF NOT EXISTS is_consolidated TEXT DEFAULT '否';
        """
    )
    cur.execute(
        """
        ALTER TABLE stations
        ADD COLUMN IF NOT EXISTS online_3_status TEXT DEFAULT '未上线';
        """
    )
    cur.execute(
        """
        ALTER TABLE stations
        ADD COLUMN IF NOT EXISTS hos_station_code TEXT;
        """
    )
    cur.execute(
        """
        UPDATE stations
        SET hos_station_code = NULLIF(UPPER(BTRIM(hos_station_code)), '')
        WHERE hos_station_code IS NOT NULL;
        """
    )
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_stations_hos_station_code_unique
        ON stations (hos_station_code)
        WHERE hos_station_code IS NOT NULL;
        """
    )
    cur.execute(
        """
        ALTER TABLE stations
        ADD COLUMN IF NOT EXISTS landline_phone TEXT;
        """
    )
    cur.execute(
        """
        UPDATE stations
        SET asset_type = CASE
            WHEN asset_type LIKE '%股权%' OR asset_type LIKE '%控股%' OR asset_type LIKE '%参股%' THEN '股权'
            ELSE '全资'
        END
        WHERE asset_type IS NULL OR asset_type NOT IN ('全资', '股权');
        """
    )


def require_management_user(cur, user_id, permission_key):
    user_id = get_authenticated_request_user_id(user_id)
    if not user_id:
        raise PermissionError("缺少用户信息。")

    user = get_user_by_id(cur, user_id)
    if not user:
        raise LookupError("用户不存在。")

    if not can_manage_system(cur, user, permission_key):
        raise PermissionError("当前账号无权操作管理系统。")

    return user


def build_station_payload(data):
    station_name = normalize_text(data.get("station_name"), 120)
    if not station_name:
        raise ValueError("请填写站点名称。")

    station_type = validate_option(
        data.get("station_type"),
        STATION_TYPE_OPTIONS,
        "站点类型",
        "加油站",
    )
    asset_type = validate_option(
        normalize_asset_type_option(data.get("asset_type")),
        STATION_ASSET_TYPE_OPTIONS,
        "资产类型",
        "全资",
    )
    is_consolidated = validate_option(
        data.get("is_consolidated"),
        STATION_CONSOLIDATED_OPTIONS,
        "是否并表",
        "否",
    )
    online_3_status = validate_option(
        data.get("online_3_status"),
        STATION_ONLINE_3_STATUS_OPTIONS,
        "是否上线3.0",
        "未上线",
    )
    status = validate_option(
        data.get("status"),
        STATION_STATUS_OPTIONS,
        "站点状态",
        "营业中",
    )

    return {
        "station_name": station_name,
        "region": normalize_text(data.get("region"), 80) or None,
        "address": normalize_text(data.get("address"), 220) or None,
        "longitude": normalize_decimal_text(data.get("longitude")),
        "latitude": normalize_decimal_text(data.get("latitude")),
        "station_manager_name": normalize_text(data.get("station_manager_name"), 80) or None,
        "station_manager_phone": normalize_text(data.get("station_manager_phone"), 40) or None,
        "station_type": station_type,
        "asset_type": asset_type,
        "is_consolidated": is_consolidated,
        "online_3_status": online_3_status,
        "hos_station_code": normalize_hos_station_code(data.get("hos_station_code")),
        "landline_phone": normalize_text(data.get("landline_phone"), 40) or None,
        "status": status,
        "operating_hours": normalize_operating_hours(data.get("operating_hours")),
    }


def parse_station_backup_json(file_storage):
    if not file_storage or not file_storage.filename:
        raise ValueError("请选择需要导入的站点备份文件。")

    filename = str(file_storage.filename or "").lower()
    if not filename.endswith(".json"):
        raise ValueError("仅支持导入 JSON 格式的站点备份文件。")

    file_bytes = file_storage.read()
    if not file_bytes:
        raise ValueError("站点备份文件内容为空。")
    if len(file_bytes) > 5 * 1024 * 1024:
        raise ValueError("站点备份文件不能超过 5MB。")

    try:
        payload = json.loads(file_bytes.decode("utf-8-sig"))
    except Exception as exc:
        raise ValueError("站点备份文件不是有效的 JSON。") from exc

    stations = payload.get("stations") if isinstance(payload, dict) else payload
    if not isinstance(stations, list):
        raise ValueError("站点备份文件缺少 stations 数据。")
    if not stations:
        raise ValueError("站点备份文件中没有可导入的站点。")

    return stations


def parse_user_backup_json(file_storage):
    if not file_storage or not file_storage.filename:
        raise ValueError("请选择需要导入的用户备份文件。")

    filename = str(file_storage.filename or "").lower()
    if not filename.endswith(".json"):
        raise ValueError("仅支持导入 JSON 格式的用户备份文件。")

    file_bytes = file_storage.read()
    if not file_bytes:
        raise ValueError("用户备份文件内容为空。")
    if len(file_bytes) > 5 * 1024 * 1024:
        raise ValueError("用户备份文件不能超过 5MB。")

    try:
        payload = json.loads(file_bytes.decode("utf-8-sig"))
    except Exception as exc:
        raise ValueError("用户备份文件不是有效的 JSON。") from exc

    users = payload.get("users") if isinstance(payload, dict) else payload
    if not isinstance(users, list):
        raise ValueError("用户备份文件缺少 users 数据。")
    if not users:
        raise ValueError("用户备份文件中没有可导入的用户。")

    return users


def normalize_station_backup_id(value):
    if value in (None, ""):
        return None
    try:
        station_id = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("站点备份文件中存在无效的站点ID。") from exc
    if station_id <= 0:
        raise ValueError("站点备份文件中存在无效的站点ID。")
    return station_id


def normalize_user_backup_id(value):
    if value in (None, ""):
        return None
    try:
        user_id = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("用户备份文件中存在无效的用户ID。") from exc
    if user_id <= 0:
        raise ValueError("用户备份文件中存在无效的用户ID。")
    return user_id


def normalize_user_role(value):
    role = normalize_text(value)
    if role not in ROLE_OPTIONS:
        raise ValueError("用户角色只能选择：root、supervisor、station_manager。")
    return role


def build_management_user_payload(data, is_create=False):
    username = normalize_text(data.get("username"), 80)
    if not username:
        raise ValueError("请填写用户名。")

    password = normalize_text(data.get("password"), 120)
    if is_create and not password:
        raise ValueError("请填写初始密码。")

    role = normalize_user_role(data.get("role"))
    real_name = normalize_text(data.get("real_name"), 80)
    if not real_name:
        raise ValueError("请填写用户姓名。")

    station_id = data.get("station_id")
    if station_id in (None, "", "null"):
        station_id = None
    elif role == "station_manager":
        try:
            station_id = int(station_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("请选择有效的所属站点。") from exc
    else:
        station_id = None

    if role == "station_manager" and not station_id:
        raise ValueError("站点账号必须选择所属站点。")

    return {
        "username": username,
        "password": password,
        "role": role,
        "real_name": real_name,
        "phone": normalize_text(data.get("phone"), 40) or None,
        "station_id": station_id,
    }


def normalize_permission_updates(raw_permissions):
    if raw_permissions in (None, ""):
        return {}
    if not isinstance(raw_permissions, dict):
        raise ValueError("权限配置格式不正确。")

    updates = {}
    for key, value in raw_permissions.items():
        if key not in PERMISSION_KEYS:
            continue
        updates[key] = bool(value)
    return updates


def apply_user_permission_updates(cur, target_user, permissions, actor_user_id):
    if is_root_user(target_user):
        cur.execute("DELETE FROM user_permissions WHERE user_id = %s;", (target_user["id"],))
        return

    permissions = enforce_exclusive_permissions(permissions, target_user.get("role"))
    for permission_key, is_allowed in permissions.items():
        cur.execute(
            """
            INSERT INTO user_permissions (
                user_id,
                permission_key,
                is_allowed,
                updated_by,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id, permission_key)
            DO UPDATE SET
                is_allowed = EXCLUDED.is_allowed,
                updated_by = EXCLUDED.updated_by,
                updated_at = CURRENT_TIMESTAMP;
            """,
            (target_user["id"], permission_key, is_allowed, actor_user_id),
        )


def can_manage_checklist_originals(cur, user):
    return has_permission(cur, user, "manage_checklist_originals")


def can_upload_training_materials(cur, user):
    return has_permission(cur, user, "upload_training_materials")


def can_delete_any_training_material(cur, user):
    return is_root_user(user)


def can_edit_training_material(cur, user, material_row):
    if not user or not material_row:
        return False
    if is_root_user(user):
        return True
    return str(material_row.get("uploaded_by") or "") == str(user.get("id") or "")


def can_delete_training_material(cur, user, material_row):
    return can_edit_training_material(cur, user, material_row) or can_delete_any_training_material(cur, user)


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

        user = get_user_by_id(cur, user_id) if user_id else None
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404
        if not has_permission(cur, user, "view_inspection_plans"):
            return jsonify({"success": False, "error": "当前账号无权查看巡检计划。"}), 403

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

        user = get_user_by_id(cur, user_id) if user_id else None
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404
        if not has_permission(cur, user, "view_inspection_plans"):
            return jsonify({"success": False, "error": "当前账号无权查看巡检计划。"}), 403

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

        if not can_manage_plan(cur, user):
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
    except ValueError as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 400
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


def serialize_standard_row(field_meta, row, register_field_meta=None):
    item = {
        "id": row.get("id"),
        "standard_id": row.get("standard_id"),
        "created_at": row.get("created_at"),
    }
    for field_key, _field_label in field_meta:
        item[field_key] = row.get(field_key)
    item["standard_detail_text"] = build_standard_detail_text(field_meta, row)
    if register_field_meta is not None:
        item["register_display_text"] = build_standard_detail_text(register_field_meta, row)
    return item


INSPECTION_STANDARD_USAGE_MODES = {"internal", "external"}
DEFAULT_INSPECTION_STANDARD_USAGE_MODE = "internal"
INSPECTION_STANDARD_USAGE_MODE_LABELS = {
    "internal": "内部规范库",
    "external": "外部规范库",
}


def normalize_inspection_standard_usage_mode(value):
    mode = str(value or "").strip().lower()
    return mode if mode in INSPECTION_STANDARD_USAGE_MODES else DEFAULT_INSPECTION_STANDARD_USAGE_MODE


def serialize_inspection_standard_usage_mode(mode, row=None):
    normalized_mode = normalize_inspection_standard_usage_mode(mode)
    return {
        "mode": normalized_mode,
        "mode_label": INSPECTION_STANDARD_USAGE_MODE_LABELS.get(normalized_mode, "内部规范库"),
        "updated_by": row.get("updated_by") if row else None,
        "updated_by_username": row.get("updated_by_username") if row else "",
        "updated_by_name": row.get("updated_by_name") if row else "",
        "updated_at": row.get("updated_at") if row else "",
    }


def ensure_inspection_standard_usage_settings_schema(cur):
    acquire_schema_migration_lock(cur)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS inspection_standard_usage_settings (
            singleton BOOLEAN PRIMARY KEY DEFAULT TRUE,
            register_standard_source TEXT NOT NULL DEFAULT 'internal',
            updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT chk_inspection_standard_usage_singleton CHECK (singleton = TRUE),
            CONSTRAINT chk_inspection_standard_usage_source
                CHECK (register_standard_source IN ('internal', 'external'))
        );
        """
    )
    cur.execute(
        """
        INSERT INTO inspection_standard_usage_settings (singleton, register_standard_source)
        VALUES (TRUE, %s)
        ON CONFLICT (singleton) DO NOTHING;
        """,
        (DEFAULT_INSPECTION_STANDARD_USAGE_MODE,),
    )


def get_inspection_standard_usage_mode(cur):
    cur.execute("SELECT to_regclass('public.inspection_standard_usage_settings') AS table_name;")
    row = cur.fetchone()
    if not row or not row.get("table_name"):
        return serialize_inspection_standard_usage_mode(DEFAULT_INSPECTION_STANDARD_USAGE_MODE)

    cur.execute(
        """
        SELECT
            s.register_standard_source,
            s.updated_by,
            COALESCE(u.username, '') AS updated_by_username,
            COALESCE(u.real_name, '') AS updated_by_name,
            TO_CHAR(s.updated_at, 'YYYY-MM-DD HH24:MI') AS updated_at
        FROM inspection_standard_usage_settings s
        LEFT JOIN users u ON u.id = s.updated_by
        WHERE s.singleton = TRUE
        LIMIT 1;
        """
    )
    setting = cur.fetchone()
    if not setting:
        return serialize_inspection_standard_usage_mode(DEFAULT_INSPECTION_STANDARD_USAGE_MODE)
    return serialize_inspection_standard_usage_mode(
        setting.get("register_standard_source"),
        setting,
    )


def save_inspection_standard_usage_mode(cur, mode, user_id):
    normalized_mode = normalize_inspection_standard_usage_mode(mode)
    cur.execute(
        """
        INSERT INTO inspection_standard_usage_settings (
            singleton,
            register_standard_source,
            updated_by,
            updated_at
        )
        VALUES (TRUE, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (singleton)
        DO UPDATE SET
            register_standard_source = EXCLUDED.register_standard_source,
            updated_by = EXCLUDED.updated_by,
            updated_at = CURRENT_TIMESTAMP;
        """,
        (normalized_mode, user_id or None),
    )
    return get_inspection_standard_usage_mode(cur)


def ensure_internal_standard_schema(cur):
    acquire_schema_migration_lock(cur)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS inspection_internal_standards (
            id SERIAL PRIMARY KEY,
            internal_standard_id TEXT UNIQUE NOT NULL,
            path_values JSONB NOT NULL DEFAULT '[]'::jsonb,
            field_values JSONB NOT NULL DEFAULT '{}'::jsonb,
            content TEXT NOT NULL DEFAULT '',
            notes TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cur.execute(
        """
        ALTER TABLE inspection_internal_standards
        ADD COLUMN IF NOT EXISTS field_values JSONB NOT NULL DEFAULT '{}'::jsonb;
        """
    )
    cur.execute(
        """
        ALTER TABLE inspection_internal_standards
        ALTER COLUMN content SET DEFAULT '';
        """
    )
    cur.execute(
        """
        UPDATE inspection_internal_standards
        SET content = ''
        WHERE content IS NULL;
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS inspection_internal_standard_fields (
            id SERIAL PRIMARY KEY,
            field_key TEXT UNIQUE NOT NULL,
            field_label TEXT UNIQUE NOT NULL,
            is_filterable BOOLEAN DEFAULT TRUE,
            is_long_text BOOLEAN DEFAULT FALSE,
            is_register_visible BOOLEAN DEFAULT TRUE,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cur.execute(
        """
        ALTER TABLE inspection_internal_standard_fields
        ADD COLUMN IF NOT EXISTS is_long_text BOOLEAN DEFAULT FALSE;
        """
    )
    cur.execute(
        """
        ALTER TABLE inspection_internal_standard_fields
        ADD COLUMN IF NOT EXISTS is_register_visible BOOLEAN DEFAULT TRUE;
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS inspection_internal_standard_links (
            id SERIAL PRIMARY KEY,
            internal_standard_id INTEGER NOT NULL REFERENCES inspection_internal_standards(id) ON DELETE CASCADE,
            external_standard_id BIGINT NOT NULL UNIQUE,
            external_inspection_table_id INTEGER REFERENCES inspection_tables(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_internal_standards_path_values
        ON inspection_internal_standards USING GIN (path_values);
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_internal_standards_field_values
        ON inspection_internal_standards USING GIN (field_values);
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_internal_standard_links_internal
        ON inspection_internal_standard_links (internal_standard_id);
        """
    )
    ensure_inspection_standard_usage_settings_schema(cur)


def get_internal_standard_fields(cur):
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'inspection_internal_standard_fields'
              AND column_name = 'is_register_visible'
        ) AS has_column;
        """
    )
    has_register_visible_column = bool(cur.fetchone().get("has_column"))
    register_visible_select = "is_register_visible" if has_register_visible_column else "TRUE AS is_register_visible"
    cur.execute(
        f"""
        SELECT
            id,
            field_key,
            field_label,
            is_filterable,
            is_long_text,
            {register_visible_select},
            sort_order
        FROM inspection_internal_standard_fields
        ORDER BY sort_order ASC, id ASC;
        """
    )
    return cur.fetchall()


def normalize_internal_standard_field_rows(fields, allow_empty=True):
    return normalize_checklist_field_rows(
        fields,
        table_code="internal_standard",
        allow_empty=allow_empty,
    )


def upsert_internal_standard_fields(cur, fields):
    incoming_keys = [field["field_key"] for field in fields]
    current_rows = get_internal_standard_fields(cur)
    current_keys = {row["field_key"] for row in current_rows}
    removed_keys = [field_key for field_key in current_keys if field_key not in incoming_keys]

    if incoming_keys:
        cur.execute(
            """
            DELETE FROM inspection_internal_standard_fields
            WHERE field_key <> ALL(%s::text[]);
            """,
            (incoming_keys,),
        )
    else:
        cur.execute("DELETE FROM inspection_internal_standard_fields;")

    for field in fields:
        cur.execute(
            """
            INSERT INTO inspection_internal_standard_fields (
                field_key,
                field_label,
                is_filterable,
                is_long_text,
                is_register_visible,
                sort_order
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (field_key)
            DO UPDATE SET
                field_label = EXCLUDED.field_label,
                is_filterable = EXCLUDED.is_filterable,
                is_long_text = EXCLUDED.is_long_text,
                is_register_visible = EXCLUDED.is_register_visible,
                sort_order = EXCLUDED.sort_order;
            """,
            (
                field["field_key"],
                field["field_label"],
                field["is_filterable"],
                field.get("is_long_text", False),
                field["is_register_visible"],
                field["sort_order"],
            ),
        )

    for field_key in removed_keys:
        cur.execute(
            """
            UPDATE inspection_internal_standards
            SET field_values = field_values - %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE field_values ? %s;
            """,
            (field_key, field_key),
        )


def parse_json_field(value, fallback):
    if value in (None, ""):
        return fallback
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed
        except Exception:
            return fallback
    return fallback


def normalize_internal_field_values(raw_values, fields):
    if not fields:
        raise ValueError("请先配置内部规范字段。")
    if not isinstance(raw_values, dict):
        raise ValueError("内部规范字段内容格式不正确。")
    normalized = {}
    for field in fields:
        field_key = field["field_key"]
        normalized[field_key] = normalize_text(raw_values.get(field_key), 1000)
    first_field = fields[0]
    if not normalized.get(first_field["field_key"]):
        raise ValueError(f"请填写首个字段【{first_field['field_label']}】，系统需要用它生成内部规范ID。")
    return normalized


def build_internal_path_values_from_field_values(fields, field_values):
    return [
        str(field_values.get(field["field_key"]) or "").strip()
        for field in fields
        if str(field_values.get(field["field_key"]) or "").strip()
    ]


def build_internal_standard_summary(fields, field_values):
    parts = []
    for field in fields:
        value = str(field_values.get(field["field_key"]) or "").strip()
        if value:
            parts.append(f"{field['field_label']}：{value}")
    return "\n".join(parts)


def normalize_external_link_rows(value):
    if not isinstance(value, list):
        return []
    links = []
    seen = set()
    for item in value:
        raw_standard_id = item.get("external_standard_id") if isinstance(item, dict) else item
        raw_table_id = item.get("external_inspection_table_id") if isinstance(item, dict) else None
        standard_id = normalize_import_standard_id(raw_standard_id)
        if standard_id in seen:
            continue
        seen.add(standard_id)
        table_id = None
        if raw_table_id not in (None, ""):
            try:
                table_id = int(raw_table_id)
            except (TypeError, ValueError):
                table_id = None
        links.append(
            {
                "external_standard_id": standard_id,
                "external_inspection_table_id": table_id,
            }
        )
    return links


def get_pinyin_initial_prefix(value):
    text = str(value or "").strip()
    if not text:
        return "NB"
    try:
        from pypinyin import Style, lazy_pinyin

        prefix = "".join(lazy_pinyin(text, style=Style.FIRST_LETTER)).upper()
    except Exception:
        basic_initials = {
            "配": "P",
            "电": "D",
            "间": "J",
            "加": "J",
            "油": "Y",
            "站": "Z",
            "安": "A",
            "全": "Q",
            "服": "F",
            "务": "W",
            "卫": "W",
            "生": "S",
            "财": "C",
            "质": "Z",
            "量": "L",
        }
        prefix = "".join(
            basic_initials.get(char, char[0].upper() if char.isascii() and char.isalnum() else "")
            for char in text
        )
    prefix = re.sub(r"[^A-Z0-9]+", "", prefix)
    return prefix or "NB"


def generate_internal_standard_id(cur, first_field_value):
    prefix = get_pinyin_initial_prefix(first_field_value)
    cur.execute(
        """
        SELECT internal_standard_id
        FROM inspection_internal_standards
        WHERE internal_standard_id ~ %s;
        """,
        (f"^{prefix}[0-9]+$",),
    )
    max_number = 0
    for row in cur.fetchall():
        match = re.match(rf"^{re.escape(prefix)}(\d+)$", row["internal_standard_id"] or "")
        if match:
            max_number = max(max_number, int(match.group(1)))
    return f"{prefix}{max_number + 1}"


def fetch_external_standard_map(cur, external_standard_ids=None):
    cur.execute("SELECT to_regclass('public.inspection_tables') AS table_name;")
    row = cur.fetchone()
    if not row or not row.get("table_name"):
        return {}
    params = []
    filter_ids = {int(item) for item in external_standard_ids or [] if str(item).strip()}
    result = {}
    cur.execute(
        """
        SELECT id, table_code, table_name
        FROM inspection_tables
        WHERE is_active = TRUE
        ORDER BY id ASC;
        """
    )
    for table in cur.fetchall():
        physical_table_name = get_physical_table_name_by_code(table["table_code"])
        if not physical_table_name or not checklist_physical_table_exists(cur, physical_table_name):
            continue
        fields = [dict(field) for field in get_management_checklist_fields(cur, table["id"])]
        field_meta = [(field["field_key"], field["field_label"]) for field in fields]
        register_field_meta = build_register_display_field_meta(fields)
        where_sql = sql.SQL("")
        params = []
        if filter_ids:
            where_sql = sql.SQL(" WHERE standard_id = ANY(%s)")
            params = [list(filter_ids)]
        cur.execute(
            sql.SQL("SELECT * FROM {}{} ORDER BY standard_id ASC;").format(
                sql.Identifier(physical_table_name),
                where_sql,
            ),
            params,
        )
        for row in cur.fetchall():
            item = serialize_standard_row(field_meta, row, register_field_meta)
            standard_id = int(item["standard_id"])
            result[standard_id] = {
                **item,
                "external_standard_id": standard_id,
                "inspection_table_id": table["id"],
                "inspection_table_name": table["table_name"],
                "inspection_table_code": table["table_code"],
            }
    return result


def fetch_internal_links_by_external_ids(cur, external_standard_ids):
    ids = [int(item) for item in external_standard_ids if str(item).strip()]
    if not ids:
        return {}
    cur.execute("SELECT to_regclass('public.inspection_internal_standard_links') AS table_name;")
    row = cur.fetchone()
    if not row or not row.get("table_name"):
        return {}
    cur.execute(
        """
        SELECT
            l.external_standard_id,
            s.id,
            s.internal_standard_id,
            s.path_values,
            s.field_values,
            s.content
        FROM inspection_internal_standard_links l
        JOIN inspection_internal_standards s ON s.id = l.internal_standard_id
        WHERE l.external_standard_id = ANY(%s);
        """,
        (ids,),
    )
    return {int(row["external_standard_id"]): dict(row) for row in cur.fetchall()}


def serialize_internal_standard(row, linked_externals=None, fields=None):
    fields = fields or []
    path_values = parse_json_field(row.get("path_values"), [])
    field_values = parse_json_field(row.get("field_values"), {})
    if not isinstance(path_values, list):
        path_values = []
    if not isinstance(field_values, dict):
        field_values = {}
    if fields and not field_values and path_values:
        for index, field in enumerate(fields):
            if index < len(path_values):
                field_values[field["field_key"]] = path_values[index]
    content = row.get("content") or ""
    if fields and not content:
        content = build_internal_standard_summary(fields, field_values)
    register_display_text = build_internal_standard_summary(
        [field for field in fields if normalize_boolean_flag(field.get("is_register_visible"), True)],
        field_values,
    ) if fields else ""
    return {
        "id": row["id"],
        "internal_standard_id": str(row["internal_standard_id"] or "").upper(),
        "path_values": path_values,
        "field_values": field_values,
        "content": content,
        "register_display_text": register_display_text,
        "notes": row.get("notes") or "",
        "is_active": bool(row.get("is_active")),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "linked_externals": linked_externals or [],
    }


def fetch_internal_standard_links(cur, internal_ids):
    ids = [int(item) for item in internal_ids if item]
    if not ids:
        return {}
    cur.execute(
        """
        SELECT
            l.internal_standard_id,
            l.external_standard_id,
            l.external_inspection_table_id
        FROM inspection_internal_standard_links l
        WHERE l.internal_standard_id = ANY(%s)
        ORDER BY l.external_standard_id ASC;
        """,
        (ids,),
    )
    link_rows = cur.fetchall()
    external_map = fetch_external_standard_map(cur, [row["external_standard_id"] for row in link_rows])
    result = {item: [] for item in ids}
    for row in link_rows:
        external = external_map.get(int(row["external_standard_id"]))
        result.setdefault(row["internal_standard_id"], []).append(
            {
                "external_standard_id": row["external_standard_id"],
                "external_inspection_table_id": row["external_inspection_table_id"],
                "inspection_table_name": external.get("inspection_table_name") if external else "",
                "standard_detail_text": external.get("standard_detail_text") if external else "",
            }
        )
    return result


def replace_internal_standard_links(cur, internal_id, links):
    external_ids = [item["external_standard_id"] for item in links]
    if external_ids:
        cur.execute(
            """
            SELECT
                l.external_standard_id,
                s.internal_standard_id
            FROM inspection_internal_standard_links l
            JOIN inspection_internal_standards s ON s.id = l.internal_standard_id
            WHERE l.external_standard_id = ANY(%s)
              AND l.internal_standard_id <> %s
            LIMIT 1;
            """,
            (external_ids, internal_id),
        )
        conflict = cur.fetchone()
        if conflict:
            raise ValueError(
                f"外部规范ID【{conflict['external_standard_id']}】已挂载到内部规范【{conflict['internal_standard_id']}】，不能重复挂载。"
            )

    external_map = fetch_external_standard_map(cur, external_ids)
    missing = [item for item in external_ids if int(item) not in external_map]
    if missing:
        raise ValueError(f"外部规范ID【{missing[0]}】不存在。")

    cur.execute("DELETE FROM inspection_internal_standard_links WHERE internal_standard_id = %s;", (internal_id,))
    for item in links:
        external = external_map[int(item["external_standard_id"])]
        table_id = item.get("external_inspection_table_id") or external["inspection_table_id"]
        cur.execute(
            """
            INSERT INTO inspection_internal_standard_links (
                internal_standard_id,
                external_standard_id,
                external_inspection_table_id
            )
            VALUES (%s, %s, %s);
            """,
            (internal_id, item["external_standard_id"], table_id),
        )


def fetch_internal_standard_by_code(cur, internal_standard_id):
    text = str(internal_standard_id or "").strip().upper()
    if not text:
        return None, [], []
    cur.execute("SELECT to_regclass('public.inspection_internal_standards') AS table_name;")
    row = cur.fetchone()
    if not row or not row.get("table_name"):
        return None, [], []
    fields = [dict(field) for field in get_internal_standard_fields(cur)]
    cur.execute(
        """
        SELECT
            id,
            internal_standard_id,
            path_values,
            field_values,
            content,
            notes,
            is_active,
            TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI') AS created_at,
            TO_CHAR(updated_at, 'YYYY-MM-DD HH24:MI') AS updated_at
        FROM inspection_internal_standards
        WHERE UPPER(internal_standard_id) = %s
          AND is_active = TRUE
        LIMIT 1;
        """,
        (text,),
    )
    row = cur.fetchone()
    if not row:
        return None, fields, []
    link_map = fetch_internal_standard_links(cur, [row["id"]])
    return serialize_internal_standard(row, link_map.get(row["id"], []), fields), fields, link_map.get(row["id"], [])


def prepare_issue_registration_targets(
    cur,
    station_id,
    inspector_id,
    external_standards,
    batch_id,
    today,
):
    targets = []
    period = get_inspection_completion_config(cur)["record_uniqueness_period"]
    for external in external_standards:
        inspection_table_id = str(external.get("inspection_table_id") or "").strip()
        standard_id = str(external.get("external_standard_id") or external.get("standard_id") or "").strip()
        if not inspection_table_id or not standard_id:
            raise ValueError("内部规范挂载的外部规范数据不完整。")

        inspection_table = get_inspection_table_record(cur, inspection_table_id)
        if not inspection_table:
            raise ValueError(f"外部规范ID【{standard_id}】对应的检查表不存在。")
        if not inspection_table["is_active"]:
            raise ValueError(f"外部规范ID【{standard_id}】对应的检查表未启用。")

        lock_inspection_period_scope(cur, station_id, inspection_table_id, today, period)
        existing_inspection = find_period_inspection(
            cur,
            station_id,
            inspection_table_id,
            today,
            period,
        )
        if existing_inspection and existing_inspection.get("inspector_completion_status") == INSPECTION_COMPLETION_DONE:
            raise ValueError(
                f"站点{inspection_period_scope_text(period)}【{inspection_table['table_name']}】已确认完成，不能继续登记。"
            )

        targets.append(
            {
                "inspection_table_id": int(inspection_table_id),
                "inspection_table_name": inspection_table["table_name"],
                "standard_id": int(standard_id),
                "standard_detail_text": external.get("standard_detail_text") or "",
                "inspection_id": existing_inspection["id"] if existing_inspection else None,
            }
        )
    return targets


def resolve_issue_standard_edit_target(
    cur,
    usage_mode,
    standard_id=None,
    internal_standard_id=None,
    preferred_external_standard_id=None,
):
    mode = normalize_inspection_standard_usage_mode(usage_mode)
    if mode == "internal":
        internal_code = str(internal_standard_id or "").strip().upper()
        if not internal_code:
            raise ValueError("请选择内部规范ID。")
        internal_standard, _internal_fields, linked_externals = fetch_internal_standard_by_code(
            cur,
            internal_code,
        )
        if not internal_standard:
            raise ValueError("所选内部规范不存在或未启用。")
        if not linked_externals:
            raise ValueError("所选内部规范尚未挂载外部规范，不能用于巡检问题。")

        sorted_links = sorted(
            linked_externals,
            key=lambda item: int(item.get("external_standard_id") or 0),
        )
        preferred_external_id = str(preferred_external_standard_id or "").strip()
        first_link = next(
            (
                link
                for link in sorted_links
                if str(link.get("external_standard_id") or "").strip() == preferred_external_id
            ),
            sorted_links[0],
        )
        external_map = fetch_external_standard_map(cur, [first_link["external_standard_id"]])
        external = external_map.get(int(first_link["external_standard_id"]))
        if not external:
            raise ValueError(f"内部规范挂载的外部规范ID【{first_link['external_standard_id']}】不存在。")

        return {
            "inspection_table_id": int(external["inspection_table_id"]),
            "standard_id": int(external["external_standard_id"]),
            "standard_detail_text": external.get("standard_detail_text") or "",
            "internal_standard_id": internal_standard["internal_standard_id"],
            "internal_standard_detail_text": internal_standard.get("content") or "",
        }

    external_id = normalize_import_standard_id(standard_id)
    external_map = fetch_external_standard_map(cur, [external_id])
    external = external_map.get(external_id)
    if not external:
        raise ValueError("所选外部规范不存在或对应检查表未启用。")

    linked_internal = fetch_internal_links_by_external_ids(cur, [external_id]).get(external_id)
    return {
        "inspection_table_id": int(external["inspection_table_id"]),
        "standard_id": external_id,
        "standard_detail_text": external.get("standard_detail_text") or "",
        "internal_standard_id": linked_internal.get("internal_standard_id") if linked_internal else None,
        "internal_standard_detail_text": linked_internal.get("content") if linked_internal else None,
    }


def get_or_create_issue_edit_inspection(cur, issue, target_inspection_table_id, target_inspector_id=None):
    current_table_id = int(issue["inspection_table_id"])
    target_table_id = int(target_inspection_table_id)
    if current_table_id == target_table_id:
        return int(issue["inspection_id"])

    next_inspector_id = int(target_inspector_id or issue["inspector_id"])
    period = get_inspection_completion_config(cur)["record_uniqueness_period"]
    lock_inspection_period_scope(
        cur,
        issue["station_id"],
        target_table_id,
        issue["inspection_date"],
        period,
    )
    existing_inspection = find_period_inspection(
        cur,
        issue["station_id"],
        target_table_id,
        issue["inspection_date"],
        period,
    )
    if existing_inspection:
        if existing_inspection.get("inspector_completion_status") == INSPECTION_COMPLETION_DONE:
            raise ValueError(f"目标检查表{inspection_period_scope_text(period)}已确认完成，不能把问题改挂到该检查表。")
        return int(existing_inspection["id"])

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
        (
            issue["station_id"],
            next_inspector_id,
            target_table_id,
            issue["inspection_date"],
            issue.get("batch_id"),
        ),
    )
    return int(cur.fetchone()["id"])


def sync_inspection_primary_inspector(cur, inspection_id):
    if not inspection_id:
        return
    cur.execute(
        """
        SELECT inspector_id
        FROM issues
        WHERE inspection_id = %s
          AND inspector_id IS NOT NULL
        ORDER BY created_at ASC, id ASC
        LIMIT 1;
        """,
        (inspection_id,),
    )
    row = cur.fetchone()
    if not row or not row.get("inspector_id"):
        return
    cur.execute(
        """
        UPDATE inspections
        SET inspector_id = %s
        WHERE id = %s
          AND inspector_id <> %s;
        """,
        (row["inspector_id"], inspection_id, row["inspector_id"]),
    )


def cleanup_empty_inspection_after_issue_move(cur, inspection_id):
    if not inspection_id:
        return
    cur.execute(
        """
        SELECT id, batch_id, sign_status, inspector_completion_status
        FROM inspections
        WHERE id = %s
        LIMIT 1;
        """,
        (inspection_id,),
    )
    inspection = cur.fetchone()
    if (
        not inspection
        or inspection.get("sign_status") == "已签名确认"
        or inspection.get("inspector_completion_status") == INSPECTION_COMPLETION_DONE
    ):
        return

    cur.execute("SELECT COUNT(*) AS issue_count FROM issues WHERE inspection_id = %s;", (inspection_id,))
    if int(cur.fetchone()["issue_count"] or 0) > 0:
        return

    cur.execute(
        """
        UPDATE inspection_plan_station_items
        SET completion_status = 'pending',
            completed_inspection_id = NULL,
            completed_at = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE completed_inspection_id = %s;
        """,
        (inspection_id,),
    )
    cur.execute("DELETE FROM inspections WHERE id = %s;", (inspection_id,))
    if inspection.get("batch_id"):
        cur.execute(
            """
            DELETE FROM inspection_batches b
            WHERE b.id = %s
              AND NOT EXISTS (
                SELECT 1
                FROM inspections ins
                WHERE ins.batch_id = b.id
              );
            """,
            (inspection["batch_id"],),
        )


def normalize_internal_standards_backup_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("备份文件格式不正确：根内容必须是对象。")
    if payload.get("backup_type") != "ywddzx_internal_standards":
        raise ValueError("备份文件类型不匹配，请选择巡检规范库备份文件。")
    standards = payload.get("standards")
    if not isinstance(standards, list):
        raise ValueError("备份文件缺少 standards 数组。")

    raw_fields = payload.get("fields")
    if not isinstance(raw_fields, list):
        max_path_length = 0
        has_content = False
        for item in standards:
            if not isinstance(item, dict):
                continue
            path_values = item.get("path_values") or []
            if isinstance(path_values, list):
                max_path_length = max(max_path_length, len(path_values))
            if str(item.get("content") or "").strip():
                has_content = True
        inferred_fields = [
            {"field_label": f"层级{i}", "is_filterable": True}
            for i in range(1, max_path_length + 1)
        ]
        if has_content:
            inferred_fields.append({"field_label": "规范内容", "is_filterable": False})
        raw_fields = inferred_fields

    fields = normalize_internal_standard_field_rows(raw_fields or [], allow_empty=True)
    normalized = []
    seen_internal_ids = set()
    seen_external_ids = set()
    for index, item in enumerate(standards, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"第 {index} 条内部规范数据格式不正确。")
        internal_standard_id = str(item.get("internal_standard_id") or "").strip().upper()
        if not internal_standard_id:
            raise ValueError(f"第 {index} 条内部规范缺少内部规范ID。")
        if not re.match(r"^[A-Z0-9]+[0-9]$", internal_standard_id):
            raise ValueError(f"内部规范ID【{internal_standard_id}】格式不正确。")
        if internal_standard_id in seen_internal_ids:
            raise ValueError(f"备份文件内内部规范ID【{internal_standard_id}】重复。")
        seen_internal_ids.add(internal_standard_id)

        raw_field_values = item.get("field_values")
        if not isinstance(raw_field_values, dict):
            raw_field_values = {}
            legacy_path_values = item.get("path_values") or []
            if isinstance(legacy_path_values, list):
                for field_index, field in enumerate(fields):
                    if field_index < len(legacy_path_values):
                        raw_field_values[field["field_key"]] = legacy_path_values[field_index]
            content_text = normalize_text(item.get("content"), 1000)
            if content_text and fields:
                raw_field_values[fields[-1]["field_key"]] = raw_field_values.get(fields[-1]["field_key"]) or content_text
        field_values = normalize_internal_field_values(raw_field_values, fields) if fields else {}
        path_values = build_internal_path_values_from_field_values(fields, field_values)
        content = build_internal_standard_summary(fields, field_values)
        links = normalize_external_link_rows(
            item.get("external_links") or item.get("linked_externals") or []
        )
        for link in links:
            external_standard_id = int(link["external_standard_id"])
            if external_standard_id in seen_external_ids:
                raise ValueError(
                    f"备份文件内外部规范ID【{external_standard_id}】被多条内部规范重复挂载。"
                )
            seen_external_ids.add(external_standard_id)

        normalized.append(
            {
                "internal_standard_id": internal_standard_id,
                "path_values": path_values,
                "field_values": field_values,
                "content": content,
                "notes": "",
                "is_active": bool(item.get("is_active", True)),
                "external_links": links,
            }
        )
    return {
        "fields": fields,
        "standards": normalized,
    }


def parse_internal_standards_backup_file(file_storage):
    if not file_storage or not file_storage.filename:
        raise ValueError("请选择需要导入的巡检规范库备份文件。")
    if not file_storage.filename.lower().endswith(".json"):
        raise ValueError("巡检规范库备份文件只能导入 JSON 格式。")
    file_bytes = file_storage.read()
    if not file_bytes:
        raise ValueError("备份文件内容为空。")
    try:
        payload = json.loads(file_bytes.decode("utf-8-sig"))
    except Exception:
        raise ValueError("备份文件不是有效的 JSON。")
    return normalize_internal_standards_backup_payload(payload)


def build_external_inspection_standard_ai_catalog(cur):
    external_map = fetch_external_standard_map(cur)
    internal_links = fetch_internal_links_by_external_ids(cur, external_map.keys())
    ai_catalog = []
    full_standards = []

    for standard in external_map.values():
        standard_id = str(standard.get("external_standard_id") or standard.get("standard_id") or "").strip()
        detail_text = str(standard.get("standard_detail_text") or "").strip()
        if not standard_id or not detail_text:
            continue
        linked_internal = internal_links.get(int(standard["external_standard_id"]))
        enriched_standard = {
            **standard,
            "standard_id": standard_id,
            "external_standard_id": standard["external_standard_id"],
            "inspection_table_id": standard.get("inspection_table_id") or "",
            "inspection_table_name": standard.get("inspection_table_name") or "",
            "standard_detail_text": detail_text,
            "linked_internal": linked_internal,
            "linked_internal_standard_id": linked_internal.get("internal_standard_id") if linked_internal else "",
        }
        full_standards.append(enriched_standard)
        ai_catalog.append(
            {
                "standard_id": standard_id,
                "inspection_table_name": enriched_standard["inspection_table_name"],
                "detail_text": detail_text,
            }
        )

    return ai_catalog, full_standards


def build_internal_inspection_standard_ai_catalog(cur):
    cur.execute(
        """
        SELECT
            id,
            internal_standard_id,
            path_values,
            field_values,
            content,
            notes,
            is_active,
            TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI') AS created_at,
            TO_CHAR(updated_at, 'YYYY-MM-DD HH24:MI') AS updated_at
        FROM inspection_internal_standards
        WHERE is_active = TRUE
        ORDER BY internal_standard_id ASC;
        """
    )
    internal_rows = cur.fetchall()
    fields = [dict(field) for field in get_internal_standard_fields(cur)]
    link_map = fetch_internal_standard_links(cur, [row["id"] for row in internal_rows])
    ai_catalog = []
    full_standards = []

    for row in internal_rows:
        standard = serialize_internal_standard(row, link_map.get(row["id"], []), fields)
        if not standard.get("linked_externals"):
            continue

        detail_text = str(standard.get("content") or "").strip()
        if not standard.get("internal_standard_id") or not detail_text:
            continue

        linked_table_names = []
        for link in standard.get("linked_externals") or []:
            table_name = str(link.get("inspection_table_name") or "").strip()
            if table_name and table_name not in linked_table_names:
                linked_table_names.append(table_name)
        table_summary = "、".join(linked_table_names) or "未命名检查表"

        enriched_standard = {
            **standard,
            "standard_id": standard["internal_standard_id"],
            "internal_standard_id": standard["internal_standard_id"],
            "inspection_table_id": "",
            "inspection_table_name": table_summary,
            "standard_detail_text": detail_text,
        }
        full_standards.append(enriched_standard)
        ai_catalog.append(
            {
                "standard_id": str(standard["internal_standard_id"]),
                "inspection_table_name": table_summary,
                "detail_text": detail_text,
            }
        )

    return ai_catalog, full_standards


def build_inspection_standard_ai_catalog(cur, usage_mode=None):
    mode = normalize_inspection_standard_usage_mode(usage_mode)
    if mode == "external":
        return build_external_inspection_standard_ai_catalog(cur)
    return build_internal_inspection_standard_ai_catalog(cur)


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
        ensure_user_security_schema(cur)
        conn.commit()
        cur.execute(
            """
            SELECT
                u.id,
                u.username,
                u.password,
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

        token = create_auth_token(user)
        return jsonify(
            {
                "success": True,
                "token": token,
                "expires_in": get_auth_token_ttl_seconds(user),
                "user": build_auth_user_payload(cur, user),
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


@app.route("/api/auth/me", methods=["GET"])
def get_authenticated_user():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        user = fetch_auth_user_by_id(cur, g.current_user["id"])
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        return jsonify(
            {
                "success": True,
                "token": extract_bearer_token(),
                "expires_in": get_auth_payload_expires_in(getattr(g, "auth_payload", {})),
                "user": build_auth_user_payload(cur, user),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/users/change-password", methods=["POST"])
def change_own_password():
    data = request.get_json(silent=True) or {}

    try:
        user_id = int(get_authenticated_request_user_id(data.get("user_id")) or 0)
    except (TypeError, ValueError):
        user_id = 0

    current_password = normalize_text(data.get("current_password"), 120)
    new_password = normalize_text(data.get("new_password"), 120)
    confirm_password = normalize_text(data.get("confirm_password"), 120)

    if user_id <= 0:
        return jsonify({"success": False, "error": "缺少用户信息。"}), 400
    if not current_password:
        return jsonify({"success": False, "error": "请填写当前密码。"}), 400

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_user_security_schema(cur)
        conn.commit()

        cur.execute(
            """
            SELECT id, username, password
            FROM users
            WHERE id = %s
            LIMIT 1;
            """,
            (user_id,),
        )
        user = cur.fetchone()

        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404
        if user["password"] != current_password:
            return jsonify({"success": False, "error": "当前密码不正确。"}), 400

        validated_password = validate_new_login_password(
            user["username"], new_password, confirm_password
        )
        if validated_password == current_password:
            return jsonify({"success": False, "error": "新密码不能与当前密码相同。"}), 400

        cur.execute(
            """
            UPDATE users
            SET password = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
            """,
            (validated_password, user_id),
        )
        conn.commit()

        updated_user = fetch_auth_user_by_id(cur, user_id)
        token = create_auth_token(updated_user)
        return jsonify(
            {
                "success": True,
                "token": token,
                "expires_in": get_auth_token_ttl_seconds(updated_user),
                "must_change_password": False,
                "user": build_auth_user_payload(cur, updated_user),
            }
        )
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


# === 检查表级签名确认 API ===
@app.route("/api/inspections/sign-pending-count", methods=["GET"])
def get_inspection_sign_pending_count():
    user = get_current_request_user()
    conn = None
    cur = None
    if not is_station_manager(user) or not user.get("station_id"):
        return jsonify({"success": True, "pending_count": 0})

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_issue_inspector_schema(cur)
        ensure_inspection_completion_schema(cur)
        if not can_sign_inspection_records(cur, user):
            conn.commit()
            return jsonify({"success": True, "pending_count": 0})
        cur.execute(
            """
            SELECT COUNT(*) AS pending_count
            FROM inspections ins
            WHERE ins.station_id = %s
              AND COALESCE(ins.sign_status, '待签名确认') <> '已签名确认'
              AND NOT EXISTS (
                  SELECT 1
                  FROM issues i
                  WHERE i.inspection_id = ins.id
                    AND COALESCE(i.audit_status, 'pending') = 'pending'
              );
            """,
            (user["station_id"],),
        )
        pending_count = int(cur.fetchone()["pending_count"] or 0)
        conn.commit()
        return jsonify({"success": True, "pending_count": pending_count})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/inspections/<int:inspection_id>/sign", methods=["POST"])
def sign_inspection_record(inspection_id):
    user_id = get_authenticated_request_user_id(request.form.get("user_id"))
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
        ensure_issue_inspector_schema(cur)
        ensure_inspection_completion_schema(cur)
        sync_signed_inspections_completion(cur)
        auto_complete_overdue_inspections(cur)
        conn.commit()

        user = get_user_by_id(cur, user_id)

        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        if not is_station_manager(user):
            return jsonify({"success": False, "error": "只有站点账号可以完成本表站经理签字确认。"}), 403
        if not can_sign_inspection_records(cur, user):
            return jsonify({"success": False, "error": "当前账号无权完成本表站经理签字确认。"}), 403

        cur.execute(
            """
            SELECT
                ins.id,
                ins.station_id,
                ins.inspection_date,
                ins.sign_status,
                ins.inspection_table_id,
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

        if str(user.get("station_id") or "") != str(inspection.get("station_id") or ""):
            return jsonify({"success": False, "error": "只能签署本账号所属站点的巡检记录。"}), 403

        cur.execute(
            """
            SELECT COUNT(*) AS pending_audit_count
            FROM issues
            WHERE inspection_id = %s
              AND COALESCE(audit_status, 'pending') = 'pending';
            """,
            (inspection_id,),
        )
        pending_audit_count = int(cur.fetchone()["pending_audit_count"] or 0)
        if pending_audit_count > 0:
            return jsonify({"success": False, "error": f"该检查表仍有 {pending_audit_count} 条问题待审核，暂不能签字确认。"}), 400

        signature_path = save_signature_file(signature_file)
        signed_at = beijing_now()

        cur.execute(
            """
            UPDATE inspections
            SET sign_status = '已签名确认',
                station_manager_signed_name = %s,
                station_manager_signature_path = %s,
                station_manager_signed_at = %s,
                inspector_completion_status = %s,
                inspector_completed_by = CASE
                    WHEN inspector_completion_status = %s THEN inspector_completed_by
                    ELSE %s
                END,
                inspector_completed_at = CASE
                    WHEN inspector_completion_status = %s THEN inspector_completed_at
                    ELSE %s
                END,
                inspector_completion_source = CASE
                    WHEN inspector_completion_status = %s THEN inspector_completion_source
                    ELSE 'signature'
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
            """,
            (
                signed_name,
                signature_path,
                signed_at,
                INSPECTION_COMPLETION_DONE,
                INSPECTION_COMPLETION_DONE,
                user_id,
                INSPECTION_COMPLETION_DONE,
                signed_at,
                INSPECTION_COMPLETION_DONE,
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


@app.route("/api/inspections/<int:inspection_id>/signature/reset", methods=["POST"])
def reset_inspection_signature(inspection_id):
    data = request.get_json(silent=True) or {}
    user_id = get_authenticated_request_user_id(data.get("user_id"))
    if not user_id:
        return jsonify({"success": False, "error": "缺少用户信息。"}), 400

    conn = None
    cur = None
    signature_path = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_inspection_completion_schema(cur)

        user = get_user_by_id(cur, user_id)
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404
        if not can_reset_inspection_signature(cur, user):
            return jsonify({"success": False, "error": "当前账号无权重置站经理签名。"}), 403

        cur.execute(
            """
            SELECT
                id,
                station_id,
                sign_status,
                station_manager_signed_name,
                station_manager_signature_path,
                station_manager_signed_at,
                inspector_completion_status,
                inspector_completion_source
            FROM inspections
            WHERE id = %s
            LIMIT 1;
            """,
            (inspection_id,),
        )
        inspection = cur.fetchone()
        if not inspection:
            return jsonify({"success": False, "error": "巡检记录不存在。"}), 404

        if inspection.get("sign_status") != "已签名确认" and not (
            inspection.get("station_manager_signature_path")
            or inspection.get("station_manager_signed_at")
            or inspection.get("station_manager_signed_name")
        ):
            return jsonify({"success": False, "error": "该巡检记录尚未完成站经理签名，无需重置。"}), 400

        cur.execute(
            """
            SELECT COUNT(*) AS rectified_issue_count
            FROM issues
            WHERE inspection_id = %s
              AND (
                  NULLIF(TRIM(COALESCE(rectification_result, '')), '') IS NOT NULL
                  OR NULLIF(TRIM(COALESCE(rectification_note, '')), '') IS NOT NULL
                  OR NULLIF(TRIM(COALESCE(rectification_photo_path, '')), '') IS NOT NULL
              );
            """,
            (inspection_id,),
        )
        rectified_issue_count = int(cur.fetchone()["rectified_issue_count"] or 0)
        if rectified_issue_count > 0:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"该巡检记录已有 {rectified_issue_count} 条问题提交了站经理整改，不能重置站经理签名。",
                    }
                ),
                400,
            )

        signature_path = inspection.get("station_manager_signature_path")
        cur.execute(
            """
            UPDATE inspections
            SET sign_status = '待签名确认',
                station_manager_signed_name = NULL,
                station_manager_signature_path = NULL,
                station_manager_signed_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
            """,
            (inspection_id,),
        )
        cur.execute(
            """
            UPDATE issues
            SET audit_status = 'pending',
                audited_by = NULL,
                audited_at = NULL
            WHERE inspection_id = %s;
            """,
            (inspection_id,),
        )
        reset_issue_count = cur.rowcount

        conn.commit()
        if signature_path:
            remove_storage_file(signature_path)
        return jsonify(
            {
                "success": True,
                "message": "站经理签名已重置，关联问题已退回待审核；重新审核完成后可再次签字。",
                "reset_issue_count": reset_issue_count,
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
        ensure_station_management_columns(cur)
        conn.commit()
        cur.execute(
            """
            SELECT
                s.id,
                s.station_name,
                s.region,
                s.address,
                s.longitude,
                s.latitude,
                s.station_manager_name,
                s.station_manager_phone,
                s.station_type,
                CASE
                    WHEN s.asset_type LIKE '%股权%' OR s.asset_type LIKE '%控股%' OR s.asset_type LIKE '%参股%' THEN '股权'
                    ELSE '全资'
                END AS asset_type,
                s.is_consolidated,
                s.online_3_status,
                s.hos_station_code,
                s.landline_phone,
                s.status,
                s.operating_hours,
                COALESCE(station_accounts.station_usernames, '') AS station_usernames
            FROM stations s
            LEFT JOIN (
                SELECT
                    station_id,
                    STRING_AGG(username, ' ' ORDER BY username) AS station_usernames
                FROM users
                WHERE role = 'station_manager'
                  AND station_id IS NOT NULL
                GROUP BY station_id
            ) station_accounts ON station_accounts.station_id = s.id
            ORDER BY s.id;
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


@app.route("/api/management/users", methods=["GET"])
def get_management_users():
    user_id = str(request.args.get("user_id", "")).strip()
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_user_security_schema(cur)
        conn.commit()
        require_management_user(cur, user_id, "manage_users")

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
                s.region AS station_region,
                TO_CHAR(u.created_at, 'YYYY-MM-DD HH24:MI') AS created_at,
                TO_CHAR(u.updated_at, 'YYYY-MM-DD HH24:MI') AS updated_at
            FROM users u
            LEFT JOIN stations s ON u.station_id = s.id
            ORDER BY
                CASE u.role
                    WHEN 'root' THEN 1
                    WHEN 'supervisor' THEN 2
                    ELSE 3
                END,
                u.id ASC;
            """
        )
        rows = cur.fetchall()

        users = []
        for row in rows:
            overrides = get_permission_overrides(cur, row["id"])
            permissions = get_effective_permissions(cur, row)
            users.append(
                {
                    "id": row["id"],
                    "username": row["username"],
                    "role": row["role"],
                    "real_name": row["real_name"],
                    "phone": row["phone"],
                    "station_id": row["station_id"],
                    "station_name": row["station_name"],
                    "station_region": row["station_region"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "permission_overrides": overrides,
                    "permissions": permissions,
                }
            )

        cur.execute(
            """
            SELECT id, station_name, region, hos_station_code
            FROM stations
            ORDER BY region ASC NULLS LAST, station_name ASC, id ASC;
            """
        )
        stations = cur.fetchall()

        return jsonify(
            {
                "success": True,
                "users": users,
                "stations": stations,
                "roles": [
                    {"value": "root", "label": "系统管理员"},
                    {"value": "supervisor", "label": "督导组账号"},
                    {"value": "station_manager", "label": "站点账号"},
                ],
                "permissions": PERMISSION_CATALOG,
            }
        )
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/users/export", methods=["GET"])
def export_management_users():
    user_id = str(request.args.get("user_id", "")).strip()
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_user_security_schema(cur)
        conn.commit()
        require_management_user(cur, user_id, "manage_users")

        cur.execute(
            """
            SELECT
                u.id,
                u.username,
                u.password,
                u.role,
                u.real_name,
                u.phone,
                u.station_id,
                s.station_name,
                s.hos_station_code,
                TO_CHAR(u.created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at,
                TO_CHAR(u.updated_at, 'YYYY-MM-DD HH24:MI:SS') AS updated_at
            FROM users u
            LEFT JOIN stations s ON u.station_id = s.id
            ORDER BY
                CASE u.role
                    WHEN 'root' THEN 1
                    WHEN 'supervisor' THEN 2
                    ELSE 3
                END,
                u.id ASC;
            """
        )
        rows = cur.fetchall()
        users = []
        for row in rows:
            users.append(
                {
                    "id": row["id"],
                    "username": row["username"],
                    "password": row["password"],
                    "role": row["role"],
                    "real_name": row["real_name"],
                    "phone": row["phone"],
                    "station_id": row["station_id"],
                    "station_name": row["station_name"],
                    "hos_station_code": row["hos_station_code"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "must_change_password": row["password"] == DEFAULT_INITIAL_PASSWORD,
                    "permission_overrides": get_permission_overrides(cur, row["id"]),
                    "permissions": get_effective_permissions(cur, row),
                }
            )

        now = beijing_now()
        response = jsonify(
            {
                "backup_type": "ywddzx_users",
                "version": 1,
                "exported_at": now.isoformat(),
                "includes_passwords": True,
                "password_backup_mode": "database_current_value",
                "default_password_policy": "password == 123456 triggers forced password change on next login",
                "users": users,
            }
        )
        filename = f"ywddzx_users_backup_{now.strftime('%Y%m%d_%H%M%S')}.json"
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        response.headers["Cache-Control"] = "no-store"
        return response
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/users/import", methods=["POST"])
def import_management_users():
    user_id = str(request.form.get("user_id", "")).strip()
    backup_file = request.files.get("file")
    conn = None
    cur = None

    try:
        raw_users = parse_user_backup_json(backup_file)
        user_payloads = []
        skipped_builtin_count = 0
        for raw_user in raw_users:
            if not isinstance(raw_user, dict):
                raise ValueError("用户备份文件中存在无效的用户记录。")

            raw_username = normalize_text(raw_user.get("username"), 80)
            raw_role = normalize_text(raw_user.get("role"))
            if (raw_username == "root") != (raw_role == "root"):
                raise ValueError("root 账号备份记录必须同时使用用户名 root 和角色 root。")

            user_data = build_management_user_payload(raw_user, is_create=True)

            raw_permissions = raw_user.get("permissions")
            if raw_permissions in (None, ""):
                raw_permissions = raw_user.get("permission_overrides")
            user_data["user_id"] = normalize_user_backup_id(raw_user.get("id"))
            user_data["permissions"] = normalize_permission_updates(raw_permissions)
            user_data["created_at"] = normalize_text(raw_user.get("created_at")) or None
            user_data["updated_at"] = normalize_text(raw_user.get("updated_at")) or None
            user_payloads.append(user_data)

        if not user_payloads:
            raise ValueError("用户备份文件中没有可导入的非 root 用户。")

        conn = get_db_connection()
        cur = conn.cursor()
        ensure_user_security_schema(cur)
        actor = require_management_user(cur, user_id, "manage_users")

        imported_count = 0
        restored_root_count = 0
        auth_invalidated = False
        for user_data in user_payloads:
            if user_data["role"] == "root":
                if user_data["username"] != "root":
                    raise ValueError("root 账号备份记录的用户名必须为 root。")

                cur.execute(
                    """
                    SELECT id, password
                    FROM users
                    WHERE username = 'root'
                    LIMIT 1;
                    """
                )
                root_user = cur.fetchone()
                if not root_user:
                    raise ValueError("系统内置 root 账号不存在，请先检查用户表初始化状态。")

                if root_user["id"] == actor["id"] and root_user["password"] != user_data["password"]:
                    auth_invalidated = True

                cur.execute(
                    """
                    UPDATE users
                    SET password = %(password)s,
                        role = 'root',
                        real_name = %(real_name)s,
                        phone = %(phone)s,
                        station_id = NULL,
                        updated_at = COALESCE(NULLIF(%(updated_at)s, '')::timestamp, CURRENT_TIMESTAMP)
                    WHERE id = %(root_user_id)s
                    RETURNING id;
                    """,
                    {**user_data, "root_user_id": root_user["id"]},
                )
                target_user_id = cur.fetchone()["id"]
                cur.execute("DELETE FROM user_permissions WHERE user_id = %s;", (target_user_id,))
                imported_count += 1
                restored_root_count += 1
                continue

            if user_data["role"] == "station_manager":
                cur.execute(
                    """
                    SELECT id
                    FROM stations
                    WHERE id = %s
                    LIMIT 1;
                    """,
                    (user_data["station_id"],),
                )
                if not cur.fetchone():
                    raise ValueError("用户备份文件中的站点账号关联了不存在的站点ID，请先导入站点备份。")

            cur.execute(
                """
                SELECT id, role
                FROM users
                WHERE username = %s
                LIMIT 1;
                """,
                (user_data["username"],),
            )
            existing_by_username = cur.fetchone()

            if existing_by_username and existing_by_username["role"] == "root":
                skipped_builtin_count += 1
                continue

            target_user_id = None
            if existing_by_username:
                target_user_id = existing_by_username["id"]
                cur.execute(
                    """
                    UPDATE users
                    SET password = %(password)s,
                        role = %(role)s,
                        real_name = %(real_name)s,
                        phone = %(phone)s,
                        station_id = %(station_id)s,
                        updated_at = COALESCE(NULLIF(%(updated_at)s, '')::timestamp, CURRENT_TIMESTAMP)
                    WHERE id = %(target_user_id)s
                    RETURNING id;
                    """,
                    {**user_data, "target_user_id": target_user_id},
                )
                target_user_id = cur.fetchone()["id"]
            else:
                backup_user_id = user_data["user_id"]
                if backup_user_id:
                    cur.execute(
                        """
                        SELECT id, role
                        FROM users
                        WHERE id = %s
                        LIMIT 1;
                        """,
                        (backup_user_id,),
                    )
                    existing_by_id = cur.fetchone()
                    if existing_by_id:
                        backup_user_id = None

                if backup_user_id:
                    cur.execute(
                        """
                        INSERT INTO users (
                            id,
                            username,
                            password,
                            role,
                            real_name,
                            phone,
                            station_id,
                            created_at,
                            updated_at
                        )
                        VALUES (
                            %(user_id)s,
                            %(username)s,
                            %(password)s,
                            %(role)s,
                            %(real_name)s,
                            %(phone)s,
                            %(station_id)s,
                            COALESCE(NULLIF(%(created_at)s, '')::timestamp, CURRENT_TIMESTAMP),
                            COALESCE(NULLIF(%(updated_at)s, '')::timestamp, CURRENT_TIMESTAMP)
                        )
                        RETURNING id;
                        """,
                        {**user_data, "user_id": backup_user_id},
                    )
                    target_user_id = cur.fetchone()["id"]
                else:
                    cur.execute(
                        """
                        INSERT INTO users (
                            username,
                            password,
                            role,
                            real_name,
                            phone,
                            station_id,
                            created_at,
                            updated_at
                        )
                        VALUES (
                            %(username)s,
                            %(password)s,
                            %(role)s,
                            %(real_name)s,
                            %(phone)s,
                            %(station_id)s,
                            COALESCE(NULLIF(%(created_at)s, '')::timestamp, CURRENT_TIMESTAMP),
                            COALESCE(NULLIF(%(updated_at)s, '')::timestamp, CURRENT_TIMESTAMP)
                        )
                        RETURNING id;
                        """,
                        user_data,
                    )
                    target_user_id = cur.fetchone()["id"]

            target_user = {
                "id": target_user_id,
                "role": user_data["role"],
            }
            cur.execute("DELETE FROM user_permissions WHERE user_id = %s;", (target_user_id,))
            apply_user_permission_updates(cur, target_user, user_data["permissions"], actor["id"])
            imported_count += 1

        cur.execute(
            """
            SELECT setval(
                pg_get_serial_sequence('users', 'id'),
                GREATEST(COALESCE((SELECT MAX(id) FROM users), 1), 1),
                TRUE
            );
            """
        )
        conn.commit()

        skipped_text = f"，已跳过 {skipped_builtin_count} 条内置 root 记录" if skipped_builtin_count else ""
        return jsonify(
            {
                "success": True,
                "message": f"用户数据导入完成，共处理 {imported_count} 条记录{skipped_text}。",
                "count": imported_count,
                "skipped_builtin_count": skipped_builtin_count,
                "restored_root_count": restored_root_count,
                "auth_invalidated": auth_invalidated,
            }
        )
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        if getattr(e, "pgcode", "") == "23505":
            return jsonify({"success": False, "error": "导入失败：备份文件中的用户名与现有用户存在冲突。"}), 400
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/users", methods=["POST"])
def create_management_user():
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    conn = None
    cur = None

    try:
        user_data = build_management_user_payload(data, is_create=True)
        if user_data["role"] == "root":
            return jsonify({"success": False, "error": "系统管理员账号为内置账号，不能通过页面新增。"}), 400
        permissions = normalize_permission_updates(data.get("permissions"))
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_user_security_schema(cur)
        actor = require_management_user(cur, user_id, "manage_users")

        cur.execute(
            """
            INSERT INTO users (
                username,
                password,
                role,
                real_name,
                phone,
                station_id,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id, username, role;
            """,
            (
                user_data["username"],
                user_data["password"],
                user_data["role"],
                user_data["real_name"],
                user_data["phone"],
                user_data["station_id"],
            ),
        )
        created_user = cur.fetchone()
        apply_user_permission_updates(cur, created_user, permissions, actor["id"])
        conn.commit()
        return jsonify({"success": True, "message": "用户已新增。", "id": created_user["id"]})
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        if getattr(e, "pgcode", "") == "23505":
            return jsonify({"success": False, "error": "用户名已存在。"}), 400
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/users/<int:target_user_id>", methods=["PUT"])
def update_management_user(target_user_id):
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    conn = None
    cur = None

    try:
        user_data = build_management_user_payload(data, is_create=False)
        permissions = normalize_permission_updates(data.get("permissions"))
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_user_security_schema(cur)
        actor = require_management_user(cur, user_id, "manage_users")

        cur.execute(
            """
            SELECT id, username, role
            FROM users
            WHERE id = %s
            LIMIT 1;
            """,
            (target_user_id,),
        )
        target_user = cur.fetchone()
        if not target_user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        if target_user["role"] == "root" and user_data["role"] != "root":
            return jsonify({"success": False, "error": "root 系统管理员角色不可修改。"}), 400

        if target_user["role"] != "root" and user_data["role"] == "root":
            return jsonify({"success": False, "error": "不能将普通用户升级为 root 系统管理员。"}), 400

        if user_data["password"]:
            cur.execute(
                """
                UPDATE users
                SET username = %s,
                    password = %s,
                    role = %s,
                    real_name = %s,
                    phone = %s,
                    station_id = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING id, username, role;
                """,
                (
                    user_data["username"],
                    user_data["password"],
                    user_data["role"],
                    user_data["real_name"],
                    user_data["phone"],
                    user_data["station_id"],
                    target_user_id,
                ),
            )
        else:
            cur.execute(
                """
                UPDATE users
                SET username = %s,
                    role = %s,
                    real_name = %s,
                    phone = %s,
                    station_id = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING id, username, role;
                """,
                (
                    user_data["username"],
                    user_data["role"],
                    user_data["real_name"],
                    user_data["phone"],
                    user_data["station_id"],
                    target_user_id,
                ),
            )
        updated_user = cur.fetchone()
        apply_user_permission_updates(cur, updated_user, permissions, actor["id"])
        conn.commit()
        return jsonify({"success": True, "message": "用户已更新。"})
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        if getattr(e, "pgcode", "") == "23505":
            return jsonify({"success": False, "error": "用户名已存在。"}), 400
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/users/<int:target_user_id>", methods=["DELETE"])
def delete_management_user(target_user_id):
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id") or request.args.get("user_id", "")).strip()
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_user_security_schema(cur)
        actor = require_management_user(cur, user_id, "manage_users")
        if str(actor["id"]) == str(target_user_id):
            return jsonify({"success": False, "error": "不能删除当前登录账号。"}), 400

        cur.execute(
            """
            SELECT id, role
            FROM users
            WHERE id = %s
            LIMIT 1;
            """,
            (target_user_id,),
        )
        target_user = cur.fetchone()
        if not target_user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        if target_user["role"] == "root":
            return jsonify({"success": False, "error": "root 系统管理员账号不可删除。"}), 400

        cur.execute("DELETE FROM users WHERE id = %s;", (target_user_id,))
        conn.commit()
        return jsonify({"success": True, "message": "用户已删除。"})
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/feedbacks/unread-count", methods=["GET"])
def get_system_feedback_unread_count():
    current_user = get_current_request_user()
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_feedback_schema(cur)
        unread_count = get_feedback_unread_count(cur, current_user["id"])
        conn.commit()
        return jsonify({"success": True, "unread_count": unread_count})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/feedbacks/mark-read", methods=["POST"])
def mark_system_feedbacks_read():
    current_user = get_current_request_user()
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_feedback_schema(cur)
        mark_feedbacks_read(cur, current_user["id"])
        conn.commit()
        return jsonify({"success": True, "unread_count": 0})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/feedbacks", methods=["GET"])
def get_system_feedbacks():
    current_user = get_current_request_user()
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_feedback_schema(cur)
        conn.commit()

        cur.execute(
            """
            SELECT
                id,
                feedback_type,
                module,
                title,
                description,
                created_by,
                author_name,
                author_phone,
                author_role,
                accepted_by,
                TO_CHAR(accepted_at, 'YYYY-MM-DD HH24:MI') AS accepted_at,
                TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI') AS created_at
            FROM system_feedbacks
            ORDER BY id DESC
            LIMIT 200;
            """
        )
        feedback_rows = cur.fetchall()
        feedback_ids = [row["id"] for row in feedback_rows]

        screenshots_by_feedback = {feedback_id: [] for feedback_id in feedback_ids}
        comments_by_feedback = {feedback_id: [] for feedback_id in feedback_ids}

        if feedback_ids:
            cur.execute(
                """
                SELECT
                    id,
                    feedback_id,
                    file_path,
                    sort_order
                FROM system_feedback_screenshots
                WHERE feedback_id = ANY(%s)
                ORDER BY feedback_id ASC, sort_order ASC, id ASC;
                """,
                (feedback_ids,),
            )
            for row in cur.fetchall():
                screenshots_by_feedback.setdefault(row["feedback_id"], []).append(dict(row))

            cur.execute(
                """
                SELECT
                    id,
                    feedback_id,
                    comment_text,
                    created_by,
                    author_name,
                    author_phone,
                    author_role,
                    TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI') AS created_at
                FROM system_feedback_comments
                WHERE feedback_id = ANY(%s)
                ORDER BY feedback_id ASC, id ASC;
                """,
                (feedback_ids,),
            )
            for row in cur.fetchall():
                comments_by_feedback.setdefault(row["feedback_id"], []).append(
                    serialize_feedback_comment(row, is_root_user(current_user))
                )

        return jsonify(
            {
                "success": True,
                "items": [
                    serialize_feedback_row(
                        row,
                        screenshots_by_feedback.get(row["id"], []),
                        comments_by_feedback.get(row["id"], []),
                        is_root_user(current_user),
                    )
                    for row in feedback_rows
                ],
                "options": {
                    "feedback_types": sorted(FEEDBACK_TYPE_OPTIONS),
                    "modules": sorted(FEEDBACK_MODULE_OPTIONS),
                },
                "can_delete": is_root_user(current_user),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/feedbacks", methods=["POST"])
def create_system_feedback():
    current_user = get_current_request_user()
    saved_files = []
    conn = None
    cur = None

    try:
        feedback_type = normalize_feedback_type(request.form.get("feedback_type"))
        module = normalize_feedback_module(request.form.get("module"))
        description = normalize_text(request.form.get("description"), 3000)
        screenshot_files = collect_feedback_files(request.files)

        if not description:
            return jsonify({"success": False, "error": "请填写详细说明。"}), 400
        if len(screenshot_files) > 6:
            return jsonify({"success": False, "error": "最多上传 6 张截图。"}), 400

        title_result = generate_feedback_title(feedback_type, module, description)
        title = normalize_text(title_result.get("title"), 120) or "系统反馈事项"

        for file_storage in screenshot_files:
            saved_files.append(save_uploaded_file(file_storage, "feedback_screenshots"))

        conn = get_db_connection()
        cur = conn.cursor()
        ensure_feedback_schema(cur)
        author = build_feedback_author_snapshot(current_user)

        cur.execute(
            """
            INSERT INTO system_feedbacks (
                feedback_type,
                module,
                title,
                description,
                created_by,
                author_name,
                author_phone,
                author_role
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (
                feedback_type,
                module,
                title,
                description,
                current_user["id"],
                author["author_name"],
                author["author_phone"],
                author["author_role"],
            ),
        )
        feedback = cur.fetchone()
        feedback_id = feedback["id"]

        for index, file_path in enumerate(saved_files, start=1):
            cur.execute(
                """
                INSERT INTO system_feedback_screenshots (
                    feedback_id,
                    file_path,
                    sort_order
                )
                VALUES (%s, %s, %s);
                """,
                (feedback_id, file_path, index),
            )

        record_ai_usage_log(
            cur,
            current_user,
            title_result,
            "系统反馈",
            "自动生成反馈标题",
            f"{feedback_type} · {module} · {description[:160]}",
        )

        conn.commit()
        return jsonify(
            {
                "success": True,
                "message": "反馈已发布，所有用户均可查看并参与讨论。",
                "id": feedback_id,
                "title": title,
                "ai_title_generated": bool(title_result.get("generated")),
                "ai_title_message": title_result.get("message") or "",
            }
        )
    except ValueError as e:
        if conn:
            conn.rollback()
        for file_path in saved_files:
            remove_storage_file(file_path)
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        for file_path in saved_files:
            remove_storage_file(file_path)
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/feedbacks/<int:feedback_id>/comments", methods=["POST"])
def create_system_feedback_comment(feedback_id):
    current_user = get_current_request_user()
    data = request.get_json(silent=True) or {}
    comment_text = normalize_text(data.get("comment_text"), 1200)
    conn = None
    cur = None

    if not comment_text:
        return jsonify({"success": False, "error": "请填写讨论内容。"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_feedback_schema(cur)

        cur.execute("SELECT id FROM system_feedbacks WHERE id = %s LIMIT 1;", (feedback_id,))
        if not cur.fetchone():
            return jsonify({"success": False, "error": "反馈不存在。"}), 404

        author = build_feedback_author_snapshot(current_user)
        cur.execute(
            """
            INSERT INTO system_feedback_comments (
                feedback_id,
                comment_text,
                created_by,
                author_name,
                author_phone,
                author_role
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING
                id,
                feedback_id,
                comment_text,
                created_by,
                author_name,
                author_phone,
                author_role,
                TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI') AS created_at;
            """,
            (
                feedback_id,
                comment_text,
                current_user["id"],
                author["author_name"],
                author["author_phone"],
                author["author_role"],
            ),
        )
        comment = cur.fetchone()
        conn.commit()
        return jsonify(
            {
                "success": True,
                "message": "讨论已发布。",
                "comment": serialize_feedback_comment(comment, is_root_user(current_user)),
            }
        )
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/feedbacks/<int:feedback_id>/acceptance", methods=["PATCH"])
def update_system_feedback_acceptance(feedback_id):
    current_user = get_current_request_user()
    if not is_root_user(current_user):
        return jsonify({"success": False, "error": "只有 root 账号可以设置反馈采纳状态。"}), 403

    data = request.get_json(silent=True) or {}
    accepted = bool(data.get("accepted"))
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_feedback_schema(cur)

        cur.execute(
            """
            UPDATE system_feedbacks
            SET accepted_at = CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE NULL END,
                accepted_by = CASE WHEN %s THEN %s ELSE NULL END
            WHERE id = %s
            RETURNING
                id,
                accepted_by,
                TO_CHAR(accepted_at, 'YYYY-MM-DD HH24:MI') AS accepted_at;
            """,
            (accepted, accepted, current_user["id"], feedback_id),
        )
        feedback = cur.fetchone()
        if not feedback:
            conn.rollback()
            return jsonify({"success": False, "error": "反馈不存在。"}), 404

        conn.commit()
        return jsonify(
            {
                "success": True,
                "message": "反馈已标记为已采纳。" if accepted else "反馈已取消采纳。",
                "feedback": {
                    "id": feedback["id"],
                    "accepted_by": feedback["accepted_by"],
                    "accepted_at": feedback["accepted_at"],
                    "is_accepted": bool(feedback["accepted_at"]),
                },
            }
        )
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/feedbacks/<int:feedback_id>", methods=["DELETE"])
def delete_system_feedback(feedback_id):
    current_user = get_current_request_user()
    if not is_root_user(current_user):
        return jsonify({"success": False, "error": "只有 root 账号可以删除反馈。"}), 403

    conn = None
    cur = None
    files_to_remove = []

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_feedback_schema(cur)

        cur.execute("SELECT id FROM system_feedbacks WHERE id = %s LIMIT 1;", (feedback_id,))
        if not cur.fetchone():
            conn.rollback()
            return jsonify({"success": False, "error": "反馈不存在。"}), 404

        cur.execute(
            """
            SELECT file_path
            FROM system_feedback_screenshots
            WHERE feedback_id = %s;
            """,
            (feedback_id,),
        )
        files_to_remove = [row["file_path"] for row in cur.fetchall() if row.get("file_path")]

        cur.execute("DELETE FROM system_feedback_comments WHERE feedback_id = %s;", (feedback_id,))
        cur.execute("DELETE FROM system_feedback_screenshots WHERE feedback_id = %s;", (feedback_id,))
        cur.execute("DELETE FROM system_feedbacks WHERE id = %s;", (feedback_id,))

        conn.commit()
        for file_path in files_to_remove:
            remove_storage_file(file_path)
        return jsonify({"success": True, "message": "反馈已删除。"})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/feedback-comments/<int:comment_id>", methods=["DELETE"])
def delete_system_feedback_comment(comment_id):
    current_user = get_current_request_user()
    if not is_root_user(current_user):
        return jsonify({"success": False, "error": "只有 root 账号可以删除讨论。"}), 403

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_feedback_schema(cur)
        cur.execute("DELETE FROM system_feedback_comments WHERE id = %s;", (comment_id,))
        if cur.rowcount == 0:
            return jsonify({"success": False, "error": "讨论不存在。"}), 404
        conn.commit()
        return jsonify({"success": True, "message": "讨论已删除。"})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/ai-usage", methods=["GET"])
def get_management_ai_usage():
    user_id = str(request.args.get("user_id", "")).strip()
    date_from = str(request.args.get("date_from", "")).strip()
    date_to = str(request.args.get("date_to", "")).strip()
    usage_module = str(request.args.get("usage_module", "")).strip()
    model = str(request.args.get("model", "")).strip()
    status = str(request.args.get("status", "")).strip()
    keyword = str(request.args.get("keyword", "")).strip()
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_user_security_schema(cur)
        ensure_ai_usage_schema(cur)
        require_management_user(cur, user_id, "manage_ai_usage")

        where_clauses = []
        params = []

        if date_from:
            datetime.strptime(date_from, "%Y-%m-%d")
            where_clauses.append("created_at >= %s::date")
            params.append(date_from)

        if date_to:
            datetime.strptime(date_to, "%Y-%m-%d")
            where_clauses.append("created_at < (%s::date + INTERVAL '1 day')")
            params.append(date_to)

        if usage_module:
            where_clauses.append("usage_module = %s")
            params.append(usage_module)

        if model:
            where_clauses.append("model = %s")
            params.append(model)

        if status == "success":
            where_clauses.append("success = TRUE")
        elif status == "fallback":
            where_clauses.append("fallback_used = TRUE")
        elif status == "called":
            where_clauses.append("ai_called = TRUE")
        elif status == "not_called":
            where_clauses.append("ai_called = FALSE")

        if keyword:
            where_clauses.append(
                """
                (
                    username ILIKE %s OR
                    real_name ILIKE %s OR
                    usage_module ILIKE %s OR
                    usage_action ILIKE %s OR
                    request_summary ILIKE %s
                )
                """
            )
            like_keyword = f"%{keyword}%"
            params.extend([like_keyword] * 5)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        cur.execute(
            f"""
            SELECT
                id,
                user_id,
                username,
                real_name,
                role,
                usage_module,
                usage_action,
                model,
                base_url,
                ai_called,
                ai_generated,
                success,
                fallback_used,
                status_code,
                prompt_chars,
                prompt_chinese_chars,
                prompt_other_chars,
                completion_chars,
                completion_chinese_chars,
                completion_other_chars,
                total_chars,
                input_tokens_est,
                output_tokens_est,
                total_tokens_est,
                input_cost_est,
                output_cost_est,
                total_cost_est,
                message,
                request_summary,
                TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI') AS created_at
            FROM ai_usage_logs
            {where_sql}
            ORDER BY id DESC
            LIMIT 2000;
            """,
            params,
        )
        rows = [serialize_ai_usage_row(row) for row in cur.fetchall()]

        cur.execute(
            """
            SELECT DISTINCT usage_module
            FROM ai_usage_logs
            WHERE usage_module IS NOT NULL AND usage_module <> ''
            ORDER BY usage_module ASC;
            """
        )
        modules = [row["usage_module"] for row in cur.fetchall()]

        cur.execute(
            """
            SELECT DISTINCT model
            FROM ai_usage_logs
            WHERE model IS NOT NULL AND model <> ''
            ORDER BY model ASC;
            """
        )
        models = [row["model"] for row in cur.fetchall()]
        conn.commit()

        return jsonify(
            {
                "success": True,
                "summary": build_ai_usage_summary(rows),
                "by_user": build_ai_usage_aggregate(
                    rows,
                    ["user_id", "username"],
                    lambda row: row.get("real_name")
                    or row.get("username")
                    or f"用户{row.get('user_id') or '-'}",
                ),
                "by_context": build_ai_usage_aggregate(
                    rows,
                    ["usage_module", "usage_action"],
                    lambda row: f"{row.get('usage_module') or '-'} · {row.get('usage_action') or '-'}",
                ),
                "items": rows,
                "options": {
                    "modules": modules,
                    "models": models,
                    "pricing": get_ai_pricing_table(),
                    "status": [
                        {"value": "", "label": "全部状态"},
                        {"value": "success", "label": "AI 成功"},
                        {"value": "fallback", "label": "使用回退"},
                        {"value": "called", "label": "已请求 AI"},
                        {"value": "not_called", "label": "未请求 AI"},
                    ],
                },
            }
        )
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except ValueError:
        return jsonify({"success": False, "error": "日期格式不正确。"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/backups", methods=["GET"])
def get_management_backups():
    user_id = str(request.args.get("user_id", "")).strip()
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        require_management_user(cur, user_id, "manage_backups")
        config = read_backup_config()
        cos_status, latest_cos_backups = get_cos_backup_overview(config)
        return jsonify(
            {
                "success": True,
                "config": {
                    **config,
                    "next_run_at": get_backup_next_run_at(config),
                    "cos": cos_status,
                },
                "frequency_options": [
                    {"value": "off", "label": "关闭自动备份"},
                    {"value": "hourly", "label": "每小时"},
                    {"value": "daily", "label": "每天"},
                    {"value": "weekly", "label": "每周"},
                    {"value": "monthly", "label": "每月"},
                ],
                "latest_backups": list_backup_files(config.get("destination_path")),
                "latest_cos_backups": latest_cos_backups,
            }
        )
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/backups/config", methods=["PUT"])
def update_management_backup_config():
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    conn = None
    cur = None

    try:
        frequency = str(data.get("frequency") or "off").strip()
        if frequency not in BACKUP_FREQUENCY_INTERVALS:
            raise ValueError("自动备份频率不正确。")

        scheduled_time = normalize_backup_scheduled_time(data.get("scheduled_time"))
        destination_path = normalize_backup_destination_path(data.get("destination_path"))
        conn = get_db_connection()
        cur = conn.cursor()
        require_management_user(cur, user_id, "manage_backups")

        os.makedirs(destination_path, exist_ok=True)
        test_path = os.path.join(destination_path, ".ywddzx_backup_write_test")
        with open(test_path, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(test_path)

        current_config = read_backup_config()
        previous_destination_path = current_config.get("destination_path")
        config = write_backup_config(
            {
                **current_config,
                "destination_path": destination_path,
                "frequency": frequency,
                "scheduled_time": scheduled_time,
                "next_auto_run_at": calculate_next_auto_run_at(
                    {
                        **current_config,
                        "frequency": frequency,
                        "scheduled_time": scheduled_time,
                    }
                ),
                "last_status": current_config.get("last_status") or "idle",
                "last_error": current_config.get("last_error") or "",
            }
        )
        if (
            previous_destination_path
            and os.path.abspath(previous_destination_path) != os.path.abspath(destination_path)
        ):
            cleanup_local_backup_files(previous_destination_path)
        cos_status, latest_cos_backups = get_cos_backup_overview(config)
        return jsonify(
            {
                "success": True,
                "message": "备份设置已保存。",
                "config": {
                    **config,
                    "next_run_at": get_backup_next_run_at(config),
                    "cos": cos_status,
                },
                "latest_backups": list_backup_files(config.get("destination_path")),
                "latest_cos_backups": latest_cos_backups,
            }
        )
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except OSError as exc:
        return jsonify({"success": False, "error": f"备份目录不可写：{exc}"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/backups/export", methods=["POST"])
def export_management_full_backup():
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        require_management_user(cur, user_id, "manage_backups")
        close_db_resources(cur, conn)
        cur = None
        conn = None

        if not backup_job_lock.acquire(blocking=False):
            return jsonify({"success": False, "error": "已有备份或恢复任务正在执行，请稍后再试。"}), 409
        try:
            config = read_backup_config()
            result = create_full_backup_archive(config.get("destination_path"), reason="manual")
            cos_result = result.get("cos") or {}
            cos_status = cos_result.get("status") or "not_configured"
            config.update(
                {
                    "last_backup_path": result["path"],
                    "last_backup_size": result["size"],
                    "last_cos_status": cos_status,
                    "last_cos_key": cos_result.get("key"),
                    "last_cos_uploaded_at": cos_result.get("uploaded_at"),
                    "last_cos_retained_count": cos_result.get("retained_count") or 0,
                    "last_cos_error": cos_result.get("message") if cos_status == "error" else "",
                    "last_status": "warning" if cos_status == "error" else "success",
                    "last_error": cos_result.get("message") if cos_status == "error" else "",
                }
            )
            write_backup_config(config)
        finally:
            backup_job_lock.release()

        response = send_file(
            result["path"],
            as_attachment=True,
            download_name=result["download_filename"],
            mimetype="application/zip",
        )
        response.headers["X-Backup-Path"] = result["path"]
        response.headers["X-Backup-Size"] = str(result["size"])
        response.headers["X-COS-Backup-Status"] = cos_status
        response.headers["X-COS-Backup-Key"] = cos_result.get("key") or ""
        response.headers["Cache-Control"] = "no-store"
        return response
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/backups/import", methods=["POST"])
def import_management_full_backup():
    user_id = str(request.form.get("user_id", "")).strip()
    backup_file = request.files.get("file")
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        require_management_user(cur, user_id, "manage_backups")
        close_db_resources(cur, conn)
        cur = None
        conn = None

        if not backup_job_lock.acquire(blocking=False):
            return jsonify({"success": False, "error": "已有备份或恢复任务正在执行，请稍后再试。"}), 409
        try:
            manifest = restore_full_backup_archive(backup_file)
        finally:
            backup_job_lock.release()

        config = read_backup_config()
        config.update(
            {
                "last_status": "success",
                "last_error": "",
            }
        )
        write_backup_config(config)
        return jsonify(
            {
                "success": True,
                "message": "完整备份已导入，数据库与上传文件目录已恢复。",
                "manifest": manifest,
            }
        )
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/stations", methods=["GET"])
def get_management_stations():
    user_id = str(request.args.get("user_id", "")).strip()
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_station_management_columns(cur)
        conn.commit()
        require_management_user(cur, user_id, "manage_stations")

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
                CASE
                    WHEN asset_type LIKE '%股权%' OR asset_type LIKE '%控股%' OR asset_type LIKE '%参股%' THEN '股权'
                    ELSE '全资'
                END AS asset_type,
                COALESCE(is_consolidated, '否') AS is_consolidated,
                COALESCE(online_3_status, '未上线') AS online_3_status,
                hos_station_code,
                landline_phone,
                status,
                operating_hours,
                TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI') AS created_at,
                TO_CHAR(updated_at, 'YYYY-MM-DD HH24:MI') AS updated_at
            FROM stations
            ORDER BY id ASC;
            """
        )
        rows = cur.fetchall()
        return jsonify(
            {
                "success": True,
                "stations": rows,
                "options": {
                    "station_types": ["加油站", "充电站"],
                    "asset_types": ["全资", "股权"],
                    "is_consolidated": ["是", "否"],
                    "online_3_statuses": ["上线", "上线参股模式", "未上线"],
                    "statuses": ["营业中", "停业"],
                },
            }
        )
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/stations/export", methods=["GET"])
def export_management_stations():
    user_id = str(request.args.get("user_id", "")).strip()
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_station_management_columns(cur)
        conn.commit()
        require_management_user(cur, user_id, "manage_stations")

        cur.execute(
            """
            SELECT
                id,
                station_name,
                region,
                address,
                longitude::TEXT AS longitude,
                latitude::TEXT AS latitude,
                station_manager_name,
                station_manager_phone,
                station_type,
                CASE
                    WHEN asset_type LIKE '%股权%' OR asset_type LIKE '%控股%' OR asset_type LIKE '%参股%' THEN '股权'
                    ELSE '全资'
                END AS asset_type,
                COALESCE(is_consolidated, '否') AS is_consolidated,
                COALESCE(online_3_status, '未上线') AS online_3_status,
                hos_station_code,
                landline_phone,
                COALESCE(status, '营业中') AS status,
                COALESCE(operating_hours, '24小时') AS operating_hours,
                TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at,
                TO_CHAR(updated_at, 'YYYY-MM-DD HH24:MI:SS') AS updated_at
            FROM stations
            ORDER BY id ASC;
            """
        )
        rows = cur.fetchall()
        now = beijing_now()
        response = jsonify(
            {
                "backup_type": "ywddzx_stations",
                "version": 1,
                "exported_at": now.isoformat(),
                "stations": rows,
            }
        )
        filename = f"ywddzx_stations_backup_{now.strftime('%Y%m%d_%H%M%S')}.json"
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        response.headers["Cache-Control"] = "no-store"
        return response
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/stations/import", methods=["POST"])
def import_management_stations():
    user_id = str(request.form.get("user_id", "")).strip()
    backup_file = request.files.get("file")
    conn = None
    cur = None

    try:
        raw_stations = parse_station_backup_json(backup_file)
        station_payloads = []
        for raw_station in raw_stations:
            if not isinstance(raw_station, dict):
                raise ValueError("站点备份文件中存在无效的站点记录。")
            station_data = build_station_payload(raw_station)
            station_data["station_id"] = normalize_station_backup_id(raw_station.get("id"))
            station_data["created_at"] = normalize_text(raw_station.get("created_at")) or None
            station_data["updated_at"] = normalize_text(raw_station.get("updated_at")) or None
            station_payloads.append(station_data)

        conn = get_db_connection()
        cur = conn.cursor()
        ensure_station_management_columns(cur)
        require_management_user(cur, user_id, "manage_stations")

        imported_count = 0
        for station_data in station_payloads:
            if station_data["station_id"]:
                cur.execute(
                    """
                    INSERT INTO stations (
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
                        is_consolidated,
                        online_3_status,
                        hos_station_code,
                        landline_phone,
                        status,
                        operating_hours,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        %(station_id)s,
                        %(station_name)s,
                        %(region)s,
                        %(address)s,
                        %(longitude)s,
                        %(latitude)s,
                        %(station_manager_name)s,
                        %(station_manager_phone)s,
                        %(station_type)s,
                        %(asset_type)s,
                        %(is_consolidated)s,
                        %(online_3_status)s,
                        %(hos_station_code)s,
                        %(landline_phone)s,
                        %(status)s,
                        %(operating_hours)s,
                        COALESCE(NULLIF(%(created_at)s, '')::timestamp, CURRENT_TIMESTAMP),
                        COALESCE(NULLIF(%(updated_at)s, '')::timestamp, CURRENT_TIMESTAMP)
                    )
                    ON CONFLICT (id)
                    DO UPDATE SET
                        station_name = EXCLUDED.station_name,
                        region = EXCLUDED.region,
                        address = EXCLUDED.address,
                        longitude = EXCLUDED.longitude,
                        latitude = EXCLUDED.latitude,
                        station_manager_name = EXCLUDED.station_manager_name,
                        station_manager_phone = EXCLUDED.station_manager_phone,
                        station_type = EXCLUDED.station_type,
                        asset_type = EXCLUDED.asset_type,
                        is_consolidated = EXCLUDED.is_consolidated,
                        online_3_status = EXCLUDED.online_3_status,
                        hos_station_code = EXCLUDED.hos_station_code,
                        landline_phone = EXCLUDED.landline_phone,
                        status = EXCLUDED.status,
                        operating_hours = EXCLUDED.operating_hours,
                        updated_at = EXCLUDED.updated_at;
                    """,
                    station_data,
                )
            else:
                cur.execute(
                    """
                    INSERT INTO stations (
                        station_name,
                        region,
                        address,
                        longitude,
                        latitude,
                        station_manager_name,
                        station_manager_phone,
                        station_type,
                        asset_type,
                        is_consolidated,
                        online_3_status,
                        hos_station_code,
                        landline_phone,
                        status,
                        operating_hours,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        %(station_name)s,
                        %(region)s,
                        %(address)s,
                        %(longitude)s,
                        %(latitude)s,
                        %(station_manager_name)s,
                        %(station_manager_phone)s,
                        %(station_type)s,
                        %(asset_type)s,
                        %(is_consolidated)s,
                        %(online_3_status)s,
                        %(hos_station_code)s,
                        %(landline_phone)s,
                        %(status)s,
                        %(operating_hours)s,
                        COALESCE(NULLIF(%(created_at)s, '')::timestamp, CURRENT_TIMESTAMP),
                        COALESCE(NULLIF(%(updated_at)s, '')::timestamp, CURRENT_TIMESTAMP)
                    )
                    ON CONFLICT (station_name)
                    DO UPDATE SET
                        region = EXCLUDED.region,
                        address = EXCLUDED.address,
                        longitude = EXCLUDED.longitude,
                        latitude = EXCLUDED.latitude,
                        station_manager_name = EXCLUDED.station_manager_name,
                        station_manager_phone = EXCLUDED.station_manager_phone,
                        station_type = EXCLUDED.station_type,
                        asset_type = EXCLUDED.asset_type,
                        is_consolidated = EXCLUDED.is_consolidated,
                        online_3_status = EXCLUDED.online_3_status,
                        hos_station_code = EXCLUDED.hos_station_code,
                        landline_phone = EXCLUDED.landline_phone,
                        status = EXCLUDED.status,
                        operating_hours = EXCLUDED.operating_hours,
                        updated_at = EXCLUDED.updated_at;
                    """,
                    station_data,
                )
            imported_count += 1

        cur.execute(
            """
            SELECT setval(
                pg_get_serial_sequence('stations', 'id'),
                GREATEST(COALESCE((SELECT MAX(id) FROM stations), 1), 1),
                TRUE
            );
            """
        )
        conn.commit()
        return jsonify(
            {
                "success": True,
                "message": f"站点数据导入完成，共处理 {imported_count} 条记录。",
                "count": imported_count,
            }
        )
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        if getattr(e, "pgcode", "") == "23505":
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "导入失败：备份文件中的站点名称或 HOS编码 与现有站点存在冲突。",
                    }
                ),
                400,
            )
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/stations", methods=["POST"])
def create_management_station():
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    conn = None
    cur = None

    try:
        station_data = build_station_payload(data)
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_station_management_columns(cur)
        require_management_user(cur, user_id, "manage_stations")

        cur.execute(
            """
            INSERT INTO stations (
                station_name,
                region,
                address,
                longitude,
                latitude,
                station_manager_name,
                station_manager_phone,
                station_type,
                asset_type,
                is_consolidated,
                online_3_status,
                hos_station_code,
                landline_phone,
                status,
                operating_hours,
                created_at,
                updated_at
            )
            VALUES (
                %(station_name)s,
                %(region)s,
                %(address)s,
                %(longitude)s,
                %(latitude)s,
                %(station_manager_name)s,
                %(station_manager_phone)s,
                %(station_type)s,
                %(asset_type)s,
                %(is_consolidated)s,
                %(online_3_status)s,
                %(hos_station_code)s,
                %(landline_phone)s,
                %(status)s,
                %(operating_hours)s,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            RETURNING id;
            """,
            station_data,
        )
        row = cur.fetchone()
        conn.commit()
        return jsonify({"success": True, "message": "站点已新增。", "id": row["id"]})
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        if getattr(e, "pgcode", "") == "23505":
            return jsonify({"success": False, "error": "站点名称或 HOS编码 已存在，请检查是否重复添加。"}), 400
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/stations/<int:station_id>", methods=["PUT"])
def update_management_station(station_id):
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    conn = None
    cur = None

    try:
        station_data = build_station_payload(data)
        station_data["station_id"] = station_id
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_station_management_columns(cur)
        require_management_user(cur, user_id, "manage_stations")

        cur.execute(
            """
            UPDATE stations
            SET station_name = %(station_name)s,
                region = %(region)s,
                address = %(address)s,
                longitude = %(longitude)s,
                latitude = %(latitude)s,
                station_manager_name = %(station_manager_name)s,
                station_manager_phone = %(station_manager_phone)s,
                station_type = %(station_type)s,
                asset_type = %(asset_type)s,
                is_consolidated = %(is_consolidated)s,
                online_3_status = %(online_3_status)s,
                hos_station_code = %(hos_station_code)s,
                landline_phone = %(landline_phone)s,
                status = %(status)s,
                operating_hours = %(operating_hours)s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %(station_id)s
            RETURNING id;
            """,
            station_data,
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"success": False, "error": "站点不存在。"}), 404

        conn.commit()
        return jsonify({"success": True, "message": "站点已更新。"})
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        if getattr(e, "pgcode", "") == "23505":
            return jsonify({"success": False, "error": "站点名称或 HOS编码 已存在，请检查是否重复添加。"}), 400
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/stations/<int:station_id>", methods=["DELETE"])
def delete_management_station(station_id):
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id") or request.args.get("user_id", "")).strip()
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_station_management_columns(cur)
        require_management_user(cur, user_id, "manage_stations")

        cur.execute("DELETE FROM stations WHERE id = %s RETURNING id;", (station_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"success": False, "error": "站点不存在。"}), 404

        conn.commit()
        return jsonify({"success": True, "message": "站点已删除。"})
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except Exception as e:
        if conn:
            conn.rollback()
        if getattr(e, "pgcode", "") == "23503":
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "该站点已有用户、巡检、问题或证照等业务数据引用，暂不能删除。",
                    }
                ),
                400,
            )
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/checklists", methods=["GET"])
def get_management_checklists():
    user_id = str(request.args.get("user_id", "")).strip()
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_inspection_checklist_management_schema(cur)
        conn.commit()
        require_management_user(cur, user_id, "manage_checklists")

        cur.execute(
            """
            SELECT
                id,
                table_code,
                table_name,
                checklist_mode,
                standard_id_base,
                description,
                is_active,
                TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI') AS created_at,
                TO_CHAR(updated_at, 'YYYY-MM-DD HH24:MI') AS updated_at
            FROM inspection_tables
            ORDER BY id ASC;
            """
        )
        rows = cur.fetchall()
        return jsonify(
            {
                "success": True,
                "checklists": [serialize_management_checklist(cur, row) for row in rows],
            }
        )
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/checklists", methods=["POST"])
def create_management_checklist():
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    conn = None
    cur = None

    try:
        table_code = normalize_checklist_code(data.get("table_code"))
        table_name = normalize_text(data.get("table_name"), 120)
        if not table_name:
            raise ValueError("请填写检查表名称。")
        checklist_mode = normalize_checklist_mode(data.get("checklist_mode"))
        description = normalize_text(data.get("description"), 300)
        fields = normalize_checklist_field_rows(data.get("fields"), table_code)
        physical_table_name = get_physical_table_name_by_code(table_code)

        conn = get_db_connection()
        cur = conn.cursor()
        ensure_inspection_checklist_management_schema(cur)
        require_management_user(cur, user_id, "manage_checklists")

        cur.execute(
            """
            SELECT id
            FROM inspection_tables
            WHERE table_code = %s OR table_name = %s
            LIMIT 1;
            """,
            (table_code, table_name),
        )
        if cur.fetchone():
            raise ValueError("检查表编码或名称已存在。")
        ensure_unique_checklist_field_keys(cur, fields)

        cur.execute(
            """
            INSERT INTO inspection_tables (
                table_code,
                table_name,
                checklist_mode,
                description,
                is_active,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id;
            """,
            (table_code, table_name, checklist_mode, description),
        )
        row = cur.fetchone()
        standard_id_base = get_default_checklist_standard_id_base(row["id"])
        cur.execute(
            """
            UPDATE inspection_tables
            SET standard_id_base = %s
            WHERE id = %s;
            """,
            (standard_id_base, row["id"]),
        )
        ensure_checklist_field_columns(cur, physical_table_name, fields)
        upsert_checklist_fields(cur, row["id"], fields)
        conn.commit()
        return jsonify(
            {
                "success": True,
                "message": "检查表已创建，字段结构已生成。",
                "id": row["id"],
                "standard_id_base": standard_id_base,
                "physical_table_name": physical_table_name,
            }
        )
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        if getattr(e, "pgcode", "") == "23505":
            return jsonify({"success": False, "error": "检查表编码、名称或字段系统标识已存在。"}), 400
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/checklists/<int:inspection_table_id>", methods=["PUT"])
def update_management_checklist(inspection_table_id):
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    conn = None
    cur = None

    try:
        table_name = normalize_text(data.get("table_name"), 120)
        if not table_name:
            raise ValueError("请填写检查表名称。")
        checklist_mode = normalize_checklist_mode(data.get("checklist_mode"))
        description = normalize_text(data.get("description"), 300)
        is_active = bool(data.get("is_active", True))

        conn = get_db_connection()
        cur = conn.cursor()
        ensure_inspection_checklist_management_schema(cur)
        require_management_user(cur, user_id, "manage_checklists")

        current_row = fetch_management_checklist(cur, inspection_table_id)
        if not current_row:
            return jsonify({"success": False, "error": "检查表不存在。"}), 404
        fields = normalize_checklist_field_rows(data.get("fields"), current_row["table_code"])
        ensure_unique_checklist_field_keys(cur, fields, inspection_table_id)
        physical_table_name = get_physical_table_name_by_code(current_row["table_code"])
        ensure_checklist_field_columns(cur, physical_table_name, fields)
        upsert_checklist_fields(cur, inspection_table_id, fields)
        cur.execute(
            """
            UPDATE inspection_tables
            SET table_name = %s,
                checklist_mode = %s,
                description = %s,
                is_active = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING id;
            """,
            (table_name, checklist_mode, description, is_active, inspection_table_id),
        )
        conn.commit()
        return jsonify({"success": True, "message": "检查表信息和字段结构已保存。"})
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        if getattr(e, "pgcode", "") == "23505":
            return jsonify({"success": False, "error": "检查表名称或字段系统标识已存在。"}), 400
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/checklists/<int:inspection_table_id>", methods=["DELETE"])
def delete_management_checklist(inspection_table_id):
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id") or request.args.get("user_id", "")).strip()
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_inspection_checklist_management_schema(cur)
        require_management_user(cur, user_id, "manage_checklists")

        current_row = fetch_management_checklist(cur, inspection_table_id)
        if not current_row:
            return jsonify({"success": False, "error": "检查表不存在。"}), 404

        blockers = get_blocking_checklist_references(cur, [inspection_table_id])
        if blockers:
            raise ValueError(
                "无法删除：该检查表仍被"
                f"{'、'.join(blockers)}引用。请先处理相关业务数据后再删除。"
            )

        physical_table_name = get_physical_table_name_by_code(current_row["table_code"])
        cur.execute("DELETE FROM inspection_table_fields WHERE inspection_table_id = %s;", (inspection_table_id,))
        cur.execute("DELETE FROM inspection_tables WHERE id = %s;", (inspection_table_id,))
        if physical_table_name:
            cur.execute(sql.SQL("DROP TABLE IF EXISTS {};").format(sql.Identifier(physical_table_name)))
        conn.commit()
        return jsonify({"success": True, "message": "检查表已删除。"})
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        if getattr(e, "pgcode", "") == "23503":
            return jsonify({"success": False, "error": "该检查表已有业务数据引用，暂不能删除。"}), 400
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/checklists/export", methods=["GET"])
def export_management_checklists():
    user_id = str(request.args.get("user_id", "")).strip()
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_inspection_checklist_management_schema(cur)
        conn.commit()
        require_management_user(cur, user_id, "manage_checklists")

        cur.execute(
            """
            SELECT
                id,
                table_code,
                table_name,
                checklist_mode,
                standard_id_base,
                description,
                is_active,
                TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at,
                TO_CHAR(updated_at, 'YYYY-MM-DD HH24:MI:SS') AS updated_at
            FROM inspection_tables
            ORDER BY id ASC;
            """
        )
        exported_checklists = []
        for row in cur.fetchall():
            fields = [dict(field) for field in get_management_checklist_fields(cur, row["id"])]
            physical_table_name = get_physical_table_name_by_code(row["table_code"])
            ensure_checklist_field_columns(cur, physical_table_name, fields)
            exported_checklists.append(
                {
                    "table_code": row["table_code"],
                    "table_name": row["table_name"],
                    "checklist_mode": normalize_checklist_mode(row.get("checklist_mode")),
                    "standard_id_base": normalize_checklist_standard_id_base(
                        row.get("standard_id_base"),
                        row["id"],
                    ),
                    "description": row["description"],
                    "is_active": row["is_active"],
                    "physical_table_name": physical_table_name,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "fields": fields,
                    "standards": fetch_checklist_standard_rows(cur, physical_table_name, fields),
                }
            )

        conn.commit()
        now = beijing_now()
        response = jsonify(
            {
                "backup_type": "ywddzx_checklists",
                "version": 2,
                "exported_at": now.isoformat(),
                "checklists": exported_checklists,
            }
        )
        filename = f"ywddzx_checklists_backup_{now.strftime('%Y%m%d_%H%M%S')}.json"
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        response.headers["Cache-Control"] = "no-store"
        return response
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/checklists/import", methods=["POST"])
def import_management_checklists_backup():
    user_id = str(request.form.get("user_id", "")).strip()
    backup_file = request.files.get("file")
    conn = None
    cur = None

    try:
        parsed_backup = parse_checklist_backup_file(backup_file)
        imported_checklists = parsed_backup["checklists"]
        imported_codes = {item["table_code"] for item in imported_checklists}
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_inspection_checklist_management_schema(cur)
        require_management_user(cur, user_id, "manage_checklists")

        cur.execute(
            """
            SELECT id, table_code, standard_id_base
            FROM inspection_tables
            ORDER BY id ASC;
            """
        )
        existing_rows = cur.fetchall()
        existing_by_code = {row["table_code"]: row for row in existing_rows}
        rows_to_remove = [row for row in existing_rows if row["table_code"] not in imported_codes]
        blockers = get_blocking_checklist_references(cur, [row["id"] for row in rows_to_remove])
        if blockers:
            raise ValueError(
                "无法覆盖导入：当前系统中有检查表不在备份文件内，但仍被"
                f"{'、'.join(blockers)}引用。请先处理这些业务数据，或导入包含这些检查表的备份文件。"
            )

        removed_count = 0
        for row in rows_to_remove:
            physical_table_name = get_physical_table_name_by_code(row["table_code"])
            cur.execute("DELETE FROM inspection_table_fields WHERE inspection_table_id = %s;", (row["id"],))
            cur.execute("DELETE FROM inspection_tables WHERE id = %s;", (row["id"],))
            if physical_table_name:
                cur.execute(sql.SQL("DROP TABLE IF EXISTS {};").format(sql.Identifier(physical_table_name)))
            removed_count += 1

        for item in imported_checklists:
            current_row = existing_by_code.get(item["table_code"])
            if current_row:
                inspection_table_id = current_row["id"]
                target_standard_id_base = normalize_checklist_standard_id_base(
                    current_row.get("standard_id_base"),
                    inspection_table_id,
                )
                cur.execute(
                    """
                    UPDATE inspection_tables
                    SET table_name = %s,
                        checklist_mode = %s,
                        description = %s,
                        is_active = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s;
                    """,
                    (
                        item["table_name"],
                        item["checklist_mode"],
                        item["description"],
                        item["is_active"],
                        inspection_table_id,
                    ),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO inspection_tables (
                        table_code,
                        table_name,
                        checklist_mode,
                        description,
                        is_active,
                        created_at,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    RETURNING id;
                    """,
                    (
                        item["table_code"],
                        item["table_name"],
                        item["checklist_mode"],
                        item["description"],
                        item["is_active"],
                    ),
                )
                inspection_table_id = cur.fetchone()["id"]
                target_standard_id_base = get_default_checklist_standard_id_base(inspection_table_id)
                cur.execute(
                    """
                    UPDATE inspection_tables
                    SET standard_id_base = %s
                    WHERE id = %s;
                    """,
                    (target_standard_id_base, inspection_table_id),
                )

            physical_table_name = get_physical_table_name_by_code(item["table_code"])
            cur.execute(sql.SQL("DROP TABLE IF EXISTS {};").format(sql.Identifier(physical_table_name)))
            ensure_checklist_field_columns(cur, physical_table_name, item["fields"])
            upsert_checklist_fields(cur, inspection_table_id, item["fields"])
            standards = rebase_checklist_standard_rows(
                item["standards"],
                item["standard_id_base"],
                target_standard_id_base,
            )
            insert_checklist_standard_rows(
                cur,
                physical_table_name,
                item["fields"],
                standards,
            )

        conn.commit()
        return jsonify(
            {
                "success": True,
                "message": f"巡检表备份已导入，覆盖 {len(imported_checklists)} 张检查表，移除 {removed_count} 张旧检查表。",
                "imported_count": len(imported_checklists),
                "removed_count": removed_count,
            }
        )
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": f"巡检表备份导入失败：{str(e)}"}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/checklists/<int:inspection_table_id>/standards", methods=["GET"])
def get_management_checklist_standards(inspection_table_id):
    user_id = str(request.args.get("user_id", "")).strip()
    keyword = str(request.args.get("keyword", "")).strip()
    page, page_size = normalize_page_args(
        request.args.get("page"),
        request.args.get("page_size"),
    )
    offset = (page - 1) * page_size
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_inspection_checklist_management_schema(cur)
        require_management_user(cur, user_id, "manage_checklists")
        _checklist, fields, physical_table_name = get_management_checklist_standard_context(
            cur, inspection_table_id, require_fields=False
        )

        where_sql, where_params = build_standard_search_sql(fields, keyword)
        cur.execute(
            sql.SQL("SELECT COUNT(*) AS total FROM {}{};").format(
                sql.Identifier(physical_table_name),
                where_sql,
            ),
            where_params,
        )
        total = int(cur.fetchone()["total"] or 0)
        total_pages = max((total + page_size - 1) // page_size, 1)
        if page > total_pages:
            page = total_pages
            offset = (page - 1) * page_size

        select_columns = [
            sql.Identifier("id"),
            sql.Identifier("standard_id"),
            sql.SQL("TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI') AS created_at"),
            *[sql.Identifier(field["field_key"]) for field in fields],
        ]
        cur.execute(
            sql.SQL(
                """
                SELECT {}
                FROM {}{}
                ORDER BY standard_id ASC
                LIMIT %s OFFSET %s;
                """
            ).format(
                sql.SQL(", ").join(select_columns),
                sql.Identifier(physical_table_name),
                where_sql,
            ),
            [*where_params, page_size, offset],
        )
        field_meta = [(field["field_key"], field["field_label"]) for field in fields]
        items = [serialize_standard_row(field_meta, row) for row in cur.fetchall()]
        conn.commit()
        return jsonify(
            {
                "success": True,
                "items": items,
                "fields": fields,
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
            }
        )
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/checklists/<int:inspection_table_id>/standards", methods=["POST"])
def create_management_checklist_standard(inspection_table_id):
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_inspection_checklist_management_schema(cur)
        require_management_user(cur, user_id, "manage_checklists")
        checklist, fields, physical_table_name = get_management_checklist_standard_context(
            cur, inspection_table_id
        )
        row = normalize_checklist_standard_payload(data, fields)
        row["standard_id"] = get_next_checklist_standard_id(cur, checklist, physical_table_name)

        columns = ["standard_id", *[field["field_key"] for field in fields]]
        cur.execute(
            sql.SQL(
                """
                INSERT INTO {} ({})
                VALUES ({});
                """
            ).format(
                sql.Identifier(physical_table_name),
                sql.SQL(", ").join(sql.Identifier(column) for column in columns),
                sql.SQL(", ").join(sql.Placeholder() for _ in columns),
            ),
            [row.get(column) for column in columns],
        )
        cur.execute(
            """
            UPDATE inspection_tables
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
            """,
            (inspection_table_id,),
        )
        conn.commit()
        return jsonify(
            {
                "success": True,
                "message": f"外部规范数据已新增，系统生成外部规范ID {row['standard_id']}。",
                "standard_id": row["standard_id"],
            }
        )
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        if getattr(e, "pgcode", "") == "23505":
            return jsonify({"success": False, "error": "外部规范ID自动生成冲突，请重试。"}), 400
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/checklists/<int:inspection_table_id>/standards/<standard_id>", methods=["PUT"])
def update_management_checklist_standard(inspection_table_id, standard_id):
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    conn = None
    cur = None

    try:
        old_standard_id = normalize_import_standard_id(standard_id)
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_inspection_checklist_management_schema(cur)
        require_management_user(cur, user_id, "manage_checklists")
        _checklist, fields, physical_table_name = get_management_checklist_standard_context(
            cur, inspection_table_id
        )
        row = normalize_checklist_standard_payload(data, fields)

        cur.execute(
            sql.SQL("SELECT id FROM {} WHERE standard_id = %s LIMIT 1;").format(
                sql.Identifier(physical_table_name)
            ),
            (old_standard_id,),
        )
        if not cur.fetchone():
            return jsonify({"success": False, "error": "规范数据不存在。"}), 404

        columns = [field["field_key"] for field in fields]
        cur.execute(
            sql.SQL(
                """
                UPDATE {}
                SET {}
                WHERE standard_id = %s
                RETURNING standard_id;
                """
            ).format(
                sql.Identifier(physical_table_name),
                sql.SQL(", ").join(
                    sql.SQL("{} = %s").format(sql.Identifier(column))
                    for column in columns
                ),
            ),
            [row.get(column) for column in columns] + [old_standard_id],
        )
        if not cur.fetchone():
            return jsonify({"success": False, "error": "规范数据不存在。"}), 404

        standard_detail_text = build_standard_detail_text(
            [(field["field_key"], field["field_label"]) for field in fields],
            row,
        )
        if not standard_detail_text:
            raise ValueError("规范详情生成失败，请至少保留一项规范内容。")
        synced_count = sync_referenced_standard_detail_text(
            cur,
            inspection_table_id,
            old_standard_id,
            standard_detail_text,
        )

        cur.execute(
            """
            UPDATE inspection_tables
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
            """,
            (inspection_table_id,),
        )
        conn.commit()
        message = "规范数据已保存。"
        if synced_count:
            message = f"规范数据已保存，并同步更新 {synced_count} 条已引用问题。"
        return jsonify({"success": True, "message": message, "synced_issue_count": synced_count})
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/checklists/<int:inspection_table_id>/standards/<standard_id>", methods=["DELETE"])
def delete_management_checklist_standard(inspection_table_id, standard_id):
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id") or request.args.get("user_id", "")).strip()
    conn = None
    cur = None

    try:
        standard_id_value = normalize_import_standard_id(standard_id)
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_inspection_checklist_management_schema(cur)
        require_management_user(cur, user_id, "manage_checklists")
        _checklist, fields, physical_table_name = get_management_checklist_standard_context(
            cur, inspection_table_id, require_fields=False
        )
        ensure_checklist_field_columns(cur, physical_table_name, fields)

        reference_counts = get_checklist_standard_reference_counts(
            cur,
            inspection_table_id,
            standard_id_value,
        )
        reference_message = format_checklist_standard_reference_message(reference_counts)
        if reference_message:
            raise ValueError(
                f"无法删除：该规范已被{reference_message}引用。"
                "可以编辑规范内容，系统会同步更新已引用该规范的业务数据，但不能删除已被使用的规范。"
            )

        cur.execute(
            sql.SQL("DELETE FROM {} WHERE standard_id = %s RETURNING standard_id;").format(
                sql.Identifier(physical_table_name)
            ),
            (standard_id_value,),
        )
        if not cur.fetchone():
            return jsonify({"success": False, "error": "规范数据不存在。"}), 404

        cur.execute(
            """
            UPDATE inspection_tables
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
            """,
            (inspection_table_id,),
        )
        conn.commit()
        return jsonify({"success": True, "message": "规范数据已删除。"})
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
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

        if not can_view_certificates(cur, user):
            return (
                jsonify({"success": False, "error": "当前账号无权访问证照管理。"}),
                403,
            )

        scope_all = can_edit_all_certificates(user) or can_view_all_certificates(cur, user)
        station_params = []
        station_where = ""
        if not scope_all:
            if not user["station_id"]:
                return jsonify(
                    {
                        "success": True,
                        "certificate_types": CERTIFICATE_TYPES,
                        "stations": [],
                        "records": [],
                        "can_view_all": False,
                        "can_edit_all": False,
                        "can_edit_own": can_edit_own_certificates(cur, user),
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
        if not scope_all:
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
                "can_view_all": scope_all,
                "can_edit_all": can_edit_all_certificates(user),
                "can_edit_own": can_edit_own_certificates(cur, user),
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

        can_edit_all = can_edit_all_certificates(user)
        can_edit_own = can_edit_own_certificates(cur, user)
        if not can_edit_all and not can_edit_own:
            return (
                jsonify(
                    {"success": False, "error": "当前账号无权维护证照有效期。"}
                ),
                403,
            )

        if not can_edit_all and str(station_id) != str(user.get("station_id") or ""):
            return jsonify({"success": False, "error": "当前账号只能维护本站证照有效期。"}), 403

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

        can_edit_all = can_edit_all_certificates(user)
        can_edit_own = can_edit_own_certificates(cur, user)
        if not can_edit_all and not can_edit_own:
            return (
                jsonify(
                    {"success": False, "error": "当前账号无权删除证照记录。"}
                ),
                403,
            )

        cur.execute(
            """
            SELECT id, station_id
            FROM station_certificates
            WHERE id = %s
            LIMIT 1;
            """,
            (certificate_id,),
        )
        certificate = cur.fetchone()
        if not certificate:
            return jsonify({"success": False, "error": "证照记录不存在。"}), 404

        if not can_edit_all and str(certificate["station_id"]) != str(user.get("station_id") or ""):
            return jsonify({"success": False, "error": "当前账号只能删除本站证照记录。"}), 403

        cur.execute(
            """
            DELETE FROM station_certificates
            WHERE id = %s
            RETURNING id;
            """,
            (certificate_id,),
        )

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
    user_id = str(request.args.get("user_id", "")).strip()
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
        if not has_permission(cur, user, "view_station_map"):
            return jsonify({"success": False, "error": "当前账号无权查看站点地图。"}), 403

        cur.execute(
            """
            WITH issue_counts AS (
                SELECT
                    station_id,
                    COUNT(*) FILTER (WHERE TRIM(COALESCE(status, '')) IN ('待整改', '未整改', '站经无法整改')) AS pending_rectification_count,
                    COUNT(*) FILTER (WHERE TRIM(COALESCE(status, '')) = '待复核') AS pending_review_count,
                    COUNT(*) FILTER (WHERE TRIM(COALESCE(status, '')) IN ('已闭环', '已整改')) AS closed_count
                FROM issues
                WHERE COALESCE(audit_status, 'pending') <> 'rejected'
                GROUP BY station_id
            ),
            inspection_latest AS (
                SELECT
                    station_id,
                    MAX(inspection_date) AS latest_inspection_date
                FROM inspections
                GROUP BY station_id
            )
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
                COALESCE(ic.pending_rectification_count, 0) AS pending_rectification_count,
                COALESCE(ic.pending_review_count, 0) AS pending_review_count,
                COALESCE(ic.closed_count, 0) AS closed_count,
                il.latest_inspection_date
            FROM stations s
            LEFT JOIN issue_counts ic ON ic.station_id = s.id
            LEFT JOIN inspection_latest il ON il.station_id = s.id
            WHERE s.longitude IS NOT NULL
              AND s.latitude IS NOT NULL
            ORDER BY s.id;
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


@app.route("/api/event-feed")
def get_event_feed():
    user_id = str(request.args.get("user_id", "")).strip()
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
        if not has_permission(cur, user, "view_station_map"):
            return jsonify({"success": False, "error": "当前账号无权查看站点地图动态。"}), 403

        cur.execute(
            """
            SELECT
                CONCAT('issue-create-', i.id) AS id,
                s.id AS "stationId",
                s.station_name AS "stationName",
                CONCAT(
                    '【',
                    t.table_name,
                    '】新增问题，规范ID：',
                    i.standard_id,
                    '，当前状态：',
                    CASE
                        WHEN TRIM(COALESCE(i.status, '')) IN ('已闭环', '已整改') THEN '已闭环'
                        WHEN TRIM(COALESCE(i.status, '')) = '未整改' THEN '待整改'
                        ELSE i.status
                    END,
                    '。'
                ) AS text,
                TO_CHAR(COALESCE(i.created_at, NOW()), 'HH24:MI') AS time,
                CASE
                    WHEN TRIM(COALESCE(i.status, '')) IN ('待整改', '未整改', '站经无法整改') THEN 'danger'
                    WHEN TRIM(COALESCE(i.status, '')) = '待复核' THEN 'warning'
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

        if not has_permission(cur, user, "view_training_materials"):
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
                    "can_edit": can_edit_training_material(cur, user, row),
                    "can_delete": can_delete_training_material(cur, user, row),
                }
            )

        return jsonify(
            {
                "success": True,
                "can_upload": can_upload_training_materials(cur, user),
                "can_delete_any": can_delete_any_training_material(cur, user),
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
        if not can_upload_training_materials(cur, user):
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
        if not can_upload_training_materials(cur, user):
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
        if not can_edit_training_material(cur, user, material):
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
        if not can_upload_training_materials(cur, user):
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
        if not can_delete_training_material(cur, user, material):
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

        if not can_view_checklist_originals(cur, user):
            return jsonify({"success": False, "error": "当前账号无权查看检查表原件库。"}), 403

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
                "can_manage": can_manage_checklist_originals(cur, user),
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

        if not can_manage_checklist_originals(cur, user):
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
        ensure_inspection_checklist_management_schema(cur)
        conn.commit()
        cur.execute(
            """
            SELECT
                id,
                table_code,
                table_name,
                checklist_mode,
                standard_id_base,
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

    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_inspection_checklist_management_schema(cur)
        conn.commit()
        if not table_id:
            return jsonify([])

        inspection_table = get_inspection_table_record(cur, table_id)
        if not inspection_table:
            return jsonify({"success": False, "error": "检查表不存在。"}), 404
        if not inspection_table["is_active"]:
            return jsonify({"success": False, "error": "检查表未启用。"}), 400

        return jsonify(
            [dict(field) for field in get_management_checklist_fields(cur, table_id, include_public=True)]
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/inspection-standard-export-template", methods=["GET"])
def get_inspection_standard_export_template():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_inspection_checklist_management_schema(cur)
        conn.commit()

        user = getattr(g, "current_user", None)
        if not (can_view_inspection_standards(cur, user) or has_permission(cur, user, "submit_inspections")):
            return jsonify({"success": False, "error": "当前账号无权访问巡检规范库。"}), 403

        template = get_standard_export_template_config(cur)
        response = jsonify(
            {
                "success": True,
                "has_saved": template["has_saved"],
                "tables": template["tables"],
            }
        )
        response.headers["Cache-Control"] = "no-store"
        return response
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/inspection-standard-export-template", methods=["PUT"])
def update_inspection_standard_export_template():
    data = request.get_json(silent=True) or {}
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_inspection_checklist_management_schema(cur)

        user = getattr(g, "current_user", None)
        if not can_view_inspection_standards(cur, user):
            return jsonify({"success": False, "error": "当前账号无权访问巡检规范库。"}), 403

        normalized = save_standard_export_template_config(cur, data.get("tables") or {})
        conn.commit()
        return jsonify(
            {
                "success": True,
                "message": "导出规范公共模板已保存。",
                "has_saved": True,
                "tables": normalized,
            }
        )
    except Exception as e:
        if conn:
            conn.rollback()
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
        ensure_inspection_checklist_management_schema(cur)
        conn.commit()

        inspection_table = get_inspection_table_record(cur, table_id)
        if not inspection_table:
            return jsonify({"success": False, "error": "检查表不存在。"}), 404

        if not inspection_table["is_active"]:
            return jsonify({"success": False, "error": "检查表未启用。"}), 400

        physical_table_name = get_physical_table_name_by_code(
            inspection_table["table_code"]
        )
        fields = [dict(field) for field in get_management_checklist_fields(cur, inspection_table["id"], include_public=True)]
        field_meta = [(field["field_key"], field["field_label"]) for field in fields]
        register_field_meta = build_register_display_field_meta(fields)
        if not physical_table_name or not checklist_physical_table_exists(cur, physical_table_name):
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
            item = serialize_standard_row(field_meta, row, register_field_meta)
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

        internal_links = fetch_internal_links_by_external_ids(
            cur,
            [item["standard_id"] for item in result],
        )
        for item in result:
            linked_internal = internal_links.get(int(item["standard_id"]))
            item["linked_internal"] = linked_internal
            item["linked_internal_standard_id"] = (
                linked_internal.get("internal_standard_id") if linked_internal else ""
            )

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

        user = get_user_by_id(cur, user_id) if user_id else None
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404
        if not has_permission(cur, user, "view_inspection_plans"):
            return jsonify({"success": False, "error": "当前账号无权查看巡检计划。"}), 403

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


@app.route("/api/external-standards", methods=["GET"])
def get_external_standards():
    keyword = str(request.args.get("keyword", "")).strip().lower()
    table_id = str(request.args.get("table_id", "")).strip()
    conn = None
    cur = None
    try:
        user = get_current_request_user()
        conn = get_db_connection()
        cur = conn.cursor()
        if not (
            can_view_checklist_originals(cur, user)
            or can_view_inspection_standards(cur, user)
            or has_permission(cur, user, "submit_inspections")
            or has_permission(cur, user, "manage_internal_standards")
        ):
            return jsonify({"success": False, "error": "当前账号无权查看规范库。"}), 403

        external_map = fetch_external_standard_map(cur)
        conn.commit()
        internal_links = fetch_internal_links_by_external_ids(cur, external_map.keys())
        items = []
        for item in external_map.values():
            if table_id and str(item.get("inspection_table_id")) != table_id:
                continue
            haystack = "\n".join(
                [
                    str(item.get("external_standard_id") or ""),
                    str(item.get("inspection_table_name") or ""),
                    str(item.get("standard_detail_text") or ""),
                ]
            ).lower()
            if keyword and keyword not in haystack:
                continue
            linked_internal = internal_links.get(int(item["external_standard_id"]))
            items.append(
                {
                    **item,
                    "linked_internal": linked_internal,
                    "linked_internal_standard_id": linked_internal.get("internal_standard_id") if linked_internal else "",
                }
            )
        return jsonify({"success": True, "items": items})
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 401
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/inspection-internal-standards", methods=["GET"])
def get_inspection_internal_standards():
    keyword = str(request.args.get("keyword", "")).strip().lower()
    conn = None
    cur = None
    try:
        user = get_current_request_user()
        conn = get_db_connection()
        cur = conn.cursor()
        if not can_view_inspection_standards(cur, user):
            return jsonify({"success": False, "error": "当前账号无权访问巡检规范库。"}), 403

        cur.execute(
            """
            SELECT
                id,
                internal_standard_id,
                path_values,
                field_values,
                content,
                notes,
                is_active,
                TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI') AS created_at,
                TO_CHAR(updated_at, 'YYYY-MM-DD HH24:MI') AS updated_at
            FROM inspection_internal_standards
            WHERE is_active = TRUE
            ORDER BY internal_standard_id ASC;
            """
        )
        rows = cur.fetchall()
        fields = [dict(field) for field in get_internal_standard_fields(cur)]
        conn.commit()
        link_map = fetch_internal_standard_links(cur, [row["id"] for row in rows])
        items = []
        for row in rows:
            item = serialize_internal_standard(row, link_map.get(row["id"], []), fields)
            haystack = "\n".join(
                [
                    item["internal_standard_id"],
                    " ".join(str(value or "") for value in item["field_values"].values()),
                    item["content"],
                    " ".join(str(link.get("external_standard_id") or "") for link in item["linked_externals"]),
                ]
            ).lower()
            if keyword and keyword not in haystack:
                continue
            items.append(item)
        return jsonify({"success": True, "fields": fields, "items": items})
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 401
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/inspection-standard-usage-mode", methods=["GET"])
def get_public_inspection_standard_usage_mode():
    conn = None
    cur = None
    try:
        user = get_current_request_user()
        conn = get_db_connection()
        cur = conn.cursor()
        if not has_permission(cur, user, "submit_inspections"):
            return jsonify({"success": False, "error": "当前账号无权使用巡检登记功能。"}), 403
        return jsonify(
            {
                "success": True,
                "usage_mode": get_inspection_standard_usage_mode(cur),
            }
        )
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 401
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/internal-standards", methods=["GET"])
def get_management_internal_standards():
    user_id = str(request.args.get("user_id", "")).strip()
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        require_management_user(cur, user_id, "manage_internal_standards")
        cur.execute(
            """
            SELECT
                id,
                internal_standard_id,
                path_values,
                field_values,
                content,
                notes,
                is_active,
                TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI') AS created_at,
                TO_CHAR(updated_at, 'YYYY-MM-DD HH24:MI') AS updated_at
            FROM inspection_internal_standards
            ORDER BY internal_standard_id ASC;
            """
        )
        rows = cur.fetchall()
        fields = [dict(field) for field in get_internal_standard_fields(cur)]
        conn.commit()
        link_map = fetch_internal_standard_links(cur, [row["id"] for row in rows])
        usage_mode = get_inspection_standard_usage_mode(cur)
        return jsonify(
            {
                "success": True,
                "usage_mode": usage_mode,
                "fields": fields,
                "items": [
                    serialize_internal_standard(row, link_map.get(row["id"], []), fields)
                    for row in rows
                ],
            }
        )
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/internal-standards/usage-mode", methods=["GET"])
def get_management_internal_standard_usage_mode():
    user_id = str(request.args.get("user_id", "")).strip()
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        require_management_user(cur, user_id, "manage_internal_standards")
        return jsonify(
            {
                "success": True,
                "usage_mode": get_inspection_standard_usage_mode(cur),
            }
        )
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/internal-standards/usage-mode", methods=["PUT"])
def update_management_internal_standard_usage_mode():
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    mode = str(data.get("mode", "")).strip()
    conn = None
    cur = None
    try:
        if mode not in INSPECTION_STANDARD_USAGE_MODES:
            return jsonify({"success": False, "error": "巡检登记规范来源参数不合法。"}), 400
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_inspection_standard_usage_settings_schema(cur)
        conn.commit()
        require_management_user(cur, user_id, "manage_internal_standards")
        usage_mode = save_inspection_standard_usage_mode(cur, mode, user_id)
        conn.commit()
        return jsonify(
            {
                "success": True,
                "message": f"巡检登记已切换为使用{usage_mode['mode_label']}。",
                "usage_mode": usage_mode,
            }
        )
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/internal-standards/fields", methods=["GET"])
def get_management_internal_standard_fields():
    user_id = str(request.args.get("user_id", "")).strip()
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        require_management_user(cur, user_id, "manage_internal_standards")
        return jsonify(
            {
                "success": True,
                "fields": [dict(field) for field in get_internal_standard_fields(cur)],
            }
        )
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/internal-standards/fields", methods=["PUT"])
def update_management_internal_standard_fields():
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    conn = None
    cur = None
    try:
        fields = normalize_internal_standard_field_rows(data.get("fields") or [], allow_empty=True)
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_internal_standard_schema(cur)
        conn.commit()
        require_management_user(cur, user_id, "manage_internal_standards")
        upsert_internal_standard_fields(cur, fields)
        conn.commit()
        return jsonify(
            {
                "success": True,
                "message": "内部规范字段配置已保存。",
                "fields": [dict(field) for field in get_internal_standard_fields(cur)],
            }
        )
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        if getattr(e, "pgcode", "") == "23505":
            return jsonify({"success": False, "error": "内部规范字段名称或系统标识已存在。"}), 400
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/internal-standards", methods=["POST"])
def create_management_internal_standard():
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    conn = None
    cur = None
    try:
        links = normalize_external_link_rows(data.get("external_links") or [])

        conn = get_db_connection()
        cur = conn.cursor()
        ensure_inspection_checklist_management_schema(cur)
        ensure_internal_standard_schema(cur)
        conn.commit()
        require_management_user(cur, user_id, "manage_internal_standards")
        fields = [dict(field) for field in get_internal_standard_fields(cur)]
        field_values = normalize_internal_field_values(data.get("field_values") or {}, fields)
        path_values = build_internal_path_values_from_field_values(fields, field_values)
        content = build_internal_standard_summary(fields, field_values)
        internal_standard_id = generate_internal_standard_id(cur, field_values[fields[0]["field_key"]])
        cur.execute(
            """
            INSERT INTO inspection_internal_standards (
                internal_standard_id,
                path_values,
                field_values,
                content,
                notes,
                is_active,
                created_at,
                updated_at
            )
            VALUES (%s, %s::jsonb, %s::jsonb, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id;
            """,
            (
                internal_standard_id,
                json.dumps(path_values, ensure_ascii=False),
                json.dumps(field_values, ensure_ascii=False),
                content,
                "",
                bool(data.get("is_active", True)),
            ),
        )
        row = cur.fetchone()
        replace_internal_standard_links(cur, row["id"], links)
        conn.commit()
        return jsonify(
            {
                "success": True,
                "message": f"内部规范已创建，系统生成内部规范ID {internal_standard_id}。",
                "id": row["id"],
                "internal_standard_id": internal_standard_id,
            }
        )
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except (LookupError, ValueError) as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/internal-standards/<int:standard_id>", methods=["PUT"])
def update_management_internal_standard(standard_id):
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    conn = None
    cur = None
    try:
        links = normalize_external_link_rows(data.get("external_links") or [])

        conn = get_db_connection()
        cur = conn.cursor()
        ensure_inspection_checklist_management_schema(cur)
        ensure_internal_standard_schema(cur)
        conn.commit()
        require_management_user(cur, user_id, "manage_internal_standards")
        fields = [dict(field) for field in get_internal_standard_fields(cur)]
        field_values = normalize_internal_field_values(data.get("field_values") or {}, fields)
        path_values = build_internal_path_values_from_field_values(fields, field_values)
        content = build_internal_standard_summary(fields, field_values)
        cur.execute(
            "SELECT id, internal_standard_id FROM inspection_internal_standards WHERE id = %s LIMIT 1;",
            (standard_id,),
        )
        existing_standard = cur.fetchone()
        if not existing_standard:
            return jsonify({"success": False, "error": "内部规范不存在。"}), 404
        cur.execute(
            """
            UPDATE inspection_internal_standards
            SET path_values = %s::jsonb,
                field_values = %s::jsonb,
                content = %s,
                notes = %s,
                is_active = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
            """,
            (
                json.dumps(path_values, ensure_ascii=False),
                json.dumps(field_values, ensure_ascii=False),
                content,
                "",
                bool(data.get("is_active", True)),
                standard_id,
            ),
        )
        replace_internal_standard_links(cur, standard_id, links)
        sync_referenced_internal_standard_detail_text(
            cur,
            existing_standard["internal_standard_id"],
            content,
        )
        conn.commit()
        return jsonify({"success": True, "message": "内部规范已保存。"})
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except (LookupError, ValueError) as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/internal-standards/<int:standard_id>", methods=["DELETE"])
def delete_management_internal_standard(standard_id):
    user_id = str(request.args.get("user_id", "") or (request.get_json(silent=True) or {}).get("user_id", "")).strip()
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_internal_standard_schema(cur)
        conn.commit()
        require_management_user(cur, user_id, "manage_internal_standards")
        cur.execute(
            "DELETE FROM inspection_internal_standards WHERE id = %s RETURNING internal_standard_id;",
            (standard_id,),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"success": False, "error": "内部规范不存在。"}), 404
        conn.commit()
        return jsonify({"success": True, "message": f"内部规范 {row['internal_standard_id']} 已删除。"})
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/internal-standards/export", methods=["GET"])
def export_management_internal_standards():
    user_id = str(request.args.get("user_id", "")).strip()
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_inspection_checklist_management_schema(cur)
        ensure_internal_standard_schema(cur)
        conn.commit()
        require_management_user(cur, user_id, "manage_internal_standards")
        cur.execute(
            """
            SELECT
                id,
                internal_standard_id,
                path_values,
                field_values,
                content,
                notes,
                is_active,
                TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI') AS created_at,
                TO_CHAR(updated_at, 'YYYY-MM-DD HH24:MI') AS updated_at
            FROM inspection_internal_standards
            ORDER BY internal_standard_id ASC;
            """
        )
        rows = cur.fetchall()
        fields = [dict(field) for field in get_internal_standard_fields(cur)]
        link_map = fetch_internal_standard_links(cur, [row["id"] for row in rows])
        standards = []
        for row in rows:
            item = serialize_internal_standard(row, link_map.get(row["id"], []), fields)
            standards.append(
                {
                    "internal_standard_id": item["internal_standard_id"],
                    "field_values": item["field_values"],
                    "is_active": item["is_active"],
                    "external_links": [
                        {
                            "external_standard_id": link["external_standard_id"],
                            "external_inspection_table_id": link.get("external_inspection_table_id"),
                        }
                        for link in item["linked_externals"]
                    ],
                }
            )

        now = beijing_now()
        response = jsonify(
            {
                "backup_type": "ywddzx_internal_standards",
                "version": 2,
                "exported_at": now.isoformat(),
                "fields": fields,
                "standards": standards,
            }
        )
        filename = f"ywddzx_internal_standards_backup_{now.strftime('%Y%m%d_%H%M%S')}.json"
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        response.headers["Cache-Control"] = "no-store"
        return response
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/internal-standards/import", methods=["POST"])
def import_management_internal_standards():
    user_id = str(request.form.get("user_id", "")).strip()
    file_storage = request.files.get("file")
    conn = None
    cur = None
    try:
        backup_data = parse_internal_standards_backup_file(file_storage)
        fields = backup_data["fields"]
        standards = backup_data["standards"]
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_inspection_checklist_management_schema(cur)
        ensure_internal_standard_schema(cur)
        conn.commit()
        require_management_user(cur, user_id, "manage_internal_standards")

        external_ids = [
            link["external_standard_id"]
            for item in standards
            for link in item["external_links"]
        ]
        external_map = fetch_external_standard_map(cur, external_ids)
        for external_id in external_ids:
            if int(external_id) not in external_map:
                raise ValueError(f"外部规范ID【{external_id}】不存在，无法导入。")

        cur.execute("DELETE FROM inspection_internal_standards;")
        upsert_internal_standard_fields(cur, fields)
        for item in standards:
            cur.execute(
                """
                INSERT INTO inspection_internal_standards (
                    internal_standard_id,
                    path_values,
                    field_values,
                    content,
                    notes,
                    is_active,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s::jsonb, %s::jsonb, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                RETURNING id;
                """,
                (
                    item["internal_standard_id"],
                    json.dumps(item["path_values"], ensure_ascii=False),
                    json.dumps(item["field_values"], ensure_ascii=False),
                    item["content"],
                    "",
                    item["is_active"],
                ),
            )
            row = cur.fetchone()
            replace_internal_standard_links(cur, row["id"], item["external_links"])
            sync_referenced_internal_standard_detail_text(
                cur,
                item["internal_standard_id"],
                item["content"],
            )

        conn.commit()
        return jsonify(
            {
                "success": True,
                "message": f"巡检规范库备份已导入，共恢复 {len(standards)} 条内部规范。",
            }
        )
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/inspection-standards/ai-recommend", methods=["POST"])
def recommend_inspection_standard_by_ai():
    data = request.get_json(silent=True) or {}
    description = str(data.get("description") or "").strip()

    if len(description) < 4:
        return jsonify({"success": False, "error": "请先填写更具体的实际问题描述。"}), 400

    conn = None
    cur = None
    try:
        current_user = get_current_request_user()
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_inspection_checklist_management_schema(cur)
        ensure_internal_standard_schema(cur)
        conn.commit()

        if not has_permission(cur, current_user, "submit_inspections"):
            return jsonify({"success": False, "error": "当前账号无权使用巡检登记功能。"}), 403

        usage_mode = get_inspection_standard_usage_mode(cur)
        ai_catalog, full_standards = build_inspection_standard_ai_catalog(cur, usage_mode["mode"])
        conn.commit()

        recommendation_result = generate_standard_recommendations(
            description,
            ai_catalog,
        )
        record_ai_usage_log(
            cur,
            current_user,
            recommendation_result,
            "巡检登记",
            "AI引用规范",
            description[:200],
        )
        conn.commit()
        standard_map = {
            str(item.get("standard_id")): item
            for item in full_standards
            if item.get("standard_id") is not None
        }
        items = []
        for recommendation in recommendation_result.get("recommendations") or []:
            standard = standard_map.get(str(recommendation.get("standard_id") or ""))
            if not standard:
                continue
            items.append(
                {
                    **standard,
                    "confidence": recommendation.get("confidence") or "中",
                    "reason": recommendation.get("reason") or "",
                }
            )

        no_related = bool(recommendation_result.get("no_related")) or not items
        return jsonify(
            {
                "success": True,
                "ai_generated": bool(recommendation_result.get("generated")),
                "message": recommendation_result.get("message") or "",
                "summary": recommendation_result.get("summary") or "",
                "no_related": no_related,
                "items": [] if no_related else items,
                "catalog_count": len(ai_catalog),
                "usage_mode": usage_mode,
            }
        )
    except PermissionError as e:
        return jsonify({"success": False, "error": str(e)}), 401
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/inspection-register", methods=["POST"])
def inspection_register():
    inspector_id = get_authenticated_request_user_id(request.form.get("inspector_id"))
    station_id = str(request.form.get("station_id", "")).strip()
    inspection_table_id = str(request.form.get("inspection_table_id", "")).strip()
    has_issue = str(request.form.get("has_issue", "yes")).strip().lower()
    standard_id = str(request.form.get("standard_id", "")).strip()
    internal_standard_id = str(request.form.get("internal_standard_id", "")).strip().upper()
    description = str(request.form.get("description", "")).strip()
    photo = request.files.get("photo")

    if not inspector_id:
        return jsonify({"success": False, "error": "缺少巡检人信息。"}), 400

    if not station_id:
        return jsonify({"success": False, "error": "请选择站点名称。"}), 400

    if has_issue != "yes" and not inspection_table_id:
        return jsonify({"success": False, "error": "请选择检查表。"}), 400

    if has_issue not in {"yes", "no"}:
        return jsonify({"success": False, "error": "是否发现问题参数不合法。"}), 400

    if has_issue == "yes" and not standard_id and not internal_standard_id:
        return jsonify({"success": False, "error": "请选择规范。"}), 400

    if has_issue == "yes" and standard_id and not internal_standard_id and not inspection_table_id:
        return jsonify({"success": False, "error": "请选择检查表。"}), 400

    if has_issue == "yes" and not description:
        return jsonify({"success": False, "error": "请填写实际问题描述。"}), 400

    if has_issue == "yes" and (not photo or not photo.filename):
        return jsonify({"success": False, "error": "请上传问题照片。"}), 400

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_inspection_checklist_management_schema(cur)
        ensure_internal_standard_schema(cur)
        ensure_issue_inspector_schema(cur)
        ensure_inspection_completion_schema(cur)
        auto_complete_overdue_inspections(cur)
        conn.commit()

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

        if not has_permission(cur, inspector, "submit_inspections"):
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

        today = beijing_today()
        batch_id = get_or_create_inspection_batch(cur, station_id, inspector_id, today)
        usage_mode = get_inspection_standard_usage_mode(cur)

        if has_issue == "yes" and usage_mode["mode"] == "external" and internal_standard_id:
            return jsonify({"success": False, "error": "当前巡检登记已切换为外部规范库，请选择外部规范ID后提交。"}), 400

        if has_issue == "yes" and usage_mode["mode"] == "internal" and standard_id and not internal_standard_id:
            return jsonify({"success": False, "error": "当前巡检登记已切换为内部规范库，请选择内部规范ID后提交。"}), 400

        if has_issue == "yes" and internal_standard_id:
            internal_standard, _internal_fields, linked_externals = fetch_internal_standard_by_code(
                cur,
                internal_standard_id,
            )
            if not internal_standard:
                return jsonify({"success": False, "error": "所选内部规范不存在或未启用。"}), 404
            if not linked_externals:
                return jsonify({"success": False, "error": "所选内部规范尚未挂载外部规范，不能登记问题。"}), 400

            external_map = fetch_external_standard_map(
                cur,
                [link["external_standard_id"] for link in linked_externals],
            )
            external_standards = []
            for link in linked_externals:
                external = external_map.get(int(link["external_standard_id"]))
                if not external:
                    return jsonify(
                        {
                            "success": False,
                            "error": f"内部规范挂载的外部规范ID【{link['external_standard_id']}】不存在。",
                        }
                    ), 400
                external_standards.append(external)

            targets = prepare_issue_registration_targets(
                cur,
                station_id,
                inspector_id,
                external_standards,
                batch_id,
                today,
            )
            photo_path = save_uploaded_file(photo, "issues")
            inspection_id_by_table = {}
            created_issue_ids = []
            internal_detail_text = internal_standard.get("content") or ""

            for target in targets:
                table_key = str(target["inspection_table_id"])
                inspection_id = target["inspection_id"] or inspection_id_by_table.get(table_key)
                if not inspection_id:
                    inspection_id = create_inspection_record(
                        cur,
                        station_id,
                        inspector_id,
                        target["inspection_table_id"],
                        batch_id,
                    )
                    inspection_id_by_table[table_key] = inspection_id

                cur.execute(
                    """
                    INSERT INTO issues (
                        inspection_id,
                        inspector_id,
                        station_id,
                        inspection_table_id,
                        standard_id,
                        standard_detail_text,
                        internal_standard_id,
                        internal_standard_detail_text,
                        description,
                        photo_path,
                        status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (
                        inspection_id,
                        inspector_id,
                        station_id,
                        target["inspection_table_id"],
                        target["standard_id"],
                        target["standard_detail_text"],
                        internal_standard["internal_standard_id"],
                        internal_detail_text,
                        description,
                        photo_path,
                        "待整改",
                    ),
                )
                created_issue_ids.append(cur.fetchone()["id"])
                mark_related_plan_items_completed(
                    cur,
                    station_id,
                    target["inspection_table_id"],
                    inspection_id,
                    today,
                )

            conn.commit()
            return jsonify(
                {
                    "success": True,
                    "message": f"巡检问题登记成功，已按内部规范生成 {len(created_issue_ids)} 条外部规范问题。",
                    "inspection_id": next(iter(inspection_id_by_table.values()), targets[0]["inspection_id"]),
                    "issue_id": created_issue_ids[0] if created_issue_ids else None,
                    "issue_ids": created_issue_ids,
                }
            )

        inspection_table = get_inspection_table_record(cur, inspection_table_id)
        if not inspection_table:
            return jsonify({"success": False, "error": "检查表不存在。"}), 404

        if not inspection_table["is_active"]:
            return jsonify({"success": False, "error": "检查表未启用。"}), 400

        physical_table_name = get_physical_table_name_by_code(
            inspection_table["table_code"]
        )
        fields = [dict(field) for field in get_management_checklist_fields(cur, inspection_table["id"], include_public=True)]
        field_meta = [(field["field_key"], field["field_label"]) for field in fields]
        if not physical_table_name or not checklist_physical_table_exists(cur, physical_table_name):
            return jsonify({"success": False, "error": "检查表未配置物理表映射。"}), 400
        ensure_checklist_field_columns(cur, physical_table_name, fields)

        today = beijing_today()

        inspection_id = get_or_create_period_inspection(
            cur,
            station_id,
            inspector_id,
            inspection_table_id,
            today,
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

        linked_internal = fetch_internal_links_by_external_ids(cur, [standard_id]).get(int(standard_id))
        linked_internal_standard_id = linked_internal.get("internal_standard_id") if linked_internal else None
        linked_internal_detail_text = linked_internal.get("content") if linked_internal else None
        photo_path = save_uploaded_file(photo, "issues")

        cur.execute(
            """
            INSERT INTO issues (
                inspection_id,
                inspector_id,
                station_id,
                inspection_table_id,
                standard_id,
                standard_detail_text,
                internal_standard_id,
                internal_standard_detail_text,
                description,
                photo_path,
                status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (
                inspection_id,
                inspector_id,
                station_id,
                inspection_table_id,
                standard_id,
                standard_detail_text,
                linked_internal_standard_id,
                linked_internal_detail_text,
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
    except ValueError as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 400
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
        ensure_issue_inspector_schema(cur)
        ensure_inspection_completion_schema(cur)
        sync_signed_inspections_completion(cur)
        auto_complete_overdue_inspections(cur)
        conn.commit()

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

        if is_station_manager(user):
            if not user["station_id"]:
                return jsonify([])

            cur.execute(
                """
                SELECT
                    i.id,
                    i.station_id,
                    COALESCE(i.inspector_id, ins.inspector_id) AS inspector_id,
                    TO_CHAR(i.created_at, 'YYYY-MM') AS month,
                    TO_CHAR(i.created_at, 'YYYY-MM-DD HH24:MI') AS time,
                    s.region,
                    s.station_name AS station,
                    t.table_name AS inspection_table_name,
                    i.standard_id,
                    i.standard_detail_text,
                    i.internal_standard_id,
                    i.internal_standard_detail_text,
                    i.description,
                    i.photo_path AS issue_photo,
                    i.rectification_result,
                    i.rectification_note,
                    i.rectification_photo_path AS rectification_photo,
                    i.review_result,
                    i.review_note,
                    i.review_photo_path AS review_photo,
                    i.status,
                    COALESCE(i.audit_status, 'pending') AS audit_status,
                    COALESCE(i.is_excellent, FALSE) AS is_excellent,
                    i.audited_by,
                    TO_CHAR(i.audited_at, 'YYYY-MM-DD HH24:MI') AS audited_at,
                    ins.sign_status AS inspection_sign_status,
                    ins.station_manager_signed_name,
                    ins.station_manager_signature_path,
                    TO_CHAR(ins.station_manager_signed_at, 'YYYY-MM-DD HH24:MI') AS station_manager_signed_at,
                    ins.inspector_completion_status AS inspection_completion_status
                FROM issues i
                JOIN inspections ins ON i.inspection_id = ins.id
                JOIN stations s ON i.station_id = s.id
                JOIN inspection_tables t ON i.inspection_table_id = t.id
                WHERE i.station_id = %s
                  AND i.status = '待整改'
                  AND ins.sign_status = '已签名确认'
                  AND COALESCE(i.audit_status, 'pending') <> 'rejected'
                ORDER BY i.id DESC;
                """,
                (user["station_id"],),
            )
            rows = cur.fetchall()
            can_explicit_edit = can_edit_inspection_issues(cur, user)
            can_explicit_delete = can_delete_inspection_issues(cur, user)
            return jsonify(
                [
                    normalize_issue_row_for_response(
                        row, user, can_explicit_edit, can_explicit_delete
                    )
                    for row in rows
                ]
            )

        if is_root_user(user) or user.get("role") == "supervisor":
            cur.execute(
                """
                SELECT
                    i.id,
                    i.station_id,
                    COALESCE(i.inspector_id, ins.inspector_id) AS inspector_id,
                    TO_CHAR(i.created_at, 'YYYY-MM') AS month,
                    TO_CHAR(i.created_at, 'YYYY-MM-DD HH24:MI') AS time,
                    s.region,
                    s.station_name AS station,
                    t.table_name AS inspection_table_name,
                    i.standard_id,
                    i.standard_detail_text,
                    i.internal_standard_id,
                    i.internal_standard_detail_text,
                    i.description,
                    i.photo_path AS issue_photo,
                    i.rectification_result,
                    i.rectification_note,
                    i.rectification_photo_path AS rectification_photo,
                    i.review_result,
                    i.review_note,
                    i.review_photo_path AS review_photo,
                    i.status,
                    COALESCE(i.audit_status, 'pending') AS audit_status,
                    COALESCE(i.is_excellent, FALSE) AS is_excellent,
                    i.audited_by,
                    TO_CHAR(i.audited_at, 'YYYY-MM-DD HH24:MI') AS audited_at,
                    ins.sign_status AS inspection_sign_status,
                    ins.inspector_completion_status AS inspection_completion_status
                FROM issues i
                JOIN inspections ins ON i.inspection_id = ins.id
                JOIN stations s ON i.station_id = s.id
                JOIN inspection_tables t ON i.inspection_table_id = t.id
                WHERE i.status = '待复核'
                  AND COALESCE(i.audit_status, 'pending') <> 'rejected'
                ORDER BY i.id DESC;
                """
            )
            rows = cur.fetchall()
            can_explicit_edit = can_edit_inspection_issues(cur, user)
            can_explicit_delete = can_delete_inspection_issues(cur, user)
            return jsonify(
                [
                    normalize_issue_row_for_response(
                        row, user, can_explicit_edit, can_explicit_delete
                    )
                    for row in rows
                ]
            )

        return jsonify([])
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/my-issues/pending-rectification-count", methods=["GET"])
def get_my_pending_rectification_count():
    current_user = get_current_request_user()
    if not is_station_manager(current_user) or not current_user.get("station_id"):
        return jsonify({"success": True, "pending_count": 0})

    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_issue_inspector_schema(cur)
        ensure_inspection_completion_schema(cur)
        cur.execute(
            """
            SELECT COUNT(*) AS pending_count
            FROM issues i
            JOIN inspections ins ON i.inspection_id = ins.id
            WHERE i.station_id = %s
              AND i.status = '待整改'
              AND ins.sign_status = '已签名确认'
              AND COALESCE(i.audit_status, 'pending') <> 'rejected';
            """,
            (current_user["station_id"],),
        )
        row = cur.fetchone()
        conn.commit()
        return jsonify({"success": True, "pending_count": int(row["pending_count"] or 0)})
    except Exception as e:
        if conn:
            conn.rollback()
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
        ensure_issue_inspector_schema(cur)
        ensure_inspection_completion_schema(cur)
        auto_complete_overdue_inspections(cur)
        conn.commit()

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

        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        can_view_all = can_view_all_inspection_issues(cur, user)
        can_view_own = can_view_own_inspection_issues(cur, user)
        if can_view_all:
            pass
        elif can_view_own:
            if not user["station_id"]:
                where_clause = "WHERE COALESCE(i.inspector_id, ins.inspector_id) = %s"
                params.append(user["id"])
            else:
                where_clause = "WHERE i.station_id = %s OR COALESCE(i.inspector_id, ins.inspector_id) = %s"
                params.extend([user["station_id"], user["id"]])
        else:
            where_clause = "WHERE COALESCE(i.inspector_id, ins.inspector_id) = %s"
            params.append(user["id"])

        can_explicit_edit = can_edit_inspection_issues(cur, user)
        can_explicit_delete = can_delete_inspection_issues(cur, user)
        can_explicit_audit = can_audit_inspection_issues(cur, user)

        cur.execute(
            sql.SQL(
                """
                SELECT
                    i.id,
                    i.station_id,
                    COALESCE(i.inspector_id, ins.inspector_id) AS inspector_id,
                    TO_CHAR(i.created_at, 'YYYY-MM') AS month,
                    TO_CHAR(i.created_at, 'YYYY-MM-DD HH24:MI') AS time,
                    s.region,
                    s.station_name AS station,
                    s.station_manager_name AS station_manager,
                    s.station_manager_phone AS station_manager_phone,
                    issue_inspector.real_name AS inspector,
                    issue_inspector.phone AS inspector_phone,
                    t.table_name AS inspection_table_name,
                    i.standard_id,
                    i.standard_detail_text,
                    i.internal_standard_id,
                    i.internal_standard_detail_text,
                    i.description,
                    i.photo_path AS issue_photo,
                    i.rectification_result,
                    i.rectification_note,
                    i.rectification_photo_path AS rectification_photo,
                    i.review_result,
                    i.review_note,
                    i.review_photo_path AS review_photo,
                    i.status,
                    COALESCE(i.audit_status, 'pending') AS audit_status,
                    COALESCE(i.is_excellent, FALSE) AS is_excellent,
                    i.audited_by,
                    audit_user.real_name AS audited_by_name,
                    TO_CHAR(i.audited_at, 'YYYY-MM-DD HH24:MI') AS audited_at,
                    ins.sign_status AS inspection_sign_status,
                    ins.station_manager_signed_name,
                    ins.station_manager_signature_path,
                    TO_CHAR(ins.station_manager_signed_at, 'YYYY-MM-DD HH24:MI') AS station_manager_signed_at,
                    ins.inspector_completion_status AS inspection_completion_status
                FROM issues i
                JOIN inspections ins ON i.inspection_id = ins.id
                JOIN stations s ON i.station_id = s.id
                JOIN inspection_tables t ON i.inspection_table_id = t.id
                JOIN users issue_inspector ON COALESCE(i.inspector_id, ins.inspector_id) = issue_inspector.id
                LEFT JOIN users audit_user ON audit_user.id = i.audited_by
                {where_clause}
                ORDER BY i.id DESC;
                """
            ).format(where_clause=sql.SQL(where_clause)),
            params,
        )
        rows = cur.fetchall()
        conn.commit()
        return jsonify(
            [
                normalize_issue_row_for_response(
                    row, user, can_explicit_edit, can_explicit_delete, can_explicit_audit
                )
                for row in rows
            ]
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/issues/<int:issue_id>/audit", methods=["POST"])
def audit_issue(issue_id):
    data = request.get_json(silent=True) or {}
    user_id = get_authenticated_request_user_id(data.get("user_id"))
    action = str(data.get("action") or "").strip().lower()
    status_map = {
        "approve": "approved",
        "approved": "approved",
        "reject": "rejected",
        "rejected": "rejected",
        "reset": "pending",
        "pending": "pending",
    }
    audit_status = status_map.get(action)
    if not audit_status:
        return jsonify({"success": False, "error": "审核操作不正确。"}), 400

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_issue_inspector_schema(cur)
        ensure_inspection_completion_schema(cur)
        user = get_user_by_id(cur, user_id)
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404
        if not can_audit_inspection_issues(cur, user):
            return jsonify({"success": False, "error": "当前账号无权审核巡检问题。"}), 403

        cur.execute(
            """
            SELECT
                i.id,
                i.station_id,
                i.inspection_id,
                i.status,
                COALESCE(i.audit_status, 'pending') AS audit_status,
                ins.sign_status AS inspection_sign_status,
                ins.station_manager_signed_name,
                ins.station_manager_signature_path,
                ins.station_manager_signed_at,
                ins.inspector_completion_status AS inspection_completion_status
            FROM issues i
            JOIN inspections ins ON ins.id = i.inspection_id
            WHERE i.id = %s
            LIMIT 1;
            """,
            (issue_id,),
        )
        issue = cur.fetchone()
        if not issue:
            return jsonify({"success": False, "error": "巡检问题不存在。"}), 404
        if is_issue_inspection_signed(issue):
            return jsonify({"success": False, "error": "该问题所属检查表已完成站经理签字确认，不能继续审核。"}), 403

        can_view_all = can_view_all_inspection_issues(cur, user)
        can_view_own = can_view_own_inspection_issues(cur, user)
        if not can_view_all and not (
            can_view_own
            and user.get("station_id")
            and issue["station_id"] == user["station_id"]
        ):
            return jsonify({"success": False, "error": "当前账号无权操作该巡检问题。"}), 403

        if audit_status == "pending":
            cur.execute(
                """
                UPDATE issues
                SET audit_status = 'pending',
                    audited_by = NULL,
                    audited_at = NULL
                WHERE id = %s;
                """,
                (issue_id,),
            )
            message = "该问题已恢复为待审核。"
        else:
            cur.execute(
                """
                UPDATE issues
                SET audit_status = %s,
                    audited_by = %s,
                    audited_at = CURRENT_TIMESTAMP,
                    is_excellent = CASE WHEN %s = 'rejected' THEN FALSE ELSE is_excellent END
                WHERE id = %s;
                """,
                (audit_status, user["id"], audit_status, issue_id),
            )
            message = "该问题已审核通过。" if audit_status == "approved" else "该问题已审核否决，后续不参与记录统计和问题流转。"

        conn.commit()
        return jsonify(
            {
                "success": True,
                "message": message,
                "audit_status": audit_status,
                "audit_status_label": ISSUE_AUDIT_STATUS_LABELS.get(audit_status, "待审核"),
            }
        )
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/issues/<int:issue_id>/excellent", methods=["POST"])
def update_issue_excellent(issue_id):
    data = request.get_json(silent=True) or {}
    user_id = get_authenticated_request_user_id(data.get("user_id"))
    raw_is_excellent = data.get("is_excellent")
    if isinstance(raw_is_excellent, bool):
        is_excellent = raw_is_excellent
    else:
        is_excellent = str(raw_is_excellent).strip().lower() in {"1", "true", "yes", "on"}

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_issue_inspector_schema(cur)
        user = get_user_by_id(cur, user_id)
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404
        if not can_audit_inspection_issues(cur, user):
            return jsonify({"success": False, "error": "当前账号无权标记优秀问题。"}), 403

        cur.execute(
            """
            SELECT
                i.id,
                i.station_id,
                COALESCE(i.audit_status, 'pending') AS audit_status
            FROM issues i
            WHERE i.id = %s
            LIMIT 1;
            """,
            (issue_id,),
        )
        issue = cur.fetchone()
        if not issue:
            return jsonify({"success": False, "error": "巡检问题不存在。"}), 404

        if normalize_issue_audit_status(issue.get("audit_status")) == "rejected" and is_excellent:
            return jsonify({"success": False, "error": "审核否决的问题不能标记为优秀问题。"}), 400

        can_view_all = can_view_all_inspection_issues(cur, user)
        can_view_own = can_view_own_inspection_issues(cur, user)
        if not can_view_all and not (
            can_view_own
            and user.get("station_id")
            and issue["station_id"] == user["station_id"]
        ):
            return jsonify({"success": False, "error": "当前账号无权操作该巡检问题。"}), 403

        cur.execute(
            """
            UPDATE issues
            SET is_excellent = %s
            WHERE id = %s
            RETURNING COALESCE(is_excellent, FALSE) AS is_excellent;
            """,
            (is_excellent, issue_id),
        )
        updated = cur.fetchone()
        conn.commit()
        return jsonify(
            {
                "success": True,
                "message": "已点亮优秀问题。" if updated["is_excellent"] else "已取消优秀问题标记。",
                "is_excellent": bool(updated["is_excellent"]),
            }
        )
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/issues/export-tasks", methods=["POST"])
def create_issue_export_task():
    data = request.get_json(silent=True) or {}
    user_id = get_authenticated_request_user_id(data.get("user_id"))
    conn = None
    cur = None

    try:
        issue_ids = normalize_issue_export_ids(data.get("issue_ids"))
        filter_summary = normalize_issue_export_filter_summary(data.get("filter_summary"))
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_issue_export_schema(cur)
        cleanup_expired_issue_exports(cur)

        user = get_user_by_id(cur, user_id)
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        task_id = uuid.uuid4().hex
        now = beijing_now()
        download_filename = f"巡检问题列表_{now.strftime('%Y%m%d_%H%M%S')}_{task_id[:8]}.xlsx"
        cur.execute(
            """
            INSERT INTO issue_export_tasks (
                task_id,
                created_by,
                status,
                selected_count,
                exported_count,
                filter_summary,
                download_filename,
                expires_at
            )
            VALUES (%s, %s, 'pending', %s, 0, %s::jsonb, %s, CURRENT_TIMESTAMP + INTERVAL '7 days')
            RETURNING
                task_id,
                created_by,
                status,
                selected_count,
                exported_count,
                filter_summary,
                file_path,
                download_filename,
                error_message,
                TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI') AS created_at,
                TO_CHAR(updated_at, 'YYYY-MM-DD HH24:MI') AS updated_at,
                TO_CHAR(completed_at, 'YYYY-MM-DD HH24:MI') AS completed_at,
                TO_CHAR(expires_at, 'YYYY-MM-DD HH24:MI') AS expires_at;
            """,
            (
                task_id,
                user["id"],
                len(issue_ids),
                json.dumps(filter_summary, ensure_ascii=False),
                download_filename,
            ),
        )
        task = cur.fetchone()
        conn.commit()
        start_issue_export_task(task_id, issue_ids, user["id"])
        return jsonify(
            {
                "success": True,
                "message": "导出任务已提交，系统正在后台生成 Excel 文件。",
                "task": serialize_issue_export_task(task),
            }
        )
    except ValueError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except Exception as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/issues/export-tasks/<task_id>")
def get_issue_export_task(task_id):
    user_id = get_authenticated_request_user_id(request.args.get("user_id"))
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_issue_export_schema(cur)
        cleanup_expired_issue_exports(cur)
        user = get_user_by_id(cur, user_id)
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404
        task = get_issue_export_task_for_user(cur, task_id, user)
        conn.commit()
        return jsonify({"success": True, "task": serialize_issue_export_task(task)})
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except Exception as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/issues/export-tasks/<task_id>/download")
def download_issue_export_task(task_id):
    user_id = get_authenticated_request_user_id(request.args.get("user_id"))
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_issue_export_schema(cur)
        cleanup_expired_issue_exports(cur)
        user = get_user_by_id(cur, user_id)
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404
        task = get_issue_export_task_for_user(cur, task_id, user)
        conn.commit()

        if task["status"] != "completed":
            return jsonify({"success": False, "error": "导出文件尚未生成完成。"}), 400
        if not task.get("file_path"):
            return jsonify({"success": False, "error": "导出文件不存在或已过期。"}), 404

        abs_path = resolve_storage_abs_path(task["file_path"])
        if not abs_path or not os.path.isfile(abs_path):
            return jsonify({"success": False, "error": "导出文件不存在或已过期。"}), 404

        response = send_file(
            abs_path,
            as_attachment=True,
            download_name=task.get("download_filename") or f"inspection_issues_{task_id[:8]}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response.headers["Cache-Control"] = "no-store"
        return response
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except Exception as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/issues/<int:issue_id>", methods=["PUT"])
def update_issue(issue_id):
    data = request.form if request.form else (request.get_json(silent=True) or {})
    user_id = str(data.get("user_id", "")).strip()
    description = str(data.get("description", "")).strip()
    status = canonical_issue_status(data.get("status"))
    rectification_note = str(data.get("rectification_note", "")).strip() or None
    review_note = str(data.get("review_note", "")).strip() or None
    standard_id = str(data.get("standard_id", "")).strip()
    internal_standard_id = str(data.get("internal_standard_id", "")).strip().upper()
    target_inspector_id_param = str(data.get("target_inspector_id", "")).strip()
    issue_photo = request.files.get("issue_photo")

    if not user_id:
        return jsonify({"success": False, "error": "缺少用户信息。"}), 400

    if not description:
        return jsonify({"success": False, "error": "请填写问题描述。"}), 400

    if status not in ISSUE_STATUS_OPTIONS:
        return jsonify({"success": False, "error": "问题状态参数不合法。"}), 400

    try:
        rectification_result = normalize_optional_issue_result(
            data.get("rectification_result"), "站经理整改结果"
        )
        review_result = normalize_optional_issue_result(
            data.get("review_result"), "督导组复核结果"
        )
    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 400

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_issue_inspector_schema(cur)
        ensure_inspection_completion_schema(cur)

        user = get_user_by_id(cur, user_id)
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        cur.execute(
            """
            SELECT
                i.id,
                i.inspection_id,
                i.station_id,
                i.inspection_table_id,
                i.standard_id,
                i.standard_detail_text,
                i.internal_standard_id,
                i.internal_standard_detail_text,
                i.status,
                COALESCE(i.audit_status, 'pending') AS audit_status,
                i.rectification_result,
                COALESCE(i.inspector_id, ins.inspector_id) AS inspector_id,
                ins.inspection_date,
                ins.batch_id,
                ins.sign_status AS inspection_sign_status,
                ins.station_manager_signed_name,
                ins.station_manager_signature_path,
                ins.station_manager_signed_at,
                ins.inspector_completion_status AS inspection_completion_status
            FROM issues i
            JOIN inspections ins ON i.inspection_id = ins.id
            WHERE i.id = %s
            LIMIT 1;
            """,
            (issue_id,),
        )
        issue = cur.fetchone()

        if not issue:
            return jsonify({"success": False, "error": "巡检问题不存在。"}), 404

        if is_issue_inspection_signed(issue):
            return jsonify({"success": False, "error": "该问题所属检查表已完成站经理签字确认，不能继续编辑。"}), 403

        if is_closed_issue_status(issue["status"]) and not is_root_user(user):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "该问题已闭环，只有 root 账号可以编辑。",
                    }
                ),
                403,
            )

        can_explicit_edit = can_edit_inspection_issues(cur, user)
        creator_can_modify = can_user_use_creator_issue_controls(user, issue)
        if not can_explicit_edit and not creator_can_modify:
            return jsonify({"success": False, "error": "当前账号无权编辑巡检问题。"}), 403

        if creator_can_modify and not can_explicit_edit and not is_root_user(user):
            if (
                status != "待整改"
                or rectification_result
                or rectification_note
                or review_result
                or review_note
            ):
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "上传者只能在站点整改前修改问题描述和问题照片，不能调整流转状态或整改复核信息。",
                        }
                    ),
                    400,
                )

        can_view_all = can_view_all_inspection_issues(cur, user)
        can_view_own = can_view_own_inspection_issues(cur, user)
        if not can_view_all and not (
            can_view_own
            and user.get("station_id")
            and issue["station_id"] == user["station_id"]
        ) and not issue_created_by_user(user, issue):
            return jsonify({"success": False, "error": "当前账号无权操作该巡检问题。"}), 403

        target_inspector_id = int(issue["inspector_id"])
        if target_inspector_id_param:
            try:
                requested_inspector_id = int(target_inspector_id_param)
            except (TypeError, ValueError):
                return jsonify({"success": False, "error": "检查人参数不合法。"}), 400

            if requested_inspector_id != int(issue["inspector_id"]):
                if not can_change_issue_inspector(user):
                    return jsonify({"success": False, "error": "只有 root 账号可以修改问题检查人归属。"}), 403
                target_inspector = get_user_by_id(cur, requested_inspector_id)
                if not target_inspector:
                    return jsonify({"success": False, "error": "目标检查人不存在。"}), 404
                if not is_supervisor_like(target_inspector) and not has_permission(
                    cur, target_inspector, "submit_inspections"
                ):
                    return jsonify({"success": False, "error": "目标检查人必须具备巡检登记权限。"}), 400
                target_inspector_id = requested_inspector_id

        current_standard = {
            "inspection_table_id": int(issue["inspection_table_id"]),
            "standard_id": int(issue["standard_id"]),
            "standard_detail_text": issue.get("standard_detail_text") or "",
            "internal_standard_id": issue.get("internal_standard_id"),
            "internal_standard_detail_text": issue.get("internal_standard_detail_text"),
        }
        usage_mode = get_inspection_standard_usage_mode(cur)
        if usage_mode["mode"] == "internal":
            if internal_standard_id or issue.get("internal_standard_id"):
                target_standard = resolve_issue_standard_edit_target(
                    cur,
                    "internal",
                    internal_standard_id=internal_standard_id or issue.get("internal_standard_id"),
                    preferred_external_standard_id=issue.get("standard_id"),
                )
            else:
                target_standard = current_standard
        else:
            target_standard = resolve_issue_standard_edit_target(
                cur,
                "external",
                standard_id=standard_id or issue.get("standard_id"),
            )

        target_inspection_id = get_or_create_issue_edit_inspection(
            cur,
            issue,
            target_standard["inspection_table_id"],
            target_inspector_id,
        )
        old_inspection_id = int(issue["inspection_id"])
        new_photo_path = save_uploaded_file(issue_photo, "issues") if issue_photo and issue_photo.filename else None

        cur.execute(
            """
            UPDATE issues
            SET description = %s,
                inspector_id = %s,
                inspection_id = %s,
                inspection_table_id = %s,
                standard_id = %s,
                standard_detail_text = %s,
                internal_standard_id = %s,
                internal_standard_detail_text = %s,
                status = %s,
                rectification_result = %s,
                rectification_note = %s,
                review_result = %s,
                review_note = %s,
                photo_path = COALESCE(%s, photo_path)
            WHERE id = %s;
            """,
            (
                description,
                target_inspector_id,
                target_inspection_id,
                target_standard["inspection_table_id"],
                target_standard["standard_id"],
                target_standard["standard_detail_text"],
                target_standard.get("internal_standard_id"),
                target_standard.get("internal_standard_detail_text"),
                status,
                rectification_result,
                rectification_note,
                review_result,
                review_note,
                new_photo_path,
                issue_id,
            ),
        )
        mark_related_plan_items_completed(
            cur,
            issue["station_id"],
            target_standard["inspection_table_id"],
            target_inspection_id,
            issue["inspection_date"],
        )
        sync_inspection_primary_inspector(cur, target_inspection_id)
        if old_inspection_id != int(target_inspection_id):
            sync_inspection_primary_inspector(cur, old_inspection_id)
            cleanup_empty_inspection_after_issue_move(cur, old_inspection_id)

        conn.commit()
        return jsonify({"success": True, "message": "巡检问题已保存。"})
    except ValueError as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/issues/<int:issue_id>", methods=["DELETE"])
def delete_issue(issue_id):
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id") or request.args.get("user_id", "")).strip()

    if not user_id:
        return jsonify({"success": False, "error": "缺少用户信息。"}), 400

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_issue_inspector_schema(cur)
        ensure_inspection_completion_schema(cur)
        auto_complete_overdue_inspections(cur)
        conn.commit()

        user = get_user_by_id(cur, user_id)
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        cur.execute(
            """
            SELECT
                i.id,
                i.inspection_id,
                i.station_id,
                i.status,
                COALESCE(i.audit_status, 'pending') AS audit_status,
                i.rectification_result,
                COALESCE(i.inspector_id, ins.inspector_id) AS inspector_id,
                ins.sign_status AS inspection_sign_status,
                ins.station_manager_signed_name,
                ins.station_manager_signature_path,
                ins.station_manager_signed_at,
                ins.inspector_completion_status AS inspection_completion_status
            FROM issues i
            JOIN inspections ins ON i.inspection_id = ins.id
            WHERE i.id = %s
            LIMIT 1;
            """,
            (issue_id,),
        )
        issue = cur.fetchone()

        if not issue:
            return jsonify({"success": False, "error": "巡检问题不存在。"}), 404

        if is_issue_inspection_signed(issue):
            return jsonify({"success": False, "error": "该问题所属检查表已完成站经理签字确认，不能继续删除。"}), 403

        if is_closed_issue_status(issue["status"]) and not is_root_user(user):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "该问题已闭环，只有 root 账号可以删除。",
                    }
                ),
                403,
            )

        can_explicit_delete = can_delete_inspection_issues(cur, user)
        creator_can_modify = can_user_use_creator_issue_controls(user, issue)
        if not can_explicit_delete and not creator_can_modify:
            return jsonify({"success": False, "error": "当前账号无权删除巡检问题。"}), 403

        can_view_all = can_view_all_inspection_issues(cur, user)
        can_view_own = can_view_own_inspection_issues(cur, user)
        if not can_view_all and not (
            can_view_own
            and user.get("station_id")
            and issue["station_id"] == user["station_id"]
        ) and not issue_created_by_user(user, issue):
            return jsonify({"success": False, "error": "当前账号无权操作该巡检问题。"}), 403

        cur.execute("DELETE FROM issues WHERE id = %s;", (issue_id,))
        sync_inspection_primary_inspector(cur, issue["inspection_id"])

        # 巡检主记录和计划完成痕迹保留，记录结果由剩余问题数聚合自动体现。
        conn.commit()
        return jsonify({"success": True, "message": "巡检问题已删除。"})
    except Exception as e:
        if conn:
            conn.rollback()
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

        if not can_manage_plan(cur, user):
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

        if not can_manage_plan(cur, user):
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

        if not can_manage_plan(cur, user):
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


@app.route("/api/inspections/<int:inspection_id>/complete", methods=["POST"])
def complete_inspection_by_inspector(inspection_id):
    data = request.get_json(silent=True) or {}
    user_id = get_authenticated_request_user_id(data.get("user_id"))

    if not user_id:
        return jsonify({"success": False, "error": "缺少用户信息。"}), 400

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_issue_inspector_schema(cur)
        ensure_inspection_completion_schema(cur)

        user = get_user_by_id(cur, user_id)
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        if not is_supervisor_like(user):
            return jsonify({"success": False, "error": "只有督导组账号可以确认检查表完成。"}), 403

        cur.execute(
            """
            SELECT
                ins.id,
                ins.station_id,
                ins.inspection_table_id,
                ins.inspector_completion_status,
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

        if inspection.get("inspector_completion_status") == INSPECTION_COMPLETION_DONE:
            return jsonify({"success": False, "error": "该检查表已确认完成。"}), 400

        if not is_root_user(user) and not user_participated_in_inspection(cur, inspection_id, user_id):
            return jsonify({"success": False, "error": "只有参与该检查表录入的检查人员可以确认完成。"}), 403

        complete_inspection_record(cur, inspection_id, user_id, "manual")
        conn.commit()
        return jsonify(
            {
                "success": True,
                "message": "检查表已确认完成，后续不能再新增、编辑或删除该表问题。",
                "inspection_id": inspection_id,
            }
        )
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/inspection-completion")
def get_management_inspection_completion():
    user_id = str(request.args.get("user_id", "")).strip()
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ensure_issue_inspector_schema(cur)
        ensure_inspection_completion_schema(cur)
        sync_signed_inspections_completion(cur)
        actor = require_management_user(cur, user_id, "manage_inspection_completion")
        auto_completed_count = auto_complete_overdue_inspections(cur)
        config = get_inspection_completion_config(cur)

        cur.execute(
            """
            SELECT
                ins.id,
                ins.batch_id,
                TO_CHAR(ins.inspection_date, 'YYYY-MM-DD') AS inspection_date,
                TO_CHAR(ins.inspection_date, 'YYYY-MM') AS inspection_month,
                (%s::date - ins.inspection_date) AS age_days,
                s.station_name,
                s.region AS station_region,
                t.table_name AS inspection_table_name,
                COUNT(i.id) FILTER (WHERE COALESCE(i.audit_status, 'pending') <> 'rejected') AS issue_count,
                ins.sign_status,
                ins.station_manager_signed_name,
                TO_CHAR(ins.station_manager_signed_at, 'YYYY-MM-DD HH24:MI') AS station_manager_signed_at,
                ins.inspector_completion_status,
                ins.inspector_completion_source,
                TO_CHAR(ins.inspector_completed_at, 'YYYY-MM-DD HH24:MI') AS inspector_completed_at,
                COALESCE(completed_user.username, '') AS inspector_completed_by_username,
                COALESCE(completed_user.real_name, '') AS inspector_completed_by_name,
                STRING_AGG(
                    DISTINCT COALESCE(participant.real_name, participant.username),
                    '、'
                ) FILTER (WHERE participant.id IS NOT NULL) AS inspector_names,
                TO_CHAR(ins.created_at, 'YYYY-MM-DD HH24:MI') AS created_at,
                TO_CHAR(COALESCE(ins.updated_at, ins.created_at), 'YYYY-MM-DD HH24:MI') AS updated_at
            FROM inspections ins
            JOIN stations s ON s.id = ins.station_id
            JOIN inspection_tables t ON t.id = ins.inspection_table_id
            LEFT JOIN issues i ON i.inspection_id = ins.id
                AND COALESCE(i.audit_status, 'pending') <> 'rejected'
            LEFT JOIN users completed_user ON completed_user.id = ins.inspector_completed_by
            LEFT JOIN users participant ON participant.id = COALESCE(i.inspector_id, ins.inspector_id)
            GROUP BY
                ins.id,
                ins.batch_id,
                ins.inspection_date,
                s.station_name,
                s.region,
                t.table_name,
                ins.sign_status,
                ins.station_manager_signed_name,
                ins.station_manager_signed_at,
                ins.inspector_completion_status,
                ins.inspector_completion_source,
                ins.inspector_completed_at,
                completed_user.username,
                completed_user.real_name,
                ins.created_at,
                ins.updated_at
            ORDER BY ins.inspection_date DESC, ins.id DESC
            LIMIT 500;
            """,
            (beijing_today(),),
        )
        records = []
        for row in cur.fetchall():
            item = dict(row)
            item["issue_count"] = int(item.get("issue_count") or 0)
            item["age_days"] = int(item.get("age_days") or 0)
            item["inspection_period_key"] = format_inspection_period_key(
                item.get("inspection_date"),
                config["record_uniqueness_period"],
            )
            item["inspection_period_label"] = format_inspection_period_label(
                item.get("inspection_date"),
                config["record_uniqueness_period"],
            )
            item["inspector_completion_source_label"] = inspection_completion_source_label(
                item.get("inspector_completion_source")
            )
            records.append(item)

        conn.commit()
        return jsonify(
            {
                "success": True,
                "config": config,
                "records": records,
                "auto_completed_count": auto_completed_count,
                "actor": {
                    "id": actor["id"],
                    "username": actor["username"],
                    "real_name": actor["real_name"],
                },
            }
        )
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/inspection-completion/config", methods=["PUT"])
def update_management_inspection_completion_config():
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        actor = require_management_user(cur, user_id, "manage_inspection_completion")
        config = save_inspection_completion_config(cur, data, actor["id"])
        conn.commit()
        return jsonify({"success": True, "message": "巡检完成确认规则已保存。", "config": config})
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/inspection-completion/<int:inspection_id>/complete", methods=["POST"])
def complete_management_inspection_record(inspection_id):
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        actor = require_management_user(cur, user_id, "manage_inspection_completion")
        ensure_inspection_completion_schema(cur)
        updated = complete_inspection_record(cur, inspection_id, actor["id"], "admin")
        if updated == 0:
            return jsonify({"success": False, "error": "该巡检记录不存在或已确认完成。"}), 400
        conn.commit()
        return jsonify({"success": True, "message": "已在后台确认该检查表完成。"})
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/management/inspection-completion/<int:inspection_id>/reopen", methods=["POST"])
def reopen_management_inspection_record(inspection_id):
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        require_management_user(cur, user_id, "manage_inspection_completion")
        ensure_inspection_completion_schema(cur)
        sync_signed_inspections_completion(cur)
        cur.execute(
            """
            SELECT id, sign_status
            FROM inspections
            WHERE id = %s
            LIMIT 1;
            """,
            (inspection_id,),
        )
        inspection = cur.fetchone()
        if not inspection:
            return jsonify({"success": False, "error": "该巡检记录不存在。"}), 404
        if inspection.get("sign_status") == "已签名确认":
            return jsonify({"success": False, "error": "站经理已签字确认的巡检记录不能恢复为未完成。"}), 400
        updated = reopen_inspection_record(cur, inspection_id)
        if updated == 0:
            return jsonify({"success": False, "error": "该巡检记录不存在。"}), 404
        conn.commit()
        return jsonify({"success": True, "message": "该检查表已恢复为未完成状态。"})
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except LookupError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/assessment/attendance", methods=["GET"])
def get_assessment_attendance():
    try:
        month, month_start, next_month = parse_attendance_month(request.args.get("month"))
        mode_filter = normalize_attendance_mode(request.args.get("mode", "all"))
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        user = get_user_by_id(cur, g.current_user["id"])
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404
        if not can_view_assessment(cur, user):
            return jsonify({"success": False, "error": "当前账号无权查看人员出勤统计。"}), 403

        base_mode_clause = ""
        issue_mode_clause = ""
        params = [month_start, next_month]
        if mode_filter != "all":
            base_mode_clause = "AND COALESCE(NULLIF(t.checklist_mode, ''), 'online') = %s"
            params.append(mode_filter)
        params.extend([month_start, next_month])
        if mode_filter != "all":
            issue_mode_clause = "AND COALESCE(NULLIF(t.checklist_mode, ''), 'online') = %s"
            params.append(mode_filter)

        cur.execute(
            f"""
            WITH participant_rows AS (
                SELECT
                    ins.id AS inspection_id,
                    ins.inspection_date,
                    ins.station_id,
                    s.station_name,
                    s.region AS station_region,
                    t.id AS inspection_table_id,
                    t.table_name AS inspection_table_name,
                    COALESCE(NULLIF(t.checklist_mode, ''), 'online') AS checklist_mode,
                    ins.inspector_id
                FROM inspections ins
                JOIN stations s ON s.id = ins.station_id
                JOIN inspection_tables t ON t.id = ins.inspection_table_id
                WHERE ins.inspection_date >= %s
                  AND ins.inspection_date < %s
                  {base_mode_clause}

                UNION

                SELECT
                    ins.id AS inspection_id,
                    ins.inspection_date,
                    ins.station_id,
                    s.station_name,
                    s.region AS station_region,
                    t.id AS inspection_table_id,
                    t.table_name AS inspection_table_name,
                    COALESCE(NULLIF(t.checklist_mode, ''), 'online') AS checklist_mode,
                    i.inspector_id
                FROM issues i
                JOIN inspections ins ON ins.id = i.inspection_id
                JOIN stations s ON s.id = ins.station_id
                JOIN inspection_tables t ON t.id = ins.inspection_table_id
                WHERE ins.inspection_date >= %s
                  AND ins.inspection_date < %s
                  AND i.inspector_id IS NOT NULL
                  AND COALESCE(i.audit_status, 'pending') <> 'rejected'
                  {issue_mode_clause}
            )
            SELECT DISTINCT
                p.inspection_id,
                TO_CHAR(p.inspection_date, 'YYYY-MM-DD') AS inspection_date,
                p.station_id,
                p.station_name,
                p.station_region,
                p.inspection_table_id,
                p.inspection_table_name,
                p.checklist_mode,
                p.inspector_id,
                u.username AS inspector_username,
                u.real_name AS inspector_name,
                u.phone AS inspector_phone
            FROM participant_rows p
            JOIN users u ON u.id = p.inspector_id
            WHERE p.inspector_id IS NOT NULL
              AND p.checklist_mode IN ('online', 'offline')
            ORDER BY
                p.checklist_mode,
                inspection_date,
                p.station_region,
                p.station_name,
                p.inspection_table_name,
                inspector_name;
            """,
            params,
        )
        rows = [dict(row) for row in cur.fetchall()]
        return jsonify(
            {
                "success": True,
                **build_attendance_payload(rows, month, mode_filter),
            }
        )
    except Exception as e:
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
        ensure_issue_inspector_schema(cur)
        ensure_inspection_completion_schema(cur)
        auto_complete_overdue_inspections(cur)
        conn.commit()

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

        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        can_view_all = can_view_all_inspection_records(cur, user)
        can_view_own = can_view_own_inspection_records(cur, user)
        can_delete_records = can_delete_inspection_records(cur, user)
        can_sign_records = can_sign_inspection_records(cur, user)
        can_reset_signature = can_reset_inspection_signature(cur, user)
        if can_view_all:
            pass
        elif can_view_own:
            if not user["station_id"]:
                return jsonify([])
            where_clause = "WHERE ins.station_id = %s"
            params.append(user["station_id"])
        else:
            return jsonify({"success": False, "error": "当前账号无权查看巡检记录。"}), 403

        cur.execute(
            sql.SQL(
                """
                SELECT
                    ins.id AS id,
                    ins.batch_id AS batch_id,
                    ins.station_id AS station_id,
                    TO_CHAR(ins.inspection_date, 'YYYY-MM-DD') AS date,
                    s.station_name AS station,
                    t.table_name AS inspection_table_name,
                    CASE
                        WHEN COUNT(i.id) FILTER (WHERE COALESCE(i.audit_status, 'pending') <> 'rejected') > 0 THEN '异常'
                        ELSE '正常'
                    END AS result,
                    COUNT(i.id) FILTER (WHERE COALESCE(i.audit_status, 'pending') <> 'rejected') AS issue_count,
                    COUNT(i.id) AS total_issue_count,
                    COUNT(i.id) FILTER (WHERE COALESCE(i.audit_status, 'pending') = 'pending') AS pending_audit_count,
                    COUNT(i.id) FILTER (WHERE COALESCE(i.audit_status, 'pending') <> 'pending') AS audited_issue_count,
                    COUNT(i.id) FILTER (
                        WHERE NULLIF(TRIM(COALESCE(i.rectification_result, '')), '') IS NOT NULL
                           OR NULLIF(TRIM(COALESCE(i.rectification_note, '')), '') IS NOT NULL
                           OR NULLIF(TRIM(COALESCE(i.rectification_photo_path, '')), '') IS NOT NULL
                    ) AS rectified_issue_count,
                    ins.sign_status,
                    ins.station_manager_signed_name,
                    ins.station_manager_signature_path,
                    TO_CHAR(ins.station_manager_signed_at, 'YYYY-MM-DD HH24:MI') AS station_manager_signed_at,
                    ins.inspector_completion_status,
                    ins.inspector_completion_source,
                    TO_CHAR(ins.inspector_completed_at, 'YYYY-MM-DD HH24:MI') AS inspector_completed_at,
                    completed_user.username AS inspector_completed_by_username,
                    completed_user.real_name AS inspector_completed_by_name,
                    (
                        SELECT STRING_AGG(
                            DISTINCT COALESCE(participant.real_name, participant.username, participant.phone, participant.id::text),
                            '、'
                        )
                        FROM (
                            SELECT ins_part.inspector_id AS inspector_id
                            FROM inspections ins_part
                            WHERE ins_part.id = ins.id
                            UNION
                            SELECT issue_part.inspector_id AS inspector_id
                            FROM issues issue_part
                            WHERE issue_part.inspection_id = ins.id
                              AND issue_part.inspector_id IS NOT NULL
                              AND COALESCE(issue_part.audit_status, 'pending') <> 'rejected'
                        ) participant_ids
                        JOIN users participant ON participant.id = participant_ids.inspector_id
                    ) AS inspector_names,
                    (
                        SELECT STRING_AGG(
                            DISTINCT CONCAT_WS(' ', participant.real_name, participant.username, participant.phone),
                            ' '
                        )
                        FROM (
                            SELECT ins_part.inspector_id AS inspector_id
                            FROM inspections ins_part
                            WHERE ins_part.id = ins.id
                            UNION
                            SELECT issue_part.inspector_id AS inspector_id
                            FROM issues issue_part
                            WHERE issue_part.inspection_id = ins.id
                              AND issue_part.inspector_id IS NOT NULL
                              AND COALESCE(issue_part.audit_status, 'pending') <> 'rejected'
                        ) participant_ids
                        JOIN users participant ON participant.id = participant_ids.inspector_id
                    ) AS inspector_search_text,
                    BOOL_OR(
                        ins.inspector_id = %s
                        OR (
                            i.inspector_id = %s
                            AND COALESCE(i.audit_status, 'pending') <> 'rejected'
                        )
                    ) AS current_user_participated
                FROM inspections ins
                JOIN stations s ON ins.station_id = s.id
                JOIN inspection_tables t ON ins.inspection_table_id = t.id
                LEFT JOIN users completed_user ON completed_user.id = ins.inspector_completed_by
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
                    ins.station_manager_signed_at,
                    ins.inspector_completion_status,
                    ins.inspector_completion_source,
                    ins.inspector_completed_at,
                    completed_user.username,
                    completed_user.real_name
                ORDER BY ins.inspection_date DESC, ins.id DESC;
                """
            ).format(where_clause=sql.SQL(where_clause)),
            [user["id"], user["id"], *params],
        )
        rows = cur.fetchall()
        return jsonify(
            [
                {
                    **dict(row),
                    "can_delete_record": bool(can_delete_records),
                    "can_reset_signature": bool(
                        can_reset_signature
                        and row.get("sign_status") == "已签名确认"
                        and int(row.get("rectified_issue_count") or 0) == 0
                    ),
                    "reset_signature_lock_reason": (
                        "已有站经理整改，不能重置签名。"
                        if int(row.get("rectified_issue_count") or 0) > 0
                        else ""
                    ),
                    "can_sign_record": bool(
                        is_station_manager(user)
                        and can_sign_records
                        and row.get("sign_status") != "已签名确认"
                        and user.get("station_id")
                        and row.get("station_id") == user.get("station_id")
                        and int(row.get("pending_audit_count") or 0) == 0
                    ),
                    "can_complete_record": bool(
                        is_supervisor_like(user)
                        and row.get("inspector_completion_status") != INSPECTION_COMPLETION_DONE
                        and row.get("current_user_participated")
                    ),
                    "inspector_completion_source_label": inspection_completion_source_label(
                        row.get("inspector_completion_source")
                    ),
                }
                for row in rows
            ]
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    finally:
        close_db_resources(cur, conn)


@app.route("/api/inspections/<int:inspection_id>", methods=["DELETE"])
def delete_inspection_record(inspection_id):
    data = request.get_json(silent=True) or {}
    user_id = get_authenticated_request_user_id(
        data.get("user_id") or request.args.get("user_id", "")
    )

    if not user_id:
        return jsonify({"success": False, "error": "缺少用户信息。"}), 400

    conn = None
    cur = None
    files_to_remove = set()

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        user = get_user_by_id(cur, user_id)
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        if not can_delete_inspection_records(cur, user):
            return jsonify({"success": False, "error": "当前账号无权删除巡检记录。"}), 403

        cur.execute(
            """
            SELECT
                ins.id,
                ins.batch_id,
                ins.station_id,
                ins.inspection_table_id,
                ins.inspection_date,
                ins.station_manager_signature_path,
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

        can_view_all = can_view_all_inspection_records(cur, user)
        can_view_own = can_view_own_inspection_records(cur, user)
        if not can_view_all and not (
            can_view_own
            and user.get("station_id")
            and inspection["station_id"] == user["station_id"]
        ):
            return jsonify({"success": False, "error": "当前账号无权操作该巡检记录。"}), 403

        if inspection.get("station_manager_signature_path"):
            files_to_remove.add(inspection["station_manager_signature_path"])

        cur.execute(
            """
            SELECT
                id,
                photo_path,
                rectification_photo_path,
                review_photo_path
            FROM issues
            WHERE inspection_id = %s;
            """,
            (inspection_id,),
        )
        issue_rows = cur.fetchall()
        for issue in issue_rows:
            for key in (
                "photo_path",
                "rectification_photo_path",
                "review_photo_path",
            ):
                if issue.get(key):
                    files_to_remove.add(issue[key])

        cur.execute(
            """
            SELECT DISTINCT plan_config_id
            FROM inspection_plan_station_items
            WHERE completed_inspection_id = %s;
            """,
            (inspection_id,),
        )
        affected_plan_config_ids = [row["plan_config_id"] for row in cur.fetchall()]

        cur.execute(
            """
            UPDATE inspection_plan_station_items
            SET completion_status = 'pending',
                completed_inspection_id = NULL,
                completed_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE completed_inspection_id = %s;
            """,
            (inspection_id,),
        )
        affected_plan_item_count = cur.rowcount

        cur.execute("DELETE FROM issues WHERE inspection_id = %s;", (inspection_id,))
        deleted_issue_count = cur.rowcount

        cur.execute("DELETE FROM inspections WHERE id = %s;", (inspection_id,))
        if cur.rowcount == 0:
            raise ValueError("巡检记录删除失败，请刷新后重试。")

        if inspection.get("batch_id"):
            cur.execute(
                """
                DELETE FROM inspection_batches b
                WHERE b.id = %s
                  AND NOT EXISTS (
                    SELECT 1
                    FROM inspections ins
                    WHERE ins.batch_id = b.id
                  );
                """,
                (inspection["batch_id"],),
            )

        for plan_config_id in affected_plan_config_ids:
            sync_plan_station_items_completion_by_history(cur, plan_config_id)

        conn.commit()

        for path in files_to_remove:
            remove_storage_file(path)

        return jsonify(
            {
                "success": True,
                "message": "巡检记录已删除，关联巡检问题和计划完成状态已同步更新。",
                "deleted_issue_count": deleted_issue_count,
                "affected_plan_item_count": affected_plan_item_count,
            }
        )
    except ValueError as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        if conn:
            conn.rollback()
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
        ensure_issue_inspector_schema(cur)

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
                TO_CHAR(ins.inspection_date, 'YYYY-MM-DD') AS inspection_date,
                TO_CHAR(ins.inspection_date, 'YYYY-MM-DD') AS date,
                ins.inspector_id,
                ins.sign_status,
                ins.station_manager_signed_name,
                ins.station_manager_signature_path,
                TO_CHAR(ins.station_manager_signed_at, 'YYYY-MM-DD HH24:MI') AS station_manager_signed_at,
                ins.inspector_completion_status,
                ins.inspector_completion_source,
                TO_CHAR(ins.inspector_completed_at, 'YYYY-MM-DD HH24:MI') AS inspector_completed_at,
                completed_user.username AS inspector_completed_by_username,
                completed_user.real_name AS inspector_completed_by_name,
                s.station_name,
                s.region AS station_region,
                s.address AS station_address,
                s.station_manager_name,
                s.station_manager_phone,
                inspector.username AS inspector_username,
                inspector.real_name AS inspector_name,
                inspector.phone AS inspector_phone,
                t.table_name AS inspection_table_name
            FROM inspections ins
            JOIN stations s ON ins.station_id = s.id
            JOIN inspection_tables t ON ins.inspection_table_id = t.id
            JOIN users inspector ON ins.inspector_id = inspector.id
            LEFT JOIN users completed_user ON completed_user.id = ins.inspector_completed_by
            WHERE ins.id = %s
            LIMIT 1;
            """,
            (inspection_id,),
        )
        inspection = cur.fetchone()

        if not inspection:
            return jsonify({"success": False, "error": "巡检记录不存在。"}), 404

        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        can_view_all = can_view_all_inspection_records(cur, user)
        can_view_own = can_view_own_inspection_records(cur, user)
        cur.execute(
            """
            SELECT DISTINCT
                participant.id,
                participant.username,
                participant.real_name,
                participant.phone
            FROM (
                SELECT ins.inspector_id AS inspector_id
                FROM inspections ins
                WHERE ins.id = %s
                UNION
                SELECT i.inspector_id AS inspector_id
                FROM issues i
                WHERE i.inspection_id = %s
                  AND i.inspector_id IS NOT NULL
                  AND COALESCE(i.audit_status, 'pending') <> 'rejected'
            ) participant_ids
            JOIN users participant ON participant_ids.inspector_id = participant.id
            ORDER BY participant.id ASC;
            """,
            (inspection_id, inspection_id),
        )
        inspectors = [dict(row) for row in cur.fetchall()]
        inspection = dict(inspection)
        inspection["inspectors"] = inspectors
        inspection["inspector_names"] = "、".join(
            [
                (row.get("real_name") or row.get("username") or str(row.get("id")))
                for row in inspectors
            ]
        )
        inspection["inspector_completion_source_label"] = inspection_completion_source_label(
            inspection.get("inspector_completion_source")
        )

        is_inspector = any(str(item.get("id") or "") == str(user.get("id") or "") for item in inspectors)
        if (
            can_view_own
            and not can_view_all
            and inspection["station_id"] != user["station_id"]
            and not is_inspector
        ):
            return jsonify({"success": False, "error": "无权查看该检查表内容。"}), 403
        if not can_view_all and not can_view_own and not is_inspector:
            return jsonify({"success": False, "error": "无权查看该检查表内容。"}), 403

        cur.execute(
            """
            SELECT
                i.id,
                COALESCE(i.inspector_id, ins.inspector_id) AS inspector_id,
                issue_inspector.username AS inspector_username,
                issue_inspector.real_name AS inspector_name,
                issue_inspector.phone AS inspector_phone,
                TO_CHAR(i.created_at, 'YYYY-MM-DD HH24:MI') AS created_at,
                t.table_name AS inspection_table_name,
                i.standard_id,
                i.standard_detail_text,
                i.internal_standard_id,
                i.internal_standard_detail_text,
                i.description,
                i.photo_path AS issue_photo,
                i.rectification_result,
                i.rectification_note,
                i.rectification_photo_path AS rectification_photo,
                i.review_result,
                i.review_note,
                i.review_photo_path AS review_photo,
                i.status,
                COALESCE(i.audit_status, 'pending') AS audit_status,
                i.audited_by,
                TO_CHAR(i.audited_at, 'YYYY-MM-DD HH24:MI') AS audited_at,
                ins.sign_status AS inspection_sign_status,
                ins.station_manager_signed_name,
                ins.station_manager_signature_path,
                TO_CHAR(ins.station_manager_signed_at, 'YYYY-MM-DD HH24:MI') AS station_manager_signed_at,
                ins.inspector_completion_status AS inspection_completion_status
            FROM issues i
            JOIN inspections ins ON i.inspection_id = ins.id
            JOIN inspection_tables t ON i.inspection_table_id = t.id
            JOIN users issue_inspector ON COALESCE(i.inspector_id, ins.inspector_id) = issue_inspector.id
            WHERE i.inspection_id = %s
              AND COALESCE(i.audit_status, 'pending') <> 'rejected'
            ORDER BY i.id ASC;
            """,
            (inspection_id,),
        )
        issues = [normalize_issue_row_for_response(row, user) for row in cur.fetchall()]

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
    rectification_result = canonical_issue_result(
        request.form.get("rectification_result", "")
    )
    rectification_note = str(request.form.get("rectification_note", "")).strip()
    rectification_photo = request.files.get("rectification_photo")

    if not user_id:
        return jsonify({"success": False, "error": "缺少用户信息。"}), 400

    if not rectification_result:
        return jsonify({"success": False, "error": "请选择整改结果。"}), 400

    if rectification_result not in ISSUE_RESULT_OPTIONS:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "整改结果只能选择已整改或站经无法整改。",
                }
            ),
            400,
        )

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
                COALESCE(i.audit_status, 'pending') AS audit_status,
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

        if is_issue_audit_rejected(issue):
            return jsonify({"success": False, "error": "该问题已被审核否决，不再参与整改流转。"}), 400

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


@app.route("/api/issues/<int:issue_id>/rectification-photo", methods=["POST"])
def update_rectification_photo(issue_id):
    user_id = str(request.form.get("user_id", "")).strip()
    rectification_photo = request.files.get("rectification_photo")

    if not user_id:
        return jsonify({"success": False, "error": "缺少用户信息。"}), 400

    if not rectification_photo or not rectification_photo.filename:
        return jsonify({"success": False, "error": "请上传新的整改照片。"}), 400

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        user = get_user_by_id(cur, user_id)
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        cur.execute(
            """
            SELECT
                id,
                station_id,
                status,
                COALESCE(audit_status, 'pending') AS audit_status,
                rectification_result
            FROM issues
            WHERE id = %s
            LIMIT 1;
            """,
            (issue_id,),
        )
        issue = cur.fetchone()

        if not issue:
            return jsonify({"success": False, "error": "问题不存在。"}), 404

        can_explicit_edit = can_edit_inspection_issues(cur, user)
        if not can_user_update_rectification_photo(user, issue, can_explicit_edit):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "当前账号无权更新该问题的整改照片，或问题已不在可修改阶段。",
                    }
                ),
                403,
            )

        rectification_photo_path = save_uploaded_file(
            rectification_photo, "rectifications"
        )
        cur.execute(
            """
            UPDATE issues
            SET rectification_photo_path = %s
            WHERE id = %s;
            """,
            (rectification_photo_path, issue_id),
        )
        conn.commit()

        return jsonify(
            {
                "success": True,
                "message": "整改照片已更新。",
                "rectification_photo": rectification_photo_path,
            }
        )
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        close_db_resources(cur, conn)


@app.route("/api/issues/<int:issue_id>/review", methods=["POST"])
def submit_review(issue_id):
    user_id = str(request.form.get("user_id", "")).strip()
    review_result = canonical_issue_result(request.form.get("review_result", ""))
    review_note = str(request.form.get("review_note", "")).strip()
    review_photo = request.files.get("review_photo")

    if not user_id:
        return jsonify({"success": False, "error": "缺少用户信息。"}), 400

    if not review_result:
        return jsonify({"success": False, "error": "请选择督导组复核结果。"}), 400

    if review_result not in ISSUE_RESULT_OPTIONS:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "督导组复核结果只能选择已整改或站经无法整改。",
                }
            ),
            400,
        )

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

        if not (is_root_user(user) or user.get("role") == "supervisor"):
            return (
                jsonify({"success": False, "error": "只有督导组账号可以提交复核。"}),
                403,
            )

        cur.execute(
            """
            SELECT id, status
                , COALESCE(audit_status, 'pending') AS audit_status
            FROM issues
            WHERE id = %s
            LIMIT 1;
            """,
            (issue_id,),
        )
        issue = cur.fetchone()

        if not issue:
            return jsonify({"success": False, "error": "问题不存在。"}), 404

        if is_issue_audit_rejected(issue):
            return jsonify({"success": False, "error": "该问题已被审核否决，不再参与复核流转。"}), 400

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

        new_status = "已闭环" if review_result == "已整改" else "站经无法整改"
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
        return jsonify(
            {
                "success": True,
                "message": f"督导组复核提交成功，问题状态已更新为{new_status}。",
            }
        )
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
