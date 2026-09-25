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
from typing import Optional, Dict, Any, List, Tuple

import requests

from .config import BASE_DIR, AUTHORIZED_CHAT_ID, logger, sanitize, mask_chat_id
from .command_auth import is_authorized
from .command_audit import log_command_audit
from .telegram import send_telegram_message, send_telegram_photo, get_telegram_updates

# Modular Action Handlers
from .remote_actions import (
    execute_status,
    execute_location,
    execute_screenshot,
    execute_processes,
    execute_camera
)
from .power_actions import (
    execute_lock,
    execute_shutdown_request,
    execute_confirm_shutdown,
    execute_restart_request,
    execute_confirm_restart
)
from .system_actions import (
    execute_cpu,
    execute_ram,
    execute_disk,
    execute_battery,
    execute_uptime,
    execute_system
)
from .security_actions import (
    execute_sessions,
    execute_security,
    execute_events,
    execute_audit,
    execute_lastboot,
    execute_health,
    execute_version
)
from .file_actions import (
    execute_find,
    execute_list,
    execute_fileinfo,
    execute_open
)
from .network_actions import (
    execute_ping,
    execute_publicip,
    execute_network,
    execute_wifi
)
from .agent_actions import (
    execute_agent,
    execute_restart_agent
)

STATE_FILE = BASE_DIR / ".update_state.json"
MAX_HISTORY_IDS = 500

ALLOWLIST = {
    # System
    "/status",
    "/cpu",
    "/ram",
    "/disk",
    "/battery",
    "/uptime",
    "/system",
    "/network",
    "/wifi",
    "/location",
    # Security / Monitoring
    "/sessions",
    "/security",
    "/events",
    "/audit",
    "/lastboot",
    "/health",
    "/version",
    # Power
    "/lock",
    "/shutdown",
    "/confirm_shutdown",
    "/restart",
    "/confirm_restart",
    # Safe File Operations
    "/find",
    "/list",
    "/fileinfo",
    "/open",
    # Network Diagnostics
    "/ping",
    "/publicip",
    # Agent Lifecycle
    "/agent",
    "/restart_agent",
    # Sensory / Existing
    "/screenshot",
    "/processes",
    "/camera",
    "/help",
    "/start"
}

HELP_TEXT = (
    "🛡️ <b>SENTINEL REMOTE COMMAND REFERENCE (v0.5)</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "📊 <b>SYSTEM TELEMETRY:</b>\n"
    "• <code>/status</code> — Full device & status summary\n"
    "• <code>/cpu</code> — CPU load, topology & clock speed\n"
    "• <code>/ram</code> — RAM & swap memory telemetry\n"
    "• <code>/disk</code> — Local storage usage (used/free/total)\n"
    "• <code>/battery</code> — Battery %, power source & status\n"
    "• <code>/uptime</code> — Windows uptime & boot timestamp\n"
    "• <code>/system</code> — OS version, CPU, RAM & GPU summary\n"
    "• <code>/network</code> — Active network adapters & IP info\n"
    "• <code>/wifi</code> — Connected Wi-Fi SSID, signal & radio info\n"
    "• <code>/location</code> — 3-tier GPS & IP location report\n\n"
    "🔒 <b>SECURITY & MONITORING:</b>\n"
    "• <code>/sessions</code> — Windows user & console sessions\n"
    "• <code>/security</code> — Sentinel security posture & gates\n"
    "• <code>/events</code> — Recent Sentinel lifecycle events\n"
    "• <code>/audit</code> — Sanitized remote-command audit trail\n"
    "• <code>/lastboot</code> — Latest boot timestamp & duration\n"
    "• <code>/health</code> — Component-by-component self check\n"
    "• <code>/version</code> — Sentinel version & component versions\n\n"
    "⚡ <b>POWER CONTROLS:</b>\n"
    "• <code>/lock</code> — Instantly lock workstation\n"
    "• <code>/shutdown</code> — Request system shutdown <i>[Requires 2-step confirmation]</i>\n"
    "• <code>/confirm_shutdown</code> — Confirm pending shutdown within 30s\n"
    "• <code>/restart</code> — Request system restart <i>[Requires 2-step confirmation]</i>\n"
    "• <code>/confirm_restart</code> — Confirm pending restart within 30s\n\n"
    "📁 <b>SAFE FILE OPERATIONS:</b>\n"
    "• <code>/find &lt;filename&gt;</code> — Search only within approved roots\n"
    "• <code>/list [approved-folder]</code> — List approved folder contents\n"
    "• <code>/fileinfo &lt;path&gt;</code> — Safe file metadata (no contents)\n"
    "• <code>/open &lt;approved-folder&gt;</code> — Open folder in Explorer <i>[Interactive session only]</i>\n\n"
    "📡 <b>NETWORK DIAGNOSTICS:</b>\n"
    "• <code>/ping</code> — Bounded latency test to trusted endpoints\n"
    "• <code>/publicip</code> — Multi-provider public IP detection\n\n"
    "🤖 <b>AGENT LIFECYCLE:</b>\n"
    "• <code>/agent</code> — Sentinel process health & memory usage\n"
    "• <code>/restart_agent</code> — Safely restart Sentinel daemon\n\n"
    "📸 <b>SENSORY & PROCESSES:</b>\n"
    "• <code>/screenshot</code> — Desktop screenshot <i>[Interactive session only]</i>\n"
    "• <code>/processes</code> — Top 20 processes by memory\n"
    "• <code>/camera</code> — Single snapshot <i>[Requires local user GUI consent]</i>\n"
    "• <code>/help</code> — Show this command reference\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "🔒 <i>Strict single-user authorization & audit active.</i>"
)


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
        """Dispatches an allowlisted command safely with modular routing."""
        parts = raw_cmd.strip().split(maxsplit=1)
        cmd_token = parts[0].lower() if parts else ""
        cmd_arg = parts[1].strip() if len(parts) > 1 else ""

        # Strip bot username suffix if present (e.g., /status@bot_name -> /status)
        if "@" in cmd_token:
            cmd_token = cmd_token.split("@")[0]

        logger.info(f"Processing remote command '{cmd_token}' from chat {mask_chat_id(chat_id)}")

        # ----------------- SYSTEM TELEMETRY -----------------
        if cmd_token == "/status":
            output = execute_status()
            send_telegram_message(output, chat_id=chat_id)
            log_command_audit("/status", chat_id, is_authorized_user=True, result="SUCCESS")

        elif cmd_token == "/cpu":
            output = execute_cpu()
            send_telegram_message(output, chat_id=chat_id)
            log_command_audit("/cpu", chat_id, is_authorized_user=True, result="SUCCESS")

        elif cmd_token == "/ram":
            output = execute_ram()
            send_telegram_message(output, chat_id=chat_id)
            log_command_audit("/ram", chat_id, is_authorized_user=True, result="SUCCESS")

        elif cmd_token == "/disk":
            output = execute_disk()
            send_telegram_message(output, chat_id=chat_id)
            log_command_audit("/disk", chat_id, is_authorized_user=True, result="SUCCESS")

        elif cmd_token == "/battery":
            output = execute_battery()
            send_telegram_message(output, chat_id=chat_id)
            log_command_audit("/battery", chat_id, is_authorized_user=True, result="SUCCESS")

        elif cmd_token == "/uptime":
            output = execute_uptime()
            send_telegram_message(output, chat_id=chat_id)
            log_command_audit("/uptime", chat_id, is_authorized_user=True, result="SUCCESS")

        elif cmd_token == "/system":
            output = execute_system()
            send_telegram_message(output, chat_id=chat_id)
            log_command_audit("/system", chat_id, is_authorized_user=True, result="SUCCESS")

        elif cmd_token == "/network":
            output = execute_network()
            send_telegram_message(output, chat_id=chat_id)
            log_command_audit("/network", chat_id, is_authorized_user=True, result="SUCCESS")

        elif cmd_token == "/wifi":
            output = execute_wifi()
            send_telegram_message(output, chat_id=chat_id)
            log_command_audit("/wifi", chat_id, is_authorized_user=True, result="SUCCESS")

        elif cmd_token == "/location":
            output = execute_location()
            send_telegram_message(output, chat_id=chat_id)
            log_command_audit("/location", chat_id, is_authorized_user=True, result="SUCCESS")

        # ----------------- SECURITY & MONITORING -----------------
        elif cmd_token == "/sessions":
            output = execute_sessions()
            send_telegram_message(output, chat_id=chat_id)
            log_command_audit("/sessions", chat_id, is_authorized_user=True, result="SUCCESS")

        elif cmd_token == "/security":
            output = execute_security()
            send_telegram_message(output, chat_id=chat_id)
            log_command_audit("/security", chat_id, is_authorized_user=True, result="SUCCESS")

        elif cmd_token == "/events":
            output = execute_events()
            send_telegram_message(output, chat_id=chat_id)
            log_command_audit("/events", chat_id, is_authorized_user=True, result="SUCCESS")

        elif cmd_token == "/audit":
            output = execute_audit()
            send_telegram_message(output, chat_id=chat_id)
            log_command_audit("/audit", chat_id, is_authorized_user=True, result="SUCCESS")

        elif cmd_token == "/lastboot":
            output = execute_lastboot()
            send_telegram_message(output, chat_id=chat_id)
            log_command_audit("/lastboot", chat_id, is_authorized_user=True, result="SUCCESS")

        elif cmd_token == "/health":
            output = execute_health()
            send_telegram_message(output, chat_id=chat_id)
            log_command_audit("/health", chat_id, is_authorized_user=True, result="SUCCESS")

        elif cmd_token == "/version":
            output = execute_version()
            send_telegram_message(output, chat_id=chat_id)
            log_command_audit("/version", chat_id, is_authorized_user=True, result="SUCCESS")

        # ----------------- POWER CONTROLS -----------------
        elif cmd_token == "/lock":
            output = execute_lock()
            send_telegram_message(output, chat_id=chat_id)
            res_str = "SUCCESS" if "✅" in output else "FAILED"
            log_command_audit("/lock", chat_id, is_authorized_user=True, result=res_str, reason=output if res_str == "FAILED" else None)

        elif cmd_token == "/shutdown":
            prompt = execute_shutdown_request(chat_id)
            send_telegram_message(prompt, chat_id=chat_id)
            log_command_audit("/shutdown", chat_id, is_authorized_user=True, result="SUCCESS")

        elif cmd_token == "/confirm_shutdown":
            accepted, msg = execute_confirm_shutdown(chat_id)
            send_telegram_message(msg, chat_id=chat_id)
            log_command_audit(
                "/confirm_shutdown",
                chat_id,
                is_authorized_user=True,
                result="SUCCESS" if accepted else "FAILED",
                reason=msg if not accepted else None
            )

        elif cmd_token == "/restart":
            prompt = execute_restart_request(chat_id)
            send_telegram_message(prompt, chat_id=chat_id)
            log_command_audit("/restart", chat_id, is_authorized_user=True, result="SUCCESS")

        elif cmd_token == "/confirm_restart":
            accepted, msg = execute_confirm_restart(chat_id)
            send_telegram_message(msg, chat_id=chat_id)
            log_command_audit(
                "/confirm_restart",
                chat_id,
                is_authorized_user=True,
                result="SUCCESS" if accepted else "FAILED",
                reason=msg if not accepted else None
            )

        # ----------------- SAFE FILE OPERATIONS -----------------
        elif cmd_token == "/find":
            output = execute_find(cmd_arg)
            send_telegram_message(output, chat_id=chat_id)
            res_str = "FAILED" if output.startswith("❌") else "SUCCESS"
            log_command_audit("/find", chat_id, is_authorized_user=True, result=res_str, reason=output if res_str == "FAILED" else None)

        elif cmd_token == "/list":
            output = execute_list(cmd_arg)
            send_telegram_message(output, chat_id=chat_id)
            res_str = "FAILED" if output.startswith("❌") else "SUCCESS"
            log_command_audit("/list", chat_id, is_authorized_user=True, result=res_str, reason=output if res_str == "FAILED" else None)

        elif cmd_token == "/fileinfo":
            output = execute_fileinfo(cmd_arg)
            send_telegram_message(output, chat_id=chat_id)
            res_str = "FAILED" if output.startswith("❌") else "SUCCESS"
            log_command_audit("/fileinfo", chat_id, is_authorized_user=True, result=res_str, reason=output if res_str == "FAILED" else None)

        elif cmd_token == "/open":
            output = execute_open(cmd_arg)
            send_telegram_message(output, chat_id=chat_id)
            res_str = "FAILED" if output.startswith("❌") else "SUCCESS"
            log_command_audit("/open", chat_id, is_authorized_user=True, result=res_str, reason=output if res_str == "FAILED" else None)

        # ----------------- NETWORK DIAGNOSTICS -----------------
        elif cmd_token == "/ping":
            output = execute_ping()
            send_telegram_message(output, chat_id=chat_id)
            log_command_audit("/ping", chat_id, is_authorized_user=True, result="SUCCESS")

        elif cmd_token == "/publicip":
            output = execute_publicip()
            send_telegram_message(output, chat_id=chat_id)
            log_command_audit("/publicip", chat_id, is_authorized_user=True, result="SUCCESS")

        # ----------------- AGENT LIFECYCLE -----------------
        elif cmd_token == "/agent":
            output = execute_agent()
            send_telegram_message(output, chat_id=chat_id)
            log_command_audit("/agent", chat_id, is_authorized_user=True, result="SUCCESS")

        elif cmd_token == "/restart_agent":
            output = execute_restart_agent()
            send_telegram_message(output, chat_id=chat_id)
            log_command_audit("/restart_agent", chat_id, is_authorized_user=True, result="SUCCESS")

        # ----------------- SENSORY / EXISTING -----------------
        elif cmd_token == "/screenshot":
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

        elif cmd_token == "/processes":
            output = execute_processes()
            send_telegram_message(output, chat_id=chat_id)
            log_command_audit("/processes", chat_id, is_authorized_user=True, result="SUCCESS")

        elif cmd_token == "/camera":
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

        elif cmd_token in ["/help", "/start"]:
            send_telegram_message(HELP_TEXT, chat_id=chat_id)
            log_command_audit(cmd_token, chat_id, is_authorized_user=True, result="SUCCESS")

        else:
            # Unknown command rejected
            msg = (
                f"❌ Unknown command: <code>{sanitize(cmd_token)}</code>\n"
                "Send /help to view all allowlisted commands."
            )
            send_telegram_message(msg, chat_id=chat_id)
            log_command_audit(cmd_token, chat_id, is_authorized_user=True, result="REJECTED", reason="Command not in allowlist")

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
