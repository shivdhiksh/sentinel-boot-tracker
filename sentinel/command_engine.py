"""
Sentinel Telegram Remote Command Engine:
Provides resilient long-polling, update deduplication with disk persistence,
strict sender authorization, allowlisted command dispatch, and structured auditing.
Runs as an independent worker thread or standalone process.
"""
import os
import json
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List

import requests

from .config import BASE_DIR, AUTHORIZED_CHAT_ID, logger, sanitize, mask_chat_id
from .command_auth import is_authorized
from .command_audit import log_command_audit
from .telegram import send_telegram_message, send_telegram_photo, get_telegram_updates
from .remote_actions import (
    execute_status,
    execute_location,
    execute_lock,
    execute_shutdown_request,
    execute_confirm_shutdown,
    execute_screenshot,
    execute_processes,
    execute_camera
)

STATE_FILE = BASE_DIR / ".update_state.json"
MAX_HISTORY_IDS = 500

ALLOWLIST = {
    "/status",
    "/location",
    "/lock",
    "/shutdown",
    "/confirm_shutdown",
    "/screenshot",
    "/processes",
    "/camera",
    "/help",
    "/start"
}

class CommandEngine:
    def __init__(self, stop_event: Optional[threading.Event] = None):
        self.stop_event = stop_event or threading.Event()
        self.last_update_id: int = 0
        self.processed_update_ids: List[int] = []
        self._load_state()

    def _load_state(self) -> None:
        """Loads persisted update offset and recently processed update IDs."""
        if not STATE_FILE.exists():
            return
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.last_update_id = int(data.get("last_update_id", 0))
            self.processed_update_ids = [int(x) for x in data.get("processed_ids", [])]
            logger.info(f"Loaded update state: last_update_id={self.last_update_id}, cached_ids={len(self.processed_update_ids)}")
        except Exception as exc:
            logger.warning(f"Could not load update state file: {sanitize(str(exc))}")

    def _save_state(self) -> None:
        """Atomically saves update offset and deduplication history to disk."""
        try:
            # Bound history size
            if len(self.processed_update_ids) > MAX_HISTORY_IDS:
                self.processed_update_ids = self.processed_update_ids[-MAX_HISTORY_IDS:]

            payload = {
                "last_update_id": self.last_update_id,
                "processed_ids": self.processed_update_ids
            }
            tmp_file = STATE_FILE.with_suffix(".tmp")
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            os.replace(tmp_file, STATE_FILE)
        except Exception as exc:
            logger.warning(f"Could not save update state file: {sanitize(str(exc))}")

    def _handle_command(self, raw_cmd: str, chat_id: Any) -> None:
        """Dispatches an allowlisted command safely."""
        clean_cmd = raw_cmd.strip().split()[0].lower()
        # Strip bot username suffix if present (e.g., /status@bot_name -> /status)
        if "@" in clean_cmd:
            clean_cmd = clean_cmd.split("@")[0]

        logger.info(f"Processing remote command '{clean_cmd}' from chat {mask_chat_id(chat_id)}")

        if clean_cmd == "/status":
            output = execute_status()
            send_telegram_message(output, chat_id=chat_id)
            log_command_audit("/status", chat_id, is_authorized_user=True, result="SUCCESS")

        elif clean_cmd == "/location":
            output = execute_location()
            send_telegram_message(output, chat_id=chat_id)
            log_command_audit("/location", chat_id, is_authorized_user=True, result="SUCCESS")

        elif clean_cmd == "/lock":
            output = execute_lock()
            send_telegram_message(output, chat_id=chat_id)
            res_str = "SUCCESS" if "✅" in output else "FAILED"
            log_command_audit("/lock", chat_id, is_authorized_user=True, result=res_str, reason=output if res_str == "FAILED" else None)

        elif clean_cmd == "/shutdown":
            prompt = execute_shutdown_request(chat_id)
            send_telegram_message(prompt, chat_id=chat_id)
            log_command_audit("/shutdown", chat_id, is_authorized_user=True, result="SUCCESS")

        elif clean_cmd == "/confirm_shutdown":
            accepted, msg = execute_confirm_shutdown(chat_id)
            send_telegram_message(msg, chat_id=chat_id)
            log_command_audit("/confirm_shutdown", chat_id, is_authorized_user=True, result="SUCCESS" if accepted else "FAILED", reason=msg if not accepted else None)

        elif clean_cmd == "/screenshot":
            temp_path = None
            try:
                temp_path, caption_or_err = execute_screenshot()
                if temp_path:
                    sent = send_telegram_photo(temp_path, caption=caption_or_err, chat_id=chat_id)
                    if sent:
                        log_command_audit("/screenshot", chat_id, is_authorized_user=True, result="SUCCESS")
                    else:
                        send_telegram_message("❌ Failed to transmit screenshot to Telegram.", chat_id=chat_id)
                        log_command_audit("/screenshot", chat_id, is_authorized_user=True, result="FAILED", reason="Transmission error")
                else:
                    send_telegram_message(caption_or_err, chat_id=chat_id)
                    log_command_audit("/screenshot", chat_id, is_authorized_user=True, result="FAILED", reason=caption_or_err)
            finally:
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception as e:
                        logger.warning(f"Could not remove temp screenshot: {sanitize(str(e))}")

        elif clean_cmd == "/processes":
            output = execute_processes()
            send_telegram_message(output, chat_id=chat_id)
            log_command_audit("/processes", chat_id, is_authorized_user=True, result="SUCCESS")

        elif clean_cmd == "/camera":
            temp_path = None
            try:
                temp_path, caption_or_err = execute_camera()
                if temp_path:
                    sent = send_telegram_photo(temp_path, caption=caption_or_err, chat_id=chat_id)
                    if sent:
                        log_command_audit("/camera", chat_id, is_authorized_user=True, result="SUCCESS")
                    else:
                        send_telegram_message("❌ Failed to transmit photo to Telegram.", chat_id=chat_id)
                        log_command_audit("/camera", chat_id, is_authorized_user=True, result="FAILED", reason="Transmission error")
                else:
                    send_telegram_message(caption_or_err, chat_id=chat_id)
                    log_command_audit("/camera", chat_id, is_authorized_user=True, result="FAILED", reason=caption_or_err)
            finally:
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception as e:
                        logger.warning(f"Could not remove temp photo: {sanitize(str(e))}")

        elif clean_cmd in ["/help", "/start"]:
            help_text = (
                "🛡️ <b>SENTINEL REMOTE COMMANDS</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "/status — Telemetry, CPU, RAM, battery, OS, uptime\n"
                "/location — Multi-tier GPS & approximate IP location\n"
                "/lock — Instantly lock Windows workstation\n"
                "/shutdown — 2-step confirmed system shutdown\n"
                "/screenshot — Capture current desktop screenshot\n"
                "/processes — List top 20 active processes\n"
                "/camera — Explicitly consent-based single photo\n"
                "/help — Show this reference\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "🔒 <i>Strict single-user authorization & audit active.</i>"
            )
            send_telegram_message(help_text, chat_id=chat_id)
            log_command_audit(clean_cmd, chat_id, is_authorized_user=True, result="SUCCESS")

        else:
            # Unknown command rejected
            msg = (
                f"❌ Unknown command: <code>{clean_cmd}</code>\n"
                "Send /help to view all allowlisted commands."
            )
            send_telegram_message(msg, chat_id=chat_id)
            log_command_audit(clean_cmd, chat_id, is_authorized_user=True, result="REJECTED", reason="Command not in allowlist")

    def process_update(self, update: Dict[str, Any]) -> None:
        """Processes an incoming Telegram update with strict authorization and deduplication."""
        update_id = update.get("update_id")
        if update_id is None:
            return

        # Deduplication check
        if update_id in self.processed_update_ids or update_id <= self.last_update_id:
            logger.info(f"Skipping duplicate update ID {update_id}")
            return

        message = update.get("message")
        if not message:
            # Non-message update (e.g. channel post or edit) -> acknowledge and skip
            self.last_update_id = max(self.last_update_id, update_id)
            self.processed_update_ids.append(update_id)
            self._save_state()
            return

        chat = message.get("chat", {})
        chat_id = chat.get("id")
        text = (message.get("text") or "").strip()

        # Authorization check
        if not is_authorized(chat_id):
            cmd_preview = text.split()[0] if text else "empty"
            log_command_audit(
                command=cmd_preview,
                chat_id=chat_id,
                is_authorized_user=False,
                result="REJECTED",
                reason="Unauthorized chat ID"
            )
            send_telegram_message("⛔ Access Denied: Unauthorized chat ID.", chat_id=chat_id)
            # Acknowledge update to avoid re-processing
            self.last_update_id = max(self.last_update_id, update_id)
            self.processed_update_ids.append(update_id)
            self._save_state()
            return

        # Allowlisted command check
        if text.startswith("/"):
            try:
                self._handle_command(text, chat_id)
            except Exception as exc:
                logger.error(f"Error handling command '{text}': {sanitize(str(exc))}")
                send_telegram_message(f"❌ Internal command execution error: {sanitize(str(exc))}", chat_id=chat_id)
                log_command_audit(text, chat_id, is_authorized_user=True, result="FAILED", reason=str(exc))

        # Acknowledge update ID and persist
        self.last_update_id = max(self.last_update_id, update_id)
        self.processed_update_ids.append(update_id)
        self._save_state()

    def run_polling_loop(self) -> None:
        """
        Runs the resilient Telegram long-polling loop with exponential backoff on network failures.
        Exits when stop_event is set.
        """
        logger.info("Sentinel Telegram Command Engine polling loop started.")
        backoff_sec = 2.0
        max_backoff = 30.0

        while not self.stop_event.is_set():
            query_offset = self.last_update_id + 1 if self.last_update_id > 0 else None
            try:
                updates = get_telegram_updates(offset=query_offset, timeout=15)
                # Successful connection, reset backoff
                backoff_sec = 2.0

                for update in updates:
                    if self.stop_event.is_set():
                        break
                    self.process_update(update)

            except requests.RequestException as exc:
                logger.warning(f"Telegram polling network failure: {sanitize(str(exc))}. Retrying in {backoff_sec:.1f}s...")
                # Interruptible sleep
                self.stop_event.wait(backoff_sec)
                backoff_sec = min(backoff_sec * 2.0, max_backoff)
            except Exception as exc:
                logger.error(f"Unexpected polling loop exception: {sanitize(str(exc))}")
                self.stop_event.wait(5.0)

        logger.info("Sentinel Telegram Command Engine polling loop stopped.")


def start_command_engine_worker(stop_event: Optional[threading.Event] = None) -> threading.Thread:
    """Spawns the CommandEngine polling loop in a dedicated daemon thread."""
    engine = CommandEngine(stop_event=stop_event)
    thread = threading.Thread(
        target=engine.run_polling_loop,
        name="SentinelCommandEngineWorker",
        daemon=True
    )
    thread.start()
    return thread
