import time
import os
import requests
from typing import Optional
from .config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, logger, sanitize
from .system_info import get_system_metadata
from .network import get_network_info
from .location import get_location_telemetry, is_system_context
from .notifications import format_telegram_alert

def send_telegram_alert(event_type: str) -> bool:
    """
    Orchestrates gathering system metadata, network IP, multi-tier location telemetry,
    formatting the HTML message, and dispatching it to the Telegram Bot API with resilient retry loops.
    """
    event_label = event_type.lower()
    is_startup = event_label == "startup"
    is_shutdown = event_label == "shutdown"
    action_title = event_type.capitalize()

    logger.info(f"{action_title} handler started")

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        err_msg = "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID in environment."
        logger.error(err_msg)
        print(f"Error: {err_msg}")
        logger.error(f"Final {event_label} result: FAILED")
        return False

    is_sys = is_system_context()
    user = os.getenv("USERNAME", "Unknown")
    logger.info(f"Execution context: User={user}, SYSTEM={is_sys}")

    # Step 1: Collect system and battery metadata (prioritize delivery with safe defaults)
    try:
        system_info = get_system_metadata()
    except Exception as exc:
        logger.warning(f"Failed collecting system metadata: {sanitize(str(exc))}")
        system_info = {
            "device": "ASUS TUF A15",
            "hostname": "Unknown",
            "os": "Windows",
            "user": user,
            "battery_percent": "Unavailable",
            "power_source": "Unavailable"
        }

    # Step 2: Detect public IP (tight timeout during shutdown)
    net_timeout = 2.0 if is_shutdown else 3.5
    try:
        network_info = get_network_info(timeout=net_timeout)
    except Exception as exc:
        logger.warning(f"Failed collecting network info: {sanitize(str(exc))}")
        network_info = {"ip": "Unavailable", "location": "Unavailable"}

    # Step 3: Resolve location telemetry via 3-tier engine (never blocks alert delivery)
    try:
        location_telemetry = get_location_telemetry(timeout=net_timeout, network_info=network_info)
    except Exception as exc:
        logger.warning(f"Failed collecting location telemetry: {sanitize(str(exc))}")
        location_telemetry = {
            "location_tier": "ip_fallback",
            "source": "Unavailable",
            "location_name": "Unavailable"
        }

    loc_tier = location_telemetry.get("location_tier", "unknown")
    logger.info(f"Location tier: {loc_tier}")

    # Step 4: Format HTML notification
    try:
        message = format_telegram_alert(event_type, system_info, network_info, location_telemetry)
    except Exception as exc:
        logger.error(f"Error formatting alert message: {sanitize(str(exc))}")
        message = f"🛡️ <b>SENTINEL ALERT — {event_type.upper()}</b>\nDevice: ASUS TUF A15\nStatus: Event triggered"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }

    # Configuration for retry loops (DO NOT change existing retry timing)
    max_retries = 10 if is_startup else 3
    retry_delay = 5 if is_startup else 1

    print(f"[*] Sending {event_type} notification to Telegram (Chat ID: {TELEGRAM_CHAT_ID})...")

    success = False
    for attempt in range(1, max_retries + 1):
        logger.info(f"{action_title} notification attempt {attempt}/{max_retries}")
        try:
            response = requests.post(url, json=payload, timeout=8)
            logger.info(f"Telegram HTTP response: {response.status_code}")

            if not response.ok:
                try:
                    resp_json = response.json()
                    error_detail = resp_json.get("description", response.text)
                except Exception:
                    error_detail = response.text
                err_text = sanitize(f"HTTP {response.status_code} ({error_detail})")
                logger.warning(f"{action_title} notification attempt {attempt}/{max_retries} failed: {err_text}")
                print(f"[!] Attempt {attempt}/{max_retries} failed: {err_text}")
            else:
                logger.info(f"{action_title} notification sent successfully")
                print("Success: Telegram alert sent successfully.")
                success = True
                break

        except requests.RequestException as exc:
            sanitized_exc = sanitize(f"{type(exc).__name__}: {exc}")
            logger.warning(f"{action_title} notification attempt {attempt}/{max_retries} failed: {sanitized_exc}")
            print(f"[!] Attempt {attempt}/{max_retries} failed: {sanitized_exc}")
        except Exception as exc:
            sanitized_exc = sanitize(f"{type(exc).__name__}: {exc}")
            logger.warning(f"{action_title} notification attempt {attempt}/{max_retries} failed: {sanitized_exc}")
            print(f"[!] Attempt {attempt}/{max_retries} failed: {sanitized_exc}")

        if attempt < max_retries:
            logger.info(f"Retrying in {retry_delay} second{'s' if retry_delay > 1 else ''}")
            time.sleep(retry_delay)

    if success:
        logger.info(f"Final {event_label} result: SUCCESS")
        return True
    else:
        logger.error(f"Final {event_label} result: FAILED")
        return False

def send_telegram_message(text: str, chat_id: Optional[str] = None, parse_mode: str = "HTML") -> bool:
    """
    Sends an immediate text response to the specified Telegram chat (or default TELEGRAM_CHAT_ID).
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.error("send_telegram_message: Missing TELEGRAM_BOT_TOKEN")
        return False
    
    target_chat = chat_id or TELEGRAM_CHAT_ID
    if not target_chat:
        logger.error("send_telegram_message: Missing target chat_id")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": str(target_chat),
        "text": text,
        "parse_mode": parse_mode
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.ok:
            return True
        logger.warning(f"Telegram sendMessage failed: {resp.status_code} - {sanitize(resp.text)}")
        return False
    except Exception as exc:
        logger.warning(f"Telegram sendMessage network error: {sanitize(str(exc))}")
        return False

def send_telegram_photo(photo_path: str, caption: Optional[str] = None, chat_id: Optional[str] = None) -> bool:
    """
    Uploads and sends an image file to the specified Telegram chat.
    Guarantees file handle closure.
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.error("send_telegram_photo: Missing TELEGRAM_BOT_TOKEN")
        return False

    target_chat = chat_id or TELEGRAM_CHAT_ID
    if not target_chat:
        logger.error("send_telegram_photo: Missing target chat_id")
        return False

    if not os.path.exists(photo_path):
        logger.error(f"send_telegram_photo: File not found: {photo_path}")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    data = {
        "chat_id": str(target_chat),
        "caption": caption or "",
        "parse_mode": "HTML"
    }

    try:
        with open(photo_path, "rb") as f:
            files = {"photo": f}
            resp = requests.post(url, data=data, files=files, timeout=25)
            if resp.ok:
                return True
            logger.warning(f"Telegram sendPhoto failed: {resp.status_code} - {sanitize(resp.text)}")
            return False
    except Exception as exc:
        logger.warning(f"Telegram sendPhoto network error: {sanitize(str(exc))}")
        return False

def get_telegram_updates(offset: Optional[int] = None, timeout: int = 20) -> list:
    """
    Fetches pending updates using Telegram long-polling.
    Returns a list of updates, or raises requests.RequestException on connection failure.
    """
    if not TELEGRAM_BOT_TOKEN:
        return []

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {
        "timeout": timeout,
        "allowed_updates": ["message"]
    }
    if offset is not None:
        params["offset"] = offset

    # HTTP timeout slightly longer than polling timeout
    resp = requests.get(url, params=params, timeout=timeout + 5)
    if resp.ok:
        data = resp.json()
        if data.get("ok"):
            return data.get("result", [])
    else:
        logger.warning(f"get_telegram_updates HTTP {resp.status_code}: {sanitize(resp.text)}")
    return []

