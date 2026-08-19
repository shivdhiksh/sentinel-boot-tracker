import sys
import os
import time
import socket
import logging
from datetime import datetime
from pathlib import Path
import requests
from dotenv import load_dotenv

# Set up base directory and load environment variables
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
LOG_FILE = BASE_DIR / "error.log"

# Configure logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.ERROR,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %I:%M:%S %p"
)

def sanitize(text: str) -> str:
    """Strips sensitive bot tokens from logs and terminal outputs."""
    if TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN in text:
        return text.replace(TELEGRAM_BOT_TOKEN, "[REDACTED_TOKEN]")
    return text

def send_telegram_alert(event_type: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        err_msg = "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID in environment."
        logging.error(err_msg)
        print(f"Error: {err_msg}")
        return False

    is_startup = event_type.lower() == "startup"
    icon = "🚀" if is_startup else "🛑"
    action_label = "System Startup" if is_startup else "System Shutdown"
    
    timestamp = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    hostname = socket.gethostname()

    message = (
        f"{icon} <b>ASUS TUF Alert: {action_label}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💻 <b>Device:</b> ASUS TUF A15 ({hostname})\n"
        f"🕒 <b>Time:</b> {timestamp}\n"
        f"⚡ <b>Status:</b> Event triggered and confirmed"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }

    # Configuration for retry loops
    max_retries = 10 if is_startup else 3
    retry_delay = 5 if is_startup else 1

    print(f"[*] Sending {event_type} notification to Telegram (Chat ID: {TELEGRAM_CHAT_ID})...")

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(url, json=payload, timeout=8)
            
            # Extract granular error description directly from Telegram's response
            if not response.ok:
                try:
                    resp_json = response.json()
                    error_detail = resp_json.get("description", response.text)
                except Exception:
                    error_detail = response.text
                err_text = sanitize(f"HTTP {response.status_code} ({error_detail})")
                logging.error(f"Attempt {attempt}/{max_retries} failed for {event_type}: {err_text}")
                print(f"[!] Attempt {attempt}/{max_retries} failed: {err_text}")
            else:
                print("Success: Telegram alert sent successfully.")
                return True
                
        except requests.RequestException as exc:
            sanitized_exc = sanitize(str(exc))
            logging.error(f"Attempt {attempt}/{max_retries} failed for {event_type}: {sanitized_exc}")
            print(f"[!] Attempt {attempt}/{max_retries} failed: {sanitized_exc}")

        if attempt < max_retries:
            time.sleep(retry_delay)

    final_err = f"Failed to dispatch {event_type} notification after {max_retries} attempts."
    logging.error(final_err)
    print(f"Error: {final_err}")
    return False

if __name__ == "__main__":
    action = sys.argv[1].strip().lower() if len(sys.argv) > 1 else "startup"
    if action not in ["startup", "shutdown"]:
        action = "startup"
    send_telegram_alert(action)
