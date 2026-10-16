"""Backup configuration values and scheduling calculations, without I/O or workers."""
from datetime import datetime, timedelta
import os
import re


BACKUP_FREQUENCY_INTERVALS = {
    "off": None,
    "hourly": timedelta(hours=1),
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
    "monthly": timedelta(days=30),
}


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


def normalize_backup_destination_path(value, default_directory):
    raw_value = str(value or "").strip()
    if not raw_value:
        return os.path.abspath(default_directory)
    if os.path.isabs(raw_value):
        return os.path.abspath(raw_value)
    return os.path.abspath(os.path.join(default_directory, raw_value))


def get_default_backup_config(default_directory):
    return {
        "destination_path": os.path.abspath(default_directory),
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


def normalize_backup_config(config, default_directory):
    """Normalize an already merged config, preserving metadata and validation order."""
    normalized = dict(config)
    normalized["destination_path"] = normalize_backup_destination_path(
        normalized.get("destination_path"), default_directory
    )
    if normalized.get("frequency") not in BACKUP_FREQUENCY_INTERVALS:
        normalized["frequency"] = "off"
    normalized["scheduled_time"] = normalize_backup_scheduled_time(normalized.get("scheduled_time"))
    if normalized.get("frequency") == "off":
        normalized["next_auto_run_at"] = None
    return normalized


def calculate_next_auto_run_at(config, from_time=None, *, clock, timezone):
    frequency = config.get("frequency")
    interval = BACKUP_FREQUENCY_INTERVALS.get(frequency)
    if not interval:
        return None
    now = (from_time or clock()).astimezone(timezone)

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


def get_backup_next_run_at(config, *, clock, timezone):
    if config.get("frequency") == "off":
        return None
    saved_next_run = parse_backup_time(config.get("next_auto_run_at"))
    if saved_next_run:
        return saved_next_run.astimezone(timezone).isoformat()
    return calculate_next_auto_run_at(config, clock=clock, timezone=timezone)
