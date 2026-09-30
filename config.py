"""NyxReportPro – central config. Paths + tunables only. No secrets."""
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
SESSIONS = BASE / "sessions"
PROXIES_DIR = BASE / "proxies"
LOGS = BASE / "logs"
TEMP = BASE / "temp"

API_KEYS_FILE = DATA / "api_keys.txt"
PHONES_FILE = DATA / "phones.txt"
SMTP_FILE = DATA / "smtp.json"
PROXIES_FILE = PROXIES_DIR / "alive_proxies.txt"
DB_PATH = DATA / "state.db"
LOG_FILE = LOGS / "nyx_pro.log"

DEFAULT_POSTS = 80
DEFAULT_EMAILS = 50
DEFAULT_REPORTS_PER_ACC = 6
REPORT_WORKERS = 8
REPORT_DELAY_MIN = 4.0
REPORT_DELAY_MAX = 14.0
FLOOD_GLOBAL_PAUSE = 90
PROXY_REFRESH_SEC = 120
PROXY_TEST_TIMEOUT = 10
SESSION_KEEPALIVE_MIN = 30
SESSION_KEEPALIVE_MAX = 45
ACCOUNT_CONNECT_TIMEOUT = 25

ABUSE_BOT = "AbuseNotification"
SEARCH_BOT = "SearchReport"
SCAM_BOT = "NoToScam"

REPORT_REASONS = {
    "child_abuse": 35, "spam": 20, "violence": 15, "pornography": 12,
    "scam": 10, "copyright": 5, "other": 3,
}

DEVICE_MODELS = [
    "Samsung Galaxy S23", "Samsung Galaxy S24", "Google Pixel 8",
    "Xiaomi 14", "OnePlus 12", "iPhone 15 Pro", "Huawei P60",
]
SYSTEM_VERSIONS = ["Android 14", "Android 13", "iOS 17.4", "iOS 16.6"]
APP_VERSIONS = ["10.14.5", "10.13.2", "11.0.1", "10.12.0"]

MAILBOXES = [
    "abuse@telegram.org", "stopCA@telegram.org", "dmca@telegram.org",
    "support@telegram.org", "legal@telegram.org", "privacy@telegram.org",
]

for d in (DATA, SESSIONS, PROXIES_DIR, LOGS, TEMP):
    d.mkdir(parents=True, exist_ok=True)
