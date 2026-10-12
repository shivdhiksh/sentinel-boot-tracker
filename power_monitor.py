import os
import sys
import traceback
from pathlib import Path

# Add project root to sys.path if not present
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from sentinel.config import logger, sanitize
    from sentinel.location import is_system_context
    from sentinel.telegram import send_telegram_alert
    from sentinel.session_monitor import ensure_session_monitor_running
except Exception as e:
    with open(BASE_DIR / "error.log", "a", encoding="utf-8") as f:
        f.write(f"\n[CRITICAL IMPORT ERROR] {e}\n{traceback.format_exc()}\n")
    sys.exit(1)

if __name__ == "__main__":
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    action = sys.argv[1].strip().lower() if len(sys.argv) > 1 else "startup"
    
    is_sys = is_system_context()
    user = os.getenv("USERNAME", "Unknown")
    logger.info(f"Python {action} process started (PID: {os.getpid()}, Context: {user}, SYSTEM: {is_sys})")
    
    if action == "session_monitor":
        try:
            from sentinel.session_monitor import run_session_monitor
            run_session_monitor()
        except Exception as e:
            with open(BASE_DIR / "error.log", "a", encoding="utf-8") as f:
                f.write(f"\n[SESSION MONITOR CRASH] {e}\n{traceback.format_exc()}\n")
    elif action == "command_engine":
        try:
            from sentinel.command_engine import CommandEngine
            engine = CommandEngine()
            engine.run_polling_loop()
        except Exception as e:
            with open(BASE_DIR / "error.log", "a", encoding="utf-8") as f:
                f.write(f"\n[COMMAND ENGINE CRASH] {e}\n{traceback.format_exc()}\n")
    elif action == "startup":
        send_telegram_alert("startup")
        ensure_session_monitor_running()
    elif action in ["camera-enable", "enable-camera"]:
        from sentinel.settings import set_remote_camera_enabled
        if set_remote_camera_enabled(True):
            print("[+] Sentinel Remote Camera: ENABLED")
            print("Authorized Telegram /camera requests will now capture a single photo automatically.")
            print("An on-screen active indicator will visibly display on your desktop during capture.")
        else:
            print("[-] Failed to update Remote Camera setting.")
            sys.exit(1)
    elif action in ["camera-disable", "disable-camera"]:
        from sentinel.settings import set_remote_camera_enabled
        if set_remote_camera_enabled(False):
            print("[*] Sentinel Remote Camera: DISABLED")
            print("All incoming Telegram /camera requests will be safely rejected.")
        else:
            print("[-] Failed to update Remote Camera setting.")
            sys.exit(1)
    elif action in ["camera-status", "status-camera"]:
        from sentinel.settings import get_camera_settings_summary
        summary = get_camera_settings_summary()
        enabled = summary["remote_camera_enabled"]
        updated = summary["updated_at"]
        tag = "[ENABLED]" if enabled else "[DISABLED]"
        print(f"{tag} Remote Camera: {'Enabled (Automatic capture active)' if enabled else 'Disabled (Opt-in required)'}")
        print(f"[*] Last Modified: {updated}")
    elif action in ["shutdown", "lock", "unlock"]:
        send_telegram_alert(action)
    else:
        send_telegram_alert("startup")
        ensure_session_monitor_running()

