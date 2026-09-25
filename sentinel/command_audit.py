"""
Structured Command Audit Logging System:
Produces sanitized, structured audit traces for every remote command execution,
authorization rejection, and action failure.
"""
from datetime import datetime
from typing import Any, Optional
from .config import logger, sanitize, mask_chat_id

def log_command_audit(
    command: str,
    chat_id: Any,
    is_authorized_user: bool,
    result: str,
    reason: Optional[str] = None
) -> None:
    """
    Writes a structured, sanitized audit log entry to error.log.
    Guarantees no tokens or plaintext chat IDs are exposed.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    masked_id = mask_chat_id(chat_id)
    user_label = "authorized" if is_authorized_user else "unauthorized"
    
    clean_cmd = sanitize(str(command))
    clean_result = sanitize(str(result))
    
    if result.upper() == "SUCCESS":
        msg = (
            f"Remote command\n"
            f"User: {user_label}\n"
            f"Chat ID: {masked_id}\n"
            f"Command: {clean_cmd}\n"
            f"Result: {clean_result}\n"
            f"Timestamp: {timestamp}"
        )
        logger.info(msg)
    else:
        clean_reason = sanitize(str(reason or "Unknown error"))
        msg = (
            f"Remote command\n"
            f"User: {user_label}\n"
            f"Chat ID: {masked_id}\n"
            f"Command: {clean_cmd}\n"
            f"Result: {clean_result}\n"
            f"Reason: {clean_reason}\n"
            f"Timestamp: {timestamp}"
        )
        logger.warning(msg)
