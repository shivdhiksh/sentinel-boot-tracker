"""
Sentinel Agent Actions Module:
Implements safe Sentinel process diagnostics and lifecycle controls:
/agent, /restart_agent.
Zero arbitrary shell commands, strictly bounded restart sequence,
and preservation of the persistent SessionMonitor architecture.
"""
import os
import sys
import time
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

import psutil

from .config import BASE_DIR, logger, sanitize
from .command_auth import get_process_session_id, get_active_console_session_id
from .system_info import get_username

# Thread-safe lock and debounce flag to prevent duplicate restart threads
_agent_restart_lock = threading.Lock()
_agent_restart_pending = False


def execute_agent() -> str:
    """
    Returns Sentinel process telemetry, resource usage, session IDs,
    and state file health without exposing tokens or secrets.
    """
    pid = os.getpid()
    try:
        proc = psutil.Process(pid)
        ppid = proc.ppid()
        create_time = proc.create_time()
        start_dt = time.strftime("%Y-%m-%d %I:%M:%S %p", time.localtime(create_time))
        up_secs = max(0, int(time.time() - create_time))
        hrs = up_secs // 3600
        mins = (up_secs % 3600) // 60
        secs = up_secs % 60
        proc_uptime = f"{hrs}h {mins}m {secs}s"

        mem_info = proc.memory_info()
        rss_mb = mem_info.rss / (1024 * 1024)
        num_threads = proc.num_threads()
        cpu_pct = proc.cpu_percent(interval=0.1)
    except Exception as exc:
        logger.warning(f"execute_agent psutil error: {sanitize(str(exc))}")
        ppid = "N/A"
        start_dt = "N/A"
        proc_uptime = "N/A"
        rss_mb = 0.0
        num_threads = 1
        cpu_pct = 0.0

    proc_sid = get_process_session_id()
    active_sid = get_active_console_session_id()
    username = get_username()

    # Check update state file
    from .command_engine import STATE_FILE
    state_status = "Not found"
    if STATE_FILE.exists():
        state_status = f"Active ({STATE_FILE.stat().st_size} bytes)"

    lines = [
        "🤖 <b>SENTINEL AGENT DIAGNOSTICS</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"🆔 <b>Process ID (PID):</b> <code>{pid}</code> (PPID: {ppid})",
        f"👤 <b>Context User:</b> {username}",
        f"🖥️ <b>Process Session ID:</b> <code>{proc_sid}</code> (Console: {active_sid})",
        f"🕒 <b>Process Started:</b> {start_dt}",
        f"⏱️ <b>Agent Uptime:</b> {proc_uptime}",
        f"🧠 <b>Memory Usage (RSS):</b> <code>{rss_mb:.1f} MB</code>",
        f"⚙️ <b>CPU Load:</b> <code>{cpu_pct:.1f}%</code>",
        f"🧵 <b>Active Threads:</b> <code>{num_threads}</code>",
        f"💾 <b>State Persistence:</b> {state_status}",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "🟢 <i>Session monitor & background polling active.</i>"
    ]
    return "\n".join(lines)


def execute_restart_agent() -> str:
    """
    Safely restarts the Sentinel agent.
    Schedules a deferred decoupled process to re-launch power_monitor.py session_monitor
    after a 1.5s delay to allow the Telegram confirmation message to transmit,
    then terminates the current process to release the single-instance mutex.
    Enforces atomic debouncing to prevent duplicate restart workers.
    """
    global _agent_restart_pending
    with _agent_restart_lock:
        if _agent_restart_pending:
            return "⚠️ <b>Sentinel Agent:</b> Restart already in progress."
        _agent_restart_pending = True

    def _deferred_restart():
        time.sleep(1.5)
        try:
            pythonw_path = sys.executable.replace("python.exe", "pythonw.exe")
            if not Path(pythonw_path).exists():
                pythonw_path = sys.executable

            script_path = str(BASE_DIR / "power_monitor.py")
            cmd = [
                pythonw_path,
                "-c",
                (
                    "import time, subprocess, sys; "
                    "time.sleep(1.0); "
                    f"subprocess.Popen([sys.executable, r'{script_path}', 'session_monitor'])"
                )
            ]
            subprocess.Popen(
                cmd,
                cwd=str(BASE_DIR),
                creationflags=(
                    subprocess.CREATE_NO_WINDOW |
                    subprocess.DETACHED_PROCESS |
                    subprocess.CREATE_NEW_PROCESS_GROUP
                )
            )
            # Exit current process cleanly so the mutex is freed for the new instance
            os._exit(0)
        except Exception as exc:
            logger.error(f"Failed to restart Sentinel agent: {sanitize(str(exc))}")
            with _agent_restart_lock:
                global _agent_restart_pending
                _agent_restart_pending = False

    threading.Thread(target=_deferred_restart, daemon=True).start()
    return "🔄 <b>Sentinel Agent:</b> Restart initiated. Polling will resume shortly."
