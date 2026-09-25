"""
Sentinel Remote Actions Engine:
Implements safe, allowlisted remote handlers for:
/status, /location, /lock, /shutdown, /confirm_shutdown, /screenshot, /processes, /camera.
Zero shell evaluation, strict session validation, and monotonic confirmation state.
"""
import os
import sys
import time
import socket
import tempfile
import subprocess
import threading
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

import psutil
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QGuiApplication

import sentinel
from .config import logger, sanitize, BASE_DIR
from .system_info import get_battery_info, get_os_info
from .network import get_network_info
from .location import get_location_telemetry, load_location_cache
from .command_auth import verify_interactive_session

# Thread-safe in-memory state for 2-step shutdown confirmation
_shutdown_lock = threading.Lock()
_pending_shutdown: Optional[Dict[str, Any]] = None

def execute_status() -> str:
    """Gathers comprehensive Sentinel and device status."""
    try:
        cpu = f"{psutil.cpu_percent(interval=0.2):.1f}%"
    except Exception:
        cpu = "Unavailable"

    try:
        vm = psutil.virtual_memory()
        ram = f"{vm.percent}% ({vm.used / (1024**3):.1f} / {vm.total / (1024**3):.1f} GB)"
    except Exception:
        ram = "Unavailable"

    battery_data = get_battery_info()
    battery = battery_data.get("percent", "Unavailable")
    power = battery_data.get("power_source", "Unavailable")

    try:
        boot_ts = psutil.boot_time()
        diff = max(0, int(time.time() - boot_ts))
        days = diff // 86400
        hrs = (diff % 86400) // 3600
        mins = (diff % 3600) // 60
        uptime = f"{days}d {hrs}h {mins}m" if days > 0 else f"{hrs}h {mins}m"
    except Exception:
        uptime = "Unavailable"

    os_info = get_os_info()
    hostname = socket.gethostname()

    try:
        net = get_network_info(timeout=3.0)
        public_ip = net.get("ip", "Unavailable")
        net_status = "Connected" if public_ip != "Unavailable" else "Offline / Limited"
    except Exception:
        public_ip = "Unavailable"
        net_status = "Error querying network"

    version = getattr(sentinel, "__version__", "0.4.0")

    lines = [
        "🛡️ <b>SENTINEL STATUS — ONLINE</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"💻 <b>Hostname:</b> {hostname}",
        f"🪟 <b>OS:</b> {os_info}",
        f"⏱️ <b>Uptime:</b> {uptime}",
        f"🚀 <b>Sentinel Version:</b> v{version}\n",
        f"⚙️ <b>CPU Load:</b> {cpu}",
        f"🧠 <b>RAM Usage:</b> {ram}",
        f"🔋 <b>Battery:</b> {battery}",
        f"⚡ <b>Power Source:</b> {power}\n",
        f"🌐 <b>Network Status:</b> {net_status}",
        f"📡 <b>Public IP:</b> {public_ip}",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "🟢 System monitor & remote engine active"
    ]
    return "\n".join(lines)


def execute_location() -> str:
    """
    Executes location resolution with strict timeout guard.
    Guarantees slow COM/WinRT calls cannot permanently block the Telegram polling thread.
    """
    telemetry = None
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(get_location_telemetry, timeout=3.0)
            telemetry = future.result(timeout=5.5)
    except (FuturesTimeoutError, Exception) as exc:
        logger.warning(f"Location resolution timed out or encountered error: {sanitize(str(exc))}")
        # Fast fallback: check cache first, then IP
        cached = load_location_cache()
        if cached and not cached.get("is_stale", True):
            telemetry = {
                "location_tier": "cached",
                "latitude": cached.get("latitude"),
                "longitude": cached.get("longitude"),
                "accuracy_meters": cached.get("accuracy_meters"),
                "source": cached.get("source", "Cache"),
                "maps_url": f"https://www.google.com/maps?q={cached.get('latitude')},{cached.get('longitude')}",
                "age_string": cached.get("age_string", "cached"),
            }
        else:
            net = get_network_info(timeout=2.5)
            telemetry = {
                "location_tier": "ip_fallback",
                "location_name": net.get("location", "Unavailable"),
                "latitude": net.get("latitude"),
                "longitude": net.get("longitude"),
                "accuracy_meters": None,
                "source": "IP address",
                "maps_url": net.get("maps_url")
            }

    tier = telemetry.get("location_tier", "ip_fallback")
    lat = telemetry.get("latitude")
    lon = telemetry.get("longitude")
    source = telemetry.get("source", "Unknown")
    accuracy_m = telemetry.get("accuracy_meters")
    age_str = telemetry.get("age_string", "live")
    maps_url = telemetry.get("maps_url")

    lines = [
        "📍 <b>SENTINEL LOCATION REPORT</b>",
        "━━━━━━━━━━━━━━━━━━━━━━"
    ]

    if tier == "windows_live":
        acc_str = f"~{int(round(accuracy_m))} m" if accuracy_m is not None else "High"
        lines.append(f"🟢 <b>Tier:</b> Windows Live (Tier 1)")
        if lat is not None and lon is not None:
            lines.append(f"Latitude: <code>{lat:.6f}</code>")
            lines.append(f"Longitude: <code>{lon:.6f}</code>")
        lines.append(f"🎯 <b>Accuracy:</b> {acc_str}")
        lines.append(f"📡 <b>Source:</b> {source}")
    elif tier == "cached":
        acc_str = f"~{int(round(accuracy_m))} m" if accuracy_m is not None else "High"
        lines.append(f"🟡 <b>Tier:</b> Cached Location (Tier 2)")
        if lat is not None and lon is not None:
            lines.append(f"Latitude: <code>{lat:.6f}</code>")
            lines.append(f"Longitude: <code>{lon:.6f}</code>")
        lines.append(f"🎯 <b>Accuracy:</b> {acc_str}")
        lines.append(f"📡 <b>Source:</b> {source}")
        lines.append(f"🕒 <b>Cache Age:</b> {age_str}")
    else:  # ip_fallback
        loc_name = telemetry.get("location_name", "Unavailable")
        lines.append(f"📍 <b>Tier:</b> IP Geolocation Fallback (Tier 3)")
        lines.append(f"Region: {loc_name}")
        lines.append(f"📡 <b>Source:</b> {source}")
        lines.append(f"🎯 <b>Accuracy:</b> Approximate")
        lines.append("⚠️ <i>IP-based location is not precise.</i>")

    if maps_url:
        lines.append(f"\n🗺️ <b>Google Maps:</b>\n{maps_url}")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def execute_lock() -> str:
    """Locks the Windows workstation using Win32 LockWorkStation."""
    import ctypes
    res = ctypes.windll.user32.LockWorkStation()
    if res != 0:
        return "✅ Workstation locked"
    else:
        err = ctypes.GetLastError()
        return f"❌ Failed to lock workstation (Win32 Error: {err})"


def execute_shutdown_request(chat_id: str) -> str:
    """Initiates 2-step shutdown confirmation with monotonic 30s TTL."""
    global _pending_shutdown
    with _shutdown_lock:
        _pending_shutdown = {
            "chat_id": str(chat_id).strip(),
            "expires_monotonic": time.monotonic() + 30.0
        }
    return (
        "⚠️ <b>Confirm shutdown:</b>\n"
        "Reply <code>/confirm_shutdown</code> within 30 seconds."
    )


def execute_confirm_shutdown(chat_id: str) -> Tuple[bool, str]:
    """
    Validates pending confirmation and initiates Windows shutdown.
    Returns acknowledgement string BEFORE initiating power-off.
    """
    global _pending_shutdown
    with _shutdown_lock:
        if not _pending_shutdown:
            return False, "❌ No active shutdown request found."

        pending_chat = _pending_shutdown.get("chat_id")
        expires_at = _pending_shutdown.get("expires_monotonic", 0.0)

        if str(chat_id).strip() != pending_chat:
            return False, "❌ Confirmation chat ID mismatch."

        if time.monotonic() > expires_at:
            _pending_shutdown = None
            return False, "❌ Shutdown confirmation expired (30s window exceeded)."

        # Valid confirmation
        _pending_shutdown = None

    # Schedule shutdown via subprocess after brief delay so Telegram acknowledgement can transmit
    def _deferred_shutdown():
        time.sleep(1.5)
        try:
            subprocess.Popen(
                ["shutdown.exe", "/s", "/t", "5", "/c", "Sentinel remote shutdown initiated"],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception as exc:
            logger.error(f"Failed to trigger shutdown.exe: {sanitize(str(exc))}")

    threading.Thread(target=_deferred_shutdown, daemon=True).start()
    return True, "🛑 Shutdown command accepted."


def execute_screenshot() -> Tuple[Optional[str], str]:
    """
    Captures primary desktop screenshot.
    Enforces process session ID != 0 and == active interactive console session.
    Returns (temp_file_path, caption_or_error_message).
    """
    valid, reason = verify_interactive_session()
    if not valid:
        return None, f"❌ Screenshot rejected: {reason}"

    temp_path = None
    try:
        app = QApplication.instance() or QApplication(sys.argv)
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return None, "❌ Screenshot failed: No active primary screen detected."

        pixmap = screen.grabWindow(0)
        if pixmap.isNull():
            return None, "❌ Screenshot failed: Grabbed pixmap is null."

        fd, temp_path = tempfile.mkstemp(suffix=".png", prefix="sentinel_scr_")
        os.close(fd)

        if pixmap.save(temp_path, "PNG"):
            return temp_path, "🖥️ <b>Desktop Screenshot</b>"
        else:
            return None, "❌ Screenshot failed: Unable to save PNG to disk."
    except Exception as exc:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        return None, f"❌ Screenshot error: {sanitize(str(exc))}"


def execute_processes() -> str:
    """
    Returns top 20 processes sorted by memory usage.
    STRICTLY excludes command-line arguments to prevent credential exposure.
    """
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
        try:
            info = p.info
            name = info.get('name') or "Unknown"
            pid = info.get('pid') or 0
            cpu = info.get('cpu_percent') or 0.0
            mem_bytes = info['memory_info'].rss if info.get('memory_info') else 0
            mem_mb = mem_bytes / (1024 * 1024)
            procs.append((pid, name, cpu, mem_mb))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    # Sort descending by RAM usage
    procs.sort(key=lambda x: x[3], reverse=True)
    top20 = procs[:20]

    lines = [
        "📋 <b>ACTIVE PROCESSES (Top 20 by RAM)</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "<pre>",
        f"{'PID':<7} {'NAME':<20} {'RAM':>9} {'CPU':>6}",
        f"{'-'*7} {'-'*20} {'-'*9} {'-'*6}"
    ]

    for pid, name, cpu, mem in top20:
        trunc_name = (name[:18] + '..') if len(name) > 20 else name
        lines.append(f"{pid:<7} {trunc_name:<20} {mem:>7.1f}MB {cpu:>5.1f}%")

    lines.append("</pre>")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🔒 <i>Command line arguments omitted for security.</i>")
    return "\n".join(lines)


def execute_camera(test_mode: Optional[str] = None) -> Tuple[Optional[str], str]:
    """
    Executes consent-based camera capture.
    Enforces process session ID != 0 and == active interactive console session.
    Spawns sentinel.consent_camera as an isolated UI subprocess in the user session.
    Returns (temp_image_path, caption_or_error_message).
    """
    valid, reason = verify_interactive_session()
    if not valid:
        return None, f"❌ Camera rejected: {reason}"

    fd, temp_path = tempfile.mkstemp(suffix=".jpg", prefix="sentinel_cam_")
    os.close(fd)

    success = False
    try:
        python_exe = sys.executable
        cmd = [python_exe, "-m", "sentinel.consent_camera", temp_path, "--timeout", "30"]
        if test_mode:
            cmd.extend(["--test-mode", test_mode])

        proc = subprocess.run(
            cmd,
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=40
        )

        exit_code = proc.returncode
        if exit_code == 0:
            if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                success = True
                return temp_path, "📷 <b>Camera Snapshot</b> (Explicitly Approved)"
            else:
                return None, "❌ Camera error: Captured file was empty."
        elif exit_code == 1:
            return None, "⚠️ Camera capture declined: Local user clicked Deny."
        elif exit_code == 2:
            return None, "⚠️ Camera request timed out without local user consent."
        else:
            err_output = proc.stdout.strip() or proc.stderr.strip() or f"Exit code {exit_code}"
            return None, f"❌ Camera hardware/driver error: {sanitize(err_output)}"

    except subprocess.TimeoutExpired:
        return None, "⚠️ Camera request timed out."
    except Exception as exc:
        return None, f"❌ Camera exception: {sanitize(str(exc))}"
    finally:
        # If capture was not successful or an error/denial occurred, remove temp file immediately
        if not success and temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as exc:
                logger.warning(f"Could not remove temp camera file: {sanitize(str(exc))}")
