import logging
import sys
from datetime import datetime, timezone
from colorama import Fore, Style, init

import config

init(autoreset=True)

COLORS = {
    "DEBUG": Fore.CYAN,
    "INFO": Fore.GREEN,
    "WARNING": Fore.YELLOW,
    "ERROR": Fore.RED,
    "CRITICAL": Fore.MAGENTA + Style.BRIGHT,
}


class ColorFmt(logging.Formatter):
    def format(self, record):
        c = COLORS.get(record.levelname, "")
        record.levelname = f"{c}{record.levelname}{Style.RESET_ALL}"
        record.msg = f"{c}{record.msg}{Style.RESET_ALL}"
        return super().format(record)


def setup(name="NyxPro"):
    config.LOGS.mkdir(parents=True, exist_ok=True)
    lg = logging.getLogger(name)
    lg.setLevel(logging.INFO)
    lg.handlers.clear()
    fmt = "%(asctime)s | %(levelname)-8s | %(message)s"
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(ColorFmt(fmt, "%H:%M:%S"))
    lg.addHandler(ch)
    fh = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
    fh.setFormatter(logging.Formatter(fmt, "%Y-%m-%d %H:%M:%S"))
    lg.addHandler(fh)
    return lg


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


log = setup()
