import time
import requests
from typing import Optional
from .config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, logger, sanitize
from .system_info import get_system_metadata
from .network import get_network_info
from .notifications import format_telegram_alert

def send_telegram_alert(event_type: str) -> bool:
    """
    Orchestrates gathering metadata, network info, formatting the message,
    and dispatching it to the Telegram Bot API with resilient retry loops.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        err_msg = "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID in environment."
        logger.error(err_msg)
        print(f"Error: {err_msg}")
        return False

    is_startup = event_type.lower() == "startup"

    # Step 1: Collect system and battery metadata
    system_info = get_system_metadata()

    # Step 2: Detect public IP and approximate geolocation (gracefully handles timeouts)
    # Shorter timeout during shutdown to prioritize swift dispatch
    net_timeout = 3.5 if is_startup else 2.0
    network_info = get_network_info(timeout=net_timeout)

    # Step 3: Format HTML notification
    message = format_telegram_alert(event_type, system_info, network_info)

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

            if not response.ok:
                try:
                    resp_json = response.json()
                    error_detail = resp_json.get("description", response.text)
                except Exception:
                    error_detail = response.text
                err_text = sanitize(f"HTTP {response.status_code} ({error_detail})")
                logger.error(f"Attempt {attempt}/{max_retries} failed for {event_type}: {err_text}")
                print(f"[!] Attempt {attempt}/{max_retries} failed: {err_text}")
            else:
                print("Success: Telegram alert sent successfully.")
                return True

        except requests.RequestException as exc:
            sanitized_exc = sanitize(str(exc))
            logger.error(f"Attempt {attempt}/{max_retries} failed for {event_type}: {sanitized_exc}")
            print(f"[!] Attempt {attempt}/{max_retries} failed: {sanitized_exc}")

        if attempt < max_retries:
            time.sleep(retry_delay)

    final_err = f"Failed to dispatch {event_type} notification after {max_retries} attempts."
    logger.error(final_err)
    print(f"Error: {final_err}")
    return False
