"""
Sentinel Local Settings Management:
Stores local, owner-controlled preferences (such as Remote Camera Opt-In).
Enforces default-disabled posture, atomic writes, safe parsing fallback,
and strict exclusion of secrets and authentication tokens.
"""
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from .config import BASE_DIR, logger, sanitize

SETTINGS_FILE: Path = BASE_DIR / ".settings.json"

def is_remote_camera_enabled() -> bool:
    """
    Checks whether the laptop owner has explicitly opted in to Remote Camera.
    Returns False by default if settings file is missing, unreadable, or invalid.
    """
    if not SETTINGS_FILE.exists():
        return False

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return bool(data.get("remote_camera_enabled", False))
        return False
    except Exception as exc:
        logger.warning(f"Failed to read settings file safely (defaulting to disabled): {sanitize(str(exc))}")
        return False

def set_remote_camera_enabled(enabled: bool) -> bool:
    """
    Atomically updates the persistent Remote Camera preference.
    Controlled strictly via local owner actions.
    """
    try:
        data: Dict[str, Any] = {}
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        data = loaded
            except Exception:
                data = {}

        data["remote_camera_enabled"] = bool(enabled)
        data["updated_at"] = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")

        tmp_path = SETTINGS_FILE.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        os.replace(tmp_path, SETTINGS_FILE)
        logger.info(f"Local settings updated: remote_camera_enabled={enabled}")
        return True
    except Exception as exc:
        logger.error(f"Failed to save settings file: {sanitize(str(exc))}")
        return False

def get_camera_settings_summary() -> Dict[str, Any]:
    """Returns a dictionary summary of camera settings for diagnostics."""
    enabled = is_remote_camera_enabled()
    updated_at = "Never"
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    updated_at = data.get("updated_at", "Unknown")
        except Exception:
            pass
    return {
        "remote_camera_enabled": enabled,
        "updated_at": updated_at
    }
