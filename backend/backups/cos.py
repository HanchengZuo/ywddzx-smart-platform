"""COS backup operations with explicit configuration, SDK and orchestration dependencies."""
from datetime import datetime
import os
from zoneinfo import ZoneInfo


def get_cos_env_config(*, environ, prefix, retention_count, sdk_available):
    secret_id = environ.get("COS_SECRET_ID", "").strip()
    secret_key = environ.get("COS_SECRET_KEY", "").strip()
    region = environ.get("COS_REGION", "").strip()
    bucket = environ.get("COS_BUCKET", "").strip()
    prefix = f"{prefix}/" if prefix else ""
    configured = all((secret_id, secret_key, region, bucket))
    return {
        "secret_id": secret_id,
        "secret_key": secret_key,
        "region": region,
        "bucket": bucket,
        "prefix": prefix,
        "configured": configured,
        "sdk_available": sdk_available,
        "retention_count": retention_count,
        "use_internal": environ.get("COS_USE_INTERNAL", "false").lower() in {"true", "1", "yes"},
    }


def get_cos_public_status(cos_config, config=None, error=""):
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


def get_cos_client(cos_config, *, config_factory, client_factory):
    if not cos_config["configured"]:
        raise RuntimeError("未配置 COS_SECRET_ID、COS_SECRET_KEY、COS_REGION 或 COS_BUCKET。")
    if not cos_config["sdk_available"]:
        raise RuntimeError("后端缺少腾讯云 COS Python SDK，请重新安装依赖。")
    config = config_factory(
        Region=cos_config["region"],
        SecretId=cos_config["secret_id"],
        SecretKey=cos_config["secret_key"],
        Scheme="https",
        EnableOldDomain=not cos_config.get("use_internal", False),
        EnableInternalDomain=cos_config.get("use_internal", False),
    )
    return client_factory(config), cos_config


def parse_cos_last_modified(value, *, timezone):
    text = str(value or "").strip()
    if not text:
        return datetime.min.replace(tzinfo=timezone)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone)
    except ValueError:
        try:
            return datetime.strptime(text, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=ZoneInfo("UTC")).astimezone(timezone)
        except ValueError:
            return datetime.min.replace(tzinfo=timezone)


def list_cos_backup_objects(*, get_client, backup_prefix, parse_last_modified):
    client, cos_config = get_client()
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
            if not (filename.startswith(backup_prefix) and filename.endswith(".zip")):
                continue
            last_modified = item.get("LastModified") or ""
            rows.append(
                {
                    "key": key,
                    "filename": filename,
                    "size": int(item.get("Size") or 0),
                    "updated_at": parse_last_modified(last_modified).isoformat(),
                    "etag": str(item.get("ETag") or "").strip('"'),
                }
            )
        if str(response.get("IsTruncated", "")).lower() not in {"true", "1"}:
            break
        marker = response.get("NextMarker") or response.get("Marker") or ""
        if not marker:
            break
    return sorted(rows, key=lambda item: item["updated_at"], reverse=True)


def prune_cos_backup_objects(objects=None, *, get_client, list_objects, retention_count):
    client, cos_config = get_client()
    rows = objects if objects is not None else list_objects()
    stale_objects = rows[retention_count:]
    for item in stale_objects:
        client.delete_object(Bucket=cos_config["bucket"], Key=item["key"])
    return rows[:retention_count], stale_objects


def upload_backup_archive_to_cos(
    local_path, object_filename, *, get_environment, get_client, list_objects, prune_objects, clock
):
    cos_config = get_environment()
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
        client, cos_config = get_client()
        object_key = f"{cos_config['prefix']}{object_filename}"
        local_size = os.path.getsize(local_path)
        # SDK multipart upload avoids the 5GB single-PUT limit without loading the archive into RAM.
        client.upload_file(
            Bucket=cos_config["bucket"],
            Key=object_key,
            LocalFilePath=local_path,
            PartSize=16,
            MAXThread=2,
            EnableMD5=True,
        )
        metadata = client.head_object(Bucket=cos_config["bucket"], Key=object_key)
        if int(metadata.get("Content-Length", -1)) != local_size:
            raise RuntimeError("云端备份大小校验失败，旧备份未清理。")
        objects = list_objects()
        if not any(item["key"] == object_key and item["size"] == local_size for item in objects):
            raise RuntimeError("云端列表尚未确认新备份，旧备份未清理。")
        retained, removed = prune_objects(objects)
        return {
            "status": "success",
            "message": f"COS 上传成功，云端已保留最近 {len(retained)} 个备份。",
            "key": object_key,
            "bucket": cos_config["bucket"],
            "region": cos_config["region"],
            "uploaded_at": clock().isoformat(),
            "retained_count": len(retained),
            "removed_count": len(removed),
        }
    except Exception as exc:
        return {
            "status": "error",
            "message": f"COS 上传失败：{str(exc)}",
        }


def get_cos_backup_overview(config=None, *, get_public_status, list_objects, retention_count):
    status = get_public_status(config)
    backups = []
    if status["configured"] and status["sdk_available"]:
        try:
            backups = list_objects()[:retention_count]
        except Exception as exc:
            status = get_public_status(config, f"COS 备份列表读取失败：{str(exc)}")
    return status, backups
