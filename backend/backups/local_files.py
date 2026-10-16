"""Local backup listing, storage packing and publication; no database or task ownership."""
from datetime import datetime
import os
import shutil
import uuid


def list_backup_files(backup_dir, *, backup_prefix, timezone):
    if not os.path.isdir(backup_dir):
        return []
    rows = []
    for filename in os.listdir(backup_dir):
        if not (filename.startswith(backup_prefix) and filename.endswith(".zip")):
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
                "updated_at": datetime.fromtimestamp(stat.st_mtime, timezone).isoformat(),
            }
        )
    return sorted(rows, key=lambda item: item["updated_at"], reverse=True)[:20]


def should_skip_storage_backup_path(path, excluded_dirs):
    abs_path = os.path.abspath(path)
    for excluded_dir in excluded_dirs:
        try:
            if os.path.commonpath([excluded_dir, abs_path]) == excluded_dir:
                return True
        except ValueError:
            continue
    return False


def get_storage_backup_excluded_dirs(destination_path, *, storage_root, report_exports_dir, default_backup_dir):
    storage_root_abs = os.path.abspath(storage_root)
    excluded_dirs = [os.path.abspath(report_exports_dir)]
    for candidate in (destination_path, default_backup_dir):
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


def add_storage_to_backup(
    zip_file, destination_path, *, storage_root, config_path, backup_prefix, get_excluded_dirs, should_skip_path
):
    storage_root_abs = os.path.abspath(storage_root)
    excluded_dirs = get_excluded_dirs(destination_path)
    for root, dirs, files in os.walk(storage_root_abs):
        dirs[:] = [
            name
            for name in dirs
            if not should_skip_path(os.path.join(root, name), excluded_dirs)
        ]
        if should_skip_path(root, excluded_dirs):
            continue
        for filename in files:
            file_path = os.path.join(root, filename)
            if file_path == os.path.abspath(config_path):
                continue
            if (
                os.path.abspath(root) == storage_root_abs
                and filename.startswith(backup_prefix)
                and filename.endswith(".zip")
            ):
                continue
            if should_skip_path(file_path, excluded_dirs):
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


def cleanup_local_backup_files(backup_dir, keep_path=None, *, backup_prefix):
    keep_abs = os.path.abspath(keep_path) if keep_path else ""
    if not os.path.isdir(backup_dir):
        return
    for filename in os.listdir(backup_dir):
        if not (filename.startswith(backup_prefix) and filename.endswith(".zip")):
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
