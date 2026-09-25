"""
Sentinel Authentication & Session Verification Module:
Enforces single-authorized Telegram chat access, masked audit identities,
and strict Windows interactive console session validation.
"""
import os
import ctypes
from ctypes import wintypes
from typing import Any, Tuple, Optional
from .config import AUTHORIZED_CHAT_ID, mask_chat_id, logger, sanitize

kernel32 = ctypes.windll.kernel32

def is_authorized(chat_id: Any) -> bool:
    """
    Validates whether the incoming Telegram chat ID matches the configured AUTHORIZED_CHAT_ID.
    Type-safe string comparison to handle integer or string chat IDs.
    """
    if not AUTHORIZED_CHAT_ID:
        logger.error("No AUTHORIZED_CHAT_ID or TELEGRAM_CHAT_ID configured. Rejecting all remote commands.")
        return False
    
    incoming_str = str(chat_id).strip()
    authorized_str = str(AUTHORIZED_CHAT_ID).strip()
    
    return incoming_str == authorized_str

def get_process_session_id() -> int:
    """Returns the Windows Session ID of the current process."""
    session_id = wintypes.DWORD()
    if kernel32.ProcessIdToSessionId(kernel32.GetCurrentProcessId(), ctypes.byref(session_id)):
        return int(session_id.value)
    return -1

def get_active_console_session_id() -> int:
    """Returns the Windows Session ID of the currently attached physical/interactive console."""
    return int(kernel32.WTSGetActiveConsoleSessionId())

def verify_interactive_session() -> Tuple[bool, str]:
    """
    Enforces that interactive actions (such as /screenshot and /camera):
    1. Do NOT execute from Session 0 (SYSTEM / Service context).
    2. Execute exclusively within the active interactive console user session.
    
    Returns:
        (is_valid, rejection_reason)
    """
    proc_sid = get_process_session_id()
    active_sid = get_active_console_session_id()

    if proc_sid == 0:
        return False, "Process is running in Session 0 (SYSTEM/Service context). Interactive desktop unavailable."
    
    if proc_sid == -1:
        return False, "Failed to resolve current process Session ID."

    if active_sid == 0xFFFFFFFF:
        return False, "No active console session currently attached to the workstation."

    if proc_sid != active_sid:
        return False, f"Process Session ID ({proc_sid}) does not match active interactive console Session ID ({active_sid})."

    return True, ""
