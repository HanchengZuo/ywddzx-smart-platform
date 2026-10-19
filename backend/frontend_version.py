"""Use live frontend metadata in development without changing deployed versions."""

import json
import os
from pathlib import Path
import re


def development_frontend_version(fallback, *, environ=None):
    env = os.environ if environ is None else environ
    if env.get("APP_ENV", "development").strip().lower() != "development":
        return fallback

    package_path = env.get("APP_FRONTEND_PACKAGE_PATH") or (
        Path(__file__).resolve().parent.parent / "frontend" / "package.json"
    )
    try:
        with open(package_path, encoding="utf-8") as package_file:
            package = json.load(package_file)
        version = package.get("version") if isinstance(package, dict) else None
        if isinstance(version, str) and re.fullmatch(r"v?\d+\.\d+(?:\.\d+)?", version.strip(), re.I):
            return version.strip()
    except (OSError, ValueError, UnicodeError):
        pass
    return fallback
