import os
import sys
import io
import logging
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
LOG_FILE = BASE_DIR / "error.log"

# Configure logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.ERROR,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %I:%M:%S %p"
)

logger = logging.getLogger("sentinel")

def sanitize(text: str) -> str:
    """Strips sensitive bot tokens from logs and terminal outputs."""
    if TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN in text:
        return text.replace(TELEGRAM_BOT_TOKEN, "[REDACTED_TOKEN]")
    return text
