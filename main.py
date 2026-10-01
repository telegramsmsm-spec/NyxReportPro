#!/usr/bin/env python3
"""NyxReportPro – multi-account Telegram public-content reporting tool."""
from __future__ import annotations
import asyncio
import sys
from pathlib import Path

# ensure package root
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from ui.main_window import run_app

if __name__ == "__main__":
    run_app()
