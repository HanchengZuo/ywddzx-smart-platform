from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS
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
BACKUP_CONFIG_PATH = os.path.join(STORAGE_ROOT, "backup_config.json")
DEFAULT_BACKUP_DIR = os.path.join(STORAGE_ROOT, "backups")
BACKUP_PREFIX = "ywddzx_full_backup"
AUTO_BACKUP_FILENAME = f"{BACKUP_PREFIX}_auto.zip"
BEIJING_TZ = ZoneInfo("Asia/Shanghai")


TABLE_CODE_TO_PHYSICAL_TABLE = {
    "quality_check": "inspection_table_quality_check",
    "service_hygiene_check": "inspection_table_service_hygiene_check",
}

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
        "description": "访问巡检规范库并查询检查表规范条目。",
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
        "name": "编辑本站数据",
        "category": "站点证照有效期管理",
        "description": "录入、修改、删除当前账号所属站点的证照有效期。",
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
STATION_TYPE_OPTIONS = {"加油站", "充电站"}
STATION_ASSET_TYPE_OPTIONS = {"全资", "股权"}
STATION_CONSOLIDATED_OPTIONS = {"是", "否"}
STATION_ONLINE_3_STATUS_OPTIONS = {"上线", "上线参股模式", "未上线"}
STATION_STATUS_OPTIONS = {"营业中", "停业"}
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
        "last_auto_export_at": None,
        "last_backup_path": None,
        "last_backup_size": None,
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
    return config


def write_backup_config(config):
    next_config = get_default_backup_config()
    next_config.update(config or {})
    next_config["destination_path"] = normalize_backup_destination_path(
        next_config.get("destination_path")
    )
    if next_config.get("frequency") not in BACKUP_FREQUENCY_INTERVALS:
        next_config["frequency"] = "off"
    next_config["updated_at"] = beijing_now().isoformat()
    os.makedirs(os.path.dirname(BACKUP_CONFIG_PATH), exist_ok=True)
    with open(BACKUP_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(next_config, f, ensure_ascii=False, indent=2)
    return next_config


def get_backup_next_run_at(config):
    interval = BACKUP_FREQUENCY_INTERVALS.get(config.get("frequency"))
    if not interval:
        return None
    last_run = parse_backup_time(config.get("last_auto_export_at"))
    if not last_run:
        return beijing_now().isoformat()
    return (last_run.astimezone(BEIJING_TZ) + interval).isoformat()


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


def should_skip_storage_backup_path(path, excluded_dirs):
    abs_path = os.path.abspath(path)
    for excluded_dir in excluded_dirs:
        try:
            if os.path.commonpath([excluded_dir, abs_path]) == excluded_dir:
                return True
        except ValueError:
            continue
    return False


def add_storage_to_backup(zip_file, destination_path):
    storage_root_abs = os.path.abspath(STORAGE_ROOT)
    excluded_dirs = [os.path.abspath(destination_path), os.path.abspath(DEFAULT_BACKUP_DIR)]
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
            if should_skip_storage_backup_path(file_path, excluded_dirs):
                continue
            relative_path = os.path.relpath(file_path, storage_root_abs).replace("\\", "/")
            zip_file.write(file_path, f"storage/{relative_path}")


def create_full_backup_archive(destination_path=None, reason="manual"):
    backup_dir = normalize_backup_destination_path(destination_path)
    os.makedirs(backup_dir, exist_ok=True)

    now = beijing_now()
    filename = (
        AUTO_BACKUP_FILENAME
        if reason == "auto"
        else f"{BACKUP_PREFIX}_{now.strftime('%Y%m%d_%H%M%S')}.zip"
    )
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
            "version": 1,
            "created_at": now.isoformat(),
            "reason": reason,
            "database": db_config["dbname"],
            "storage_root": STORAGE_ROOT,
        }

        temp_zip_path = os.path.join(temp_dir, filename)
        with zipfile.ZipFile(temp_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            zip_file.write(database_dump_path, "database.dump")
            add_storage_to_backup(zip_file, backup_dir)

        if reason == "auto":
            os.replace(temp_zip_path, final_path)
        else:
            shutil.copy2(temp_zip_path, final_path)

    return {
        "path": final_path,
        "filename": filename,
        "size": os.path.getsize(final_path),
        "created_at": now.isoformat(),
    }


def validate_backup_archive(zip_path):
    try:
        with zipfile.ZipFile(zip_path, "r") as zip_file:
            names = set(zip_file.namelist())
            if "manifest.json" not in names or "database.dump" not in names:
                raise ValueError("备份文件缺少 manifest.json 或 database.dump。")
            manifest = json.loads(zip_file.read("manifest.json").decode("utf-8"))
            if manifest.get("backup_type") != "ywddzx_full_backup":
                raise ValueError("备份文件类型不正确。")
            return manifest
    except zipfile.BadZipFile as exc:
        raise ValueError("备份文件不是有效的 ZIP 文件。") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("备份文件清单格式不正确。") from exc


def restore_database_from_dump(database_dump_path):
    db_config, env = build_pg_environment()
    pg_restore_command = [
        "pg_restore",
        "-h",
        db_config["host"],
        "-p",
        db_config["port"],
        "-U",
        db_config["user"],
        "-d",
        db_config["dbname"],
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-acl",
        "--single-transaction",
        database_dump_path,
    ]
    run_backup_subprocess(pg_restore_command, env)


def clear_uploaded_storage_dirs():
    for directory in (
        ISSUES_STORAGE_DIR,
        RECTIFICATIONS_STORAGE_DIR,
        SIGNATURES_STORAGE_DIR,
        INSPECTION_ORIGINALS_STORAGE_DIR,
        TRAINING_MATERIALS_STORAGE_DIR,
    ):
        if os.path.isdir(directory):
            shutil.rmtree(directory)
        os.makedirs(directory, exist_ok=True)


def restore_storage_from_backup(zip_path):
    storage_root_abs = os.path.abspath(STORAGE_ROOT)
    with zipfile.ZipFile(zip_path, "r") as zip_file:
        for member in zip_file.infolist():
            name = member.filename
            if not name.startswith("storage/") or name.endswith("/"):
                continue
            relative_path = name[len("storage/") :]
            target_path = os.path.abspath(os.path.join(storage_root_abs, relative_path))
            if os.path.commonpath([storage_root_abs, target_path]) != storage_root_abs:
                raise ValueError("备份文件中存在非法 storage 路径。")

        clear_uploaded_storage_dirs()
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
            database_dump_path = os.path.join(temp_dir, "database.dump")
            zip_file.extract("database.dump", temp_dir)
        restore_database_from_dump(database_dump_path)
        restore_storage_from_backup(backup_path)
        return manifest


def mark_auto_backup_result(success, result=None, error=""):
    config = read_backup_config()
    if success:
        config.update(
            {
                "last_auto_export_at": beijing_now().isoformat(),
                "last_backup_path": result.get("path") if result else None,
                "last_backup_size": result.get("size") if result else None,
                "last_status": "success",
                "last_error": "",
            }
        )
    else:
        config.update(
            {
                "last_status": "error",
                "last_error": str(error or "自动备份失败。")[:500],
            }
        )
    write_backup_config(config)


def maybe_run_scheduled_backup():
    config = read_backup_config()
    interval = BACKUP_FREQUENCY_INTERVALS.get(config.get("frequency"))
    if not interval:
        return

    last_run = parse_backup_time(config.get("last_auto_export_at"))
    now = beijing_now()
    if last_run and now < last_run.astimezone(BEIJING_TZ) + interval:
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


@app.before_request
def ensure_backup_scheduler_started():
    start_backup_scheduler_once()


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
        VALUES ('root', '123456', 'root', '系统管理员', '18801800773', NULL)
        ON CONFLICT (username) DO NOTHING;
        """
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

    ensure_user_security_schema(cur)
    cur.execute(
        """
        SELECT is_allowed
        FROM user_permissions
        WHERE user_id = %s AND permission_key = %s
        LIMIT 1;
        """,
        (user["id"], permission_key),
    )
    override = cur.fetchone()
    if override:
        return bool(override["is_allowed"])
    return role_default_permission(user.get("role"), permission_key)


def can_manage_plan(cur, user):
    return has_permission(cur, user, "manage_inspection_plans")


def can_manage_system(cur, user, permission_key):
    return is_root_user(user)


def can_view_inspection_standards(cur, user):
    return has_permission(cur, user, "view_inspection_standards")


def can_view_checklist_originals(cur, user):
    return has_permission(cur, user, "view_checklist_originals")


def can_view_all_inspection_issues(cur, user):
    return bool(get_effective_permissions(cur, user).get("view_all_inspection_issues"))


def can_view_own_inspection_issues(cur, user):
    return bool(get_effective_permissions(cur, user).get("view_own_inspection_issues"))


def can_view_all_inspection_records(cur, user):
    return bool(get_effective_permissions(cur, user).get("view_all_inspection_records"))


def can_view_own_inspection_records(cur, user):
    return bool(get_effective_permissions(cur, user).get("view_own_inspection_records"))


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
        ensure_user_security_schema(cur)
        conn.commit()
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

        permissions = get_effective_permissions(cur, user)
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
                    "permissions": permissions,
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

        if not is_supervisor_like(user):
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
        ensure_station_management_columns(cur)
        conn.commit()
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
                is_consolidated,
                online_3_status,
                hos_station_code,
                landline_phone,
                status,
                operating_hours
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
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "permission_overrides": overrides,
                    "permissions": permissions,
                }
            )

        cur.execute(
            """
            SELECT id, station_name
            FROM stations
            ORDER BY station_name ASC, id ASC;
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
            WHERE u.role <> 'root'
            ORDER BY
                CASE u.role
                    WHEN 'supervisor' THEN 1
                    ELSE 2
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
                "excluded_builtin_accounts": ["root"],
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
            if raw_username == "root" or raw_role == "root":
                skipped_builtin_count += 1
                continue

            user_data = build_management_user_payload(raw_user, is_create=True)
            if user_data["role"] == "root":
                skipped_builtin_count += 1
                continue

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
        for user_data in user_payloads:
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
        return jsonify(
            {
                "success": True,
                "config": {
                    **config,
                    "next_run_at": get_backup_next_run_at(config),
                },
                "frequency_options": [
                    {"value": "off", "label": "关闭自动备份"},
                    {"value": "hourly", "label": "每小时"},
                    {"value": "daily", "label": "每天"},
                    {"value": "weekly", "label": "每周"},
                    {"value": "monthly", "label": "每月"},
                ],
                "latest_backups": list_backup_files(config.get("destination_path")),
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
        config = write_backup_config(
            {
                **current_config,
                "destination_path": destination_path,
                "frequency": frequency,
                "last_status": current_config.get("last_status") or "idle",
                "last_error": current_config.get("last_error") or "",
            }
        )
        return jsonify(
            {
                "success": True,
                "message": "备份设置已保存。",
                "config": {
                    **config,
                    "next_run_at": get_backup_next_run_at(config),
                },
                "latest_backups": list_backup_files(config.get("destination_path")),
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
            config.update(
                {
                    "last_backup_path": result["path"],
                    "last_backup_size": result["size"],
                    "last_status": "success",
                    "last_error": "",
                }
            )
            write_backup_config(config)
        finally:
            backup_job_lock.release()

        response = send_file(
            result["path"],
            as_attachment=True,
            download_name=result["filename"],
            mimetype="application/zip",
        )
        response.headers["X-Backup-Path"] = result["path"]
        response.headers["X-Backup-Size"] = str(result["size"])
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

        if is_station_manager(user):
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

        if is_root_user(user) or user.get("role") == "supervisor":
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

        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        can_view_all = can_view_all_inspection_issues(cur, user)
        can_view_own = can_view_own_inspection_issues(cur, user)
        if can_view_all:
            pass
        elif can_view_own:
            if not user["station_id"]:
                return jsonify([])
            where_clause = "WHERE i.station_id = %s"
            params.append(user["station_id"])
        else:
            return jsonify({"success": False, "error": "当前账号无权查看巡检问题列表。"}), 403

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

        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        can_view_all = can_view_all_inspection_records(cur, user)
        can_view_own = can_view_own_inspection_records(cur, user)
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

        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        can_view_all = can_view_all_inspection_records(cur, user)
        can_view_own = can_view_own_inspection_records(cur, user)
        if (
            can_view_own
            and not can_view_all
            and inspection["station_id"] != user["station_id"]
        ):
            return jsonify({"success": False, "error": "无权查看该检查表内容。"}), 403
        if not can_view_all and not can_view_own:
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

        if not (is_root_user(user) or user.get("role") == "supervisor"):
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
