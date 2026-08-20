import sys
from pathlib import Path

# Add project root to sys.path if not present
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sentinel.telegram import send_telegram_alert
from sentinel.session_monitor import ensure_session_monitor_running

if __name__ == "__main__":
    action = sys.argv[1].strip().lower() if len(sys.argv) > 1 else "startup"
    
    if action == "session_monitor":
        from sentinel.session_monitor import run_session_monitor
        run_session_monitor()
    elif action == "startup":
        send_telegram_alert("startup")
        ensure_session_monitor_running()
    elif action in ["shutdown", "lock", "unlock"]:
        send_telegram_alert(action)
    else:
        send_telegram_alert("startup")
        ensure_session_monitor_running()
