from pathlib import Path
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
DB_PATH = DATA / "concalls.db"
for p in (RAW, PROCESSED):
    p.mkdir(parents=True, exist_ok=True)

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "300"))
TIMEOUT = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
MAX_PDF_MB = int(os.getenv("MAX_PDF_MB", "80"))
NSE_ENABLED = os.getenv("NSE_ENABLED", "true").lower() == "true"
BSE_ENABLED = os.getenv("BSE_ENABLED", "true").lower() == "true"
WATCH_SYMBOLS = {x.strip().upper() for x in os.getenv("WATCH_SYMBOLS", "").split(",") if x.strip()}
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
