"""
Sentinel Power Actions Module:
Implements safe workstation power state controls:
/lock, /shutdown, /confirm_shutdown, /restart, /confirm_restart.
Enforces strict 2-step confirmations, bounded monotonic 30s TTL, and single-chat binding.
"""
import time
import threading
import subprocess
from typing import Tuple, Optional, Dict, Any

from .config import logger, sanitize
# Reuse existing v0.4 lock and shutdown implementations to preserve exact state and regression safety
from .remote_actions import (
    execute_lock,
    execute_shutdown_request,
    execute_confirm_shutdown,
)

_restart_lock = threading.Lock()
_pending_restart: Optional[Dict[str, Any]] = None

CONFIRMATION_TIMEOUT_SECONDS = 30.0


def execute_restart_request(chat_id: Any) -> str:
    """Initiates 2-step restart confirmation with monotonic 30s TTL."""
    global _pending_restart
    with _restart_lock:
        _pending_restart = {
            "chat_id": str(chat_id).strip(),
            "expires_monotonic": time.monotonic() + CONFIRMATION_TIMEOUT_SECONDS
        }
    return (
        "⚠️ <b>Confirm restart:</b>\n"
        "Reply <code>/confirm_restart</code> within 30 seconds."
    )


def execute_confirm_restart(chat_id: Any) -> Tuple[bool, str]:
    """
    Validates pending restart confirmation and initiates Windows restart.
    Returns acknowledgement string BEFORE initiating reboot.
    """
    global _pending_restart
    with _restart_lock:
        if not _pending_restart:
            return False, "❌ No active restart request found."

        pending_chat = _pending_restart.get("chat_id")
        expires_at = _pending_restart.get("expires_monotonic", 0.0)

        if str(chat_id).strip() != pending_chat:
            return False, "❌ Confirmation chat ID mismatch."

        if time.monotonic() > expires_at:
            _pending_restart = None
            return False, "❌ Restart confirmation expired (30s window exceeded)."

        # Valid confirmation -> clear pending
        _pending_restart = None

    # Schedule restart via subprocess after brief delay so Telegram acknowledgement can transmit
    def _deferred_restart():
        time.sleep(1.5)
        try:
            subprocess.Popen(
                ["shutdown.exe", "/r", "/t", "5", "/c", "Sentinel remote restart initiated"],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception as exc:
            logger.error(f"Failed to trigger restart via shutdown.exe: {sanitize(str(exc))}")

    threading.Thread(target=_deferred_restart, daemon=True).start()
    return True, "🔄 Restart command accepted."
