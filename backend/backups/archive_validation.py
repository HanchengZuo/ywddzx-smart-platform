"""Read-only ZIP/manifest checks; restoration and destructive I/O stay in app.py."""
import json
import os
import zipfile


def get_database_backup_member_name(names):
    if "database.dump" in names:
        return "database.dump"
    if "database.sql" in names:
        return "database.sql"
    raise ValueError("备份文件缺少 database.dump 或 database.sql。")


def validate_backup_archive(zip_path, *, select_database_member):
    try:
        with zipfile.ZipFile(zip_path, "r") as zip_file:
            names = set(zip_file.namelist())
            if "manifest.json" not in names:
                raise ValueError("备份文件缺少 manifest.json。")
            database_member_name = select_database_member(names)
            manifest = json.loads(zip_file.read("manifest.json").decode("utf-8"))
            if manifest.get("backup_type") != "ywddzx_full_backup":
                raise ValueError("备份文件类型不正确。")
            manifest["database_member"] = database_member_name
            return manifest
    except zipfile.BadZipFile as exc:
        raise ValueError("备份文件不是有效的 ZIP 文件。") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("备份文件清单格式不正确。") from exc


def validate_storage_backup_members(zip_file, *, storage_root):
    storage_root_abs = os.path.abspath(storage_root)
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
