import sys
import traceback
from pathlib import Path

# Add project root to sys.path if not present
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from sentinel.telegram import send_telegram_alert
    from sentinel.session_monitor import ensure_session_monitor_running
except Exception as e:
    with open(BASE_DIR / "error.log", "a", encoding="utf-8") as f:
        f.write(f"\n[CRITICAL IMPORT ERROR] {e}\n{traceback.format_exc()}\n")
    sys.exit(1)

if __name__ == "__main__":
    action = sys.argv[1].strip().lower() if len(sys.argv) > 1 else "startup"
    
    if action == "session_monitor":
        try:
            from sentinel.session_monitor import run_session_monitor
            run_session_monitor()
        except Exception as e:
            with open(BASE_DIR / "error.log", "a", encoding="utf-8") as f:
                f.write(f"\n[SESSION MONITOR CRASH] {e}\n{traceback.format_exc()}\n")
    elif action == "startup":
        send_telegram_alert("startup")
        ensure_session_monitor_running()
    elif action in ["shutdown", "lock", "unlock"]:
        send_telegram_alert(action)
    else:
        send_telegram_alert("startup")
        ensure_session_monitor_running()
