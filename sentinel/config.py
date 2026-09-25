import os
import sys
import io
import logging
from typing import Any
from pathlib import Path
from dotenv import load_dotenv

# Safe stream fallback for pythonw.exe execution where stdout/stderr are None
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

# Base project directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables
load_dotenv(dotenv_path=BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
AUTHORIZED_CHAT_ID = os.getenv("AUTHORIZED_CHAT_ID") or TELEGRAM_CHAT_ID
LOG_FILE = BASE_DIR / "error.log"

# Configure logging (INFO level for diagnostic visibility)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %I:%M:%S %p"
)

logger = logging.getLogger("sentinel")

def sanitize(text: str) -> str:
    """Strips sensitive bot tokens and URLs from logs and terminal outputs."""
    if not text:
        return ""
    sanitized = str(text)
    if TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN in sanitized:
        sanitized = sanitized.replace(TELEGRAM_BOT_TOKEN, "[REDACTED_TOKEN]")
    return sanitized

def mask_chat_id(chat_id: Any) -> str:
    """Masks chat ID for secure logging (e.g. 123****89)."""
    if chat_id is None:
        return "None"
    s = str(chat_id).strip()
    if len(s) <= 4:
        return "****"
    if len(s) <= 7:
        return f"{s[:2]}***{s[-1:]}"
    return f"{s[:3]}****{s[-2:]}"

