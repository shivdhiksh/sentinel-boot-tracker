"""
Sentinel Security & Monitoring Module:
Implements safe security telemetry handlers:
/sessions, /security, /events, /audit, /lastboot, /health, /version.
Provides structured audit review, component health verification, and session state inspection.
"""
import os
import sys
import time
import socket
import platform
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

import psutil

import sentinel
from .config import BASE_DIR, LOG_FILE, AUTHORIZED_CHAT_ID, TELEGRAM_BOT_TOKEN, logger, sanitize, mask_chat_id
from .command_auth import (
    get_process_session_id,
    get_active_console_session_id,
    verify_interactive_session
)
from .system_info import get_username, get_os_info
from .location import is_system_context, load_location_cache


def execute_sessions() -> str:
    """
    Returns Windows session telemetry: process session ID, active console session ID,
    interactive desktop status, and active user sessions.
    """
    proc_sid = get_process_session_id()
    active_sid = get_active_console_session_id()
    is_interactive, reason = verify_interactive_session()
    current_user = get_username()
    is_sys = is_system_context()

    lines = [
        "👥 <b>WINDOWS SESSION TELEMETRY</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"👤 <b>Current User:</b> {current_user} (SYSTEM: {is_sys})",
        f"🆔 <b>Process Session ID:</b> <code>{proc_sid}</code>",
        f"🖥️ <b>Console Session ID:</b> <code>{active_sid}</code>",
        f"🪟 <b>Interactive Console:</b> {'🟢 Valid' if is_interactive else '🔴 Invalid (' + reason + ')'}\n",
        "<b>Active Logged-in Sessions:</b>"
    ]

    try:
        users = psutil.users()
        if users:
            for u in users:
                login_time = time.strftime("%Y-%m-%d %I:%M:%S %p", time.localtime(u.started)) if u.started else "Unknown"
                term = u.terminal or "Console"
                lines.append(f"• <b>{u.name}</b> (Terminal: <code>{term}</code>, Started: {login_time})")
        else:
            lines.append("• <i>No interactive users reported by psutil.</i>")
    except Exception as exc:
        lines.append(f"• <i>Error querying user sessions: {sanitize(str(exc))}</i>")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def execute_security() -> str:
    """
    Returns Sentinel security posture: authorization, engine allowlist,
    session monitor state, audit status, and secret redaction.
    """
    masked_chat = mask_chat_id(AUTHORIZED_CHAT_ID)
    auth_status = "🟢 Enforced" if AUTHORIZED_CHAT_ID else "🔴 Unconfigured"
    is_interactive, _ = verify_interactive_session()

    from .command_engine import ALLOWLIST
    allowlist_count = len(ALLOWLIST)

    lines = [
        "🛡️ <b>SENTINEL SECURITY POSTURE</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"🔒 <b>Single-Chat Authorization:</b> {auth_status}",
        f"🔑 <b>Authorized Chat ID:</b> <code>{masked_chat}</code>",
        f"📋 <b>Command Allowlist:</b> <code>{allowlist_count} allowed commands</code>",
        f"🛡️ <b>Update Deduplication:</b> Active (Bounded History)",
        f"🖥️ <b>Interactive Session Gate:</b> {'Active (User Console)' if is_interactive else 'Restricted'}",
        f"📁 <b>Restricted Filesystem Roots:</b> Enforced (Zero Traversal)",
        f"📝 <b>Command Audit Logging:</b> Active ({LOG_FILE.name})",
        f"🛑 <b>Token & Secret Redaction:</b> Active ([REDACTED_TOKEN])",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "🔒 <i>Zero arbitrary shell / PowerShell / eval execution.</i>"
    ]
    return "\n".join(lines)


def execute_events(limit: int = 5) -> str:
    """
    Returns recent Sentinel system/alert lifecycle events from error.log.
    """
    lines = [
        "📜 <b>RECENT SENTINEL EVENTS</b>",
        "━━━━━━━━━━━━━━━━━━━━━━"
    ]

    if not LOG_FILE.exists():
        lines.append("<i>No log file found.</i>")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)

    event_keywords = [
        "notification attempt",
        "notification sent successfully",
        "WTSSessionNotification",
        "Lock notification",
        "Unlock notification",
        "SessionMonitor acquired mutex",
        "Python startup process started",
        "Python shutdown process started",
        "Session monitor"
    ]

    matched_events: List[str] = []
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()

        for line in reversed(all_lines):
            line_clean = line.strip()
            if not line_clean:
                continue
            if any(k.lower() in line_clean.lower() for k in event_keywords):
                # Sanitize tokens and chat IDs
                sanitized_line = sanitize(line_clean)
                matched_events.append(sanitized_line)
                if len(matched_events) >= limit:
                    break
    except Exception as exc:
        lines.append(f"❌ Error reading events: {sanitize(str(exc))}")

    if matched_events:
        for ev in reversed(matched_events):
            # Trim date if already formatted in standard logger
            lines.append(f"• <code>{ev}</code>")
    else:
        lines.append("<i>No matching recent lifecycle events found.</i>")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def execute_audit(limit: int = 5) -> str:
    """
    Returns recent remote-command audit entries in a sanitized form.
    Never exposes plaintext tokens, credentials, or sensitive arguments.
    """
    lines = [
        "📋 <b>REMOTE COMMAND AUDIT TRAIL</b>",
        "━━━━━━━━━━━━━━━━━━━━━━"
    ]

    if not LOG_FILE.exists():
        lines.append("<i>No audit log file found.</i>")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)

    entries: List[Dict[str, str]] = []
    current_entry: Dict[str, str] = {}
    in_audit_block = False

    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()

        for line in all_lines:
            line_str = line.strip()
            if "Remote command" in line_str:
                if current_entry:
                    entries.append(current_entry)
                current_entry = {"header": line_str}
                in_audit_block = True
            elif in_audit_block:
                if line_str.startswith("User:"):
                    current_entry["user"] = line_str.split(":", 1)[1].strip()
                elif line_str.startswith("Chat ID:"):
                    current_entry["chat_id"] = line_str.split(":", 1)[1].strip()
                elif line_str.startswith("Command:"):
                    current_entry["command"] = line_str.split(":", 1)[1].strip()
                elif line_str.startswith("Result:"):
                    current_entry["result"] = line_str.split(":", 1)[1].strip()
                elif line_str.startswith("Reason:"):
                    current_entry["reason"] = line_str.split(":", 1)[1].strip()
                elif line_str.startswith("Timestamp:"):
                    current_entry["timestamp"] = line_str.split(":", 1)[1].strip()
                    entries.append(current_entry)
                    current_entry = {}
                    in_audit_block = False

        if current_entry:
            entries.append(current_entry)

    except Exception as exc:
        lines.append(f"❌ Error parsing audit log: {sanitize(str(exc))}")

    recent = entries[-limit:] if entries else []
    if recent:
        for e in recent:
            cmd = sanitize(e.get("command", "N/A"))
            res = e.get("result", "N/A")
            chat = sanitize(e.get("chat_id", "N/A"))
            ts = e.get("timestamp", "")
            icon = "✅" if res.upper() == "SUCCESS" else "❌"
            reason_str = f" ({sanitize(e['reason'])})" if e.get("reason") else ""
            lines.append(f"{icon} <code>{cmd}</code> — {res}{reason_str}")
            lines.append(f"   Chat: {chat} | {ts}\n")
    else:
        lines.append("<i>No remote command audit entries recorded yet.</i>")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🔒 <i>All chat IDs masked and tokens redacted.</i>")
    return "\n".join(lines)


def execute_lastboot() -> str:
    """
    Returns latest boot and startup telemetry available from the system.
    """
    try:
        boot_ts = psutil.boot_time()
        diff = max(0, int(time.time() - boot_ts))
        days = diff // 86400
        hrs = (diff % 86400) // 3600
        mins = (diff % 3600) // 60
        secs = diff % 60
        uptime = f"{days}d {hrs}h {mins}m {secs}s" if days > 0 else f"{hrs}h {mins}m {secs}s"
        boot_dt = time.strftime("%Y-%m-%d %I:%M:%S %p", time.localtime(boot_ts))
    except Exception as exc:
        boot_dt = "Unavailable"
        uptime = "Unavailable"

    lines = [
        "🚀 <b>SYSTEM BOOT TELEMETRY</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"🕒 <b>Last Boot Time:</b> {boot_dt}",
        f"⏱️ <b>System Uptime:</b> {uptime}",
        f"💻 <b>Device:</b> {socket.gethostname()}",
        f"🪟 <b>OS:</b> {get_os_info()}",
        "━━━━━━━━━━━━━━━━━━━━━━"
    ]
    return "\n".join(lines)


def execute_health() -> str:
    """
    Runs a Sentinel component-by-component self health check.
    """
    checks: List[Tuple[str, str, str]] = []  # (component, status, note)

    # 1. Config & Secrets
    if TELEGRAM_BOT_TOKEN:
        checks.append(("Telegram Bot Token", "PASS", "Configured"))
    else:
        checks.append(("Telegram Bot Token", "FAIL", "Missing from environment"))

    if AUTHORIZED_CHAT_ID:
        checks.append(("Authorized Chat ID", "PASS", f"Configured ({mask_chat_id(AUTHORIZED_CHAT_ID)})"))
    else:
        checks.append(("Authorized Chat ID", "FAIL", "Missing from environment"))

    # 2. Telegram API reachability (bounded socket test)
    try:
        sock = socket.create_connection(("api.telegram.org", 443), timeout=2.0)
        sock.close()
        checks.append(("Telegram API Connectivity", "PASS", "api.telegram.org reachable"))
    except Exception:
        checks.append(("Telegram API Connectivity", "WARN", "api.telegram.org unreachable / slow"))

    # 3. Log File & Storage
    try:
        test_write = False
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            test_write = True
        if test_write:
            checks.append(("Audit Log Storage", "PASS", f"{LOG_FILE.name} writable"))
    except Exception as exc:
        checks.append(("Audit Log Storage", "FAIL", sanitize(str(exc))))

    # 4. State Persistence Directory
    from .command_engine import STATE_FILE
    try:
        state_dir = STATE_FILE.parent
        if os.access(str(state_dir), os.W_OK):
            checks.append(("State File Storage", "PASS", f"{STATE_FILE.name} ready"))
        else:
            checks.append(("State File Storage", "FAIL", "Directory not writable"))
    except Exception as exc:
        checks.append(("State File Storage", "FAIL", sanitize(str(exc))))

    # 5. Session & Desktop Access
    proc_sid = get_process_session_id()
    if proc_sid != 0 and proc_sid != -1:
        checks.append(("Session Context", "PASS", f"Session {proc_sid} (User Console)"))
    elif proc_sid == 0:
        checks.append(("Session Context", "WARN", "Session 0 (SYSTEM / Non-interactive)"))
    else:
        checks.append(("Session Context", "WARN", "Unable to resolve session ID"))

    # 6. Geolocation Cache
    cached_loc = load_location_cache()
    if cached_loc and not cached_loc.get("is_stale", True):
        checks.append(("Location Cache", "PASS", f"Fresh ({cached_loc.get('age_string')})"))
    elif cached_loc:
        checks.append(("Location Cache", "INFO", f"Expired ({cached_loc.get('age_string')})"))
    else:
        checks.append(("Location Cache", "INFO", "No cached location file"))

    # Calculate overall health
    has_fail = any(s == "FAIL" for _, s, _ in checks)
    has_warn = any(s == "WARN" for _, s, _ in checks)

    if has_fail:
        overall = "🔴 UNHEALTHY / CRITICAL CONFIG MISSING"
    elif has_warn:
        overall = "🟡 DEGRADED / NETWORK LIMITATION"
    else:
        overall = "🟢 HEALTHY / ALL SYSTEMS OPERATIONAL"

    lines = [
        "🩺 <b>SENTINEL SELF-HEALTH CHECK</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"<b>Status:</b> {overall}\n"
    ]

    for comp, st, note in checks:
        icon = "✅" if st == "PASS" else ("⚠️" if st in ["WARN", "INFO"] else "❌")
        lines.append(f"{icon} <b>{comp}:</b> {st} — <i>{note}</i>")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def execute_version() -> str:
    """
    Returns Sentinel version and core dependencies versions.
    """
    sentinel_ver = getattr(sentinel, "__version__", "0.5.0")
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    os_name = get_os_info()

    # Query library versions
    psutil_ver = getattr(psutil, "__version__", "N/A")
    try:
        import requests
        requests_ver = getattr(requests, "__version__", "N/A")
    except ImportError:
        requests_ver = "N/A"

    try:
        import PySide6
        pyside_ver = getattr(PySide6, "__version__", "Available")
    except ImportError:
        pyside_ver = "Not installed"

    lines = [
        "🚀 <b>SENTINEL VERSION MANIFEST</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"🛡️ <b>Sentinel:</b> <code>v{sentinel_ver}</code>",
        f"🐍 <b>Python Runtime:</b> <code>{py_ver}</code>",
        f"🪟 <b>Operating System:</b> {os_name}",
        f"📦 <b>psutil:</b> <code>{psutil_ver}</code>",
        f"📦 <b>requests:</b> <code>{requests_ver}</code>",
        f"📦 <b>PySide6:</b> <code>{pyside_ver}</code>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "🔒 <i>Sentinel Boot Tracker & Remote Command Engine</i>"
    ]
    return "\n".join(lines)
