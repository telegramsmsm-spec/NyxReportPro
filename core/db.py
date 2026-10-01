"""SQLite persistence layer for NyxReportPro."""
from __future__ import annotations
import aiosqlite
from pathlib import Path
from typing import Any, Optional, List, Dict
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "nyxreport.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT UNIQUE NOT NULL,
    api_id INTEGER NOT NULL,
    api_hash_enc TEXT NOT NULL,
    session_path TEXT,
    proxy_id INTEGER,
    status TEXT DEFAULT 'unknown',
    last_check TEXT,
    warmup_days INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS proxies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    host TEXT NOT NULL,
    port INTEGER NOT NULL,
    secret TEXT,
    username TEXT,
    password TEXT,
    source_channel TEXT,
    last_tested TEXT,
    is_alive INTEGER DEFAULT 0,
    assigned_account INTEGER,
    UNIQUE(host, port, secret)
);
CREATE TABLE IF NOT EXISTS targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    tme_link TEXT,
    type TEXT,
    last_fetched TEXT
);
CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER,
    message_id INTEGER,
    date TEXT,
    text TEXT,
    media_type TEXT,
    views INTEGER,
    post_link TEXT,
    selected INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS report_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evidence_ids TEXT,
    account_id INTEGER,
    reason TEXT,
    status TEXT DEFAULT 'pending',
    bot_used TEXT,
    result TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS emails_sent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    to_address TEXT,
    subject TEXT,
    body_hash TEXT,
    attachments TEXT,
    status TEXT,
    smtp_response TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS action_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT,
    message TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_accounts_phone ON accounts(phone);
CREATE INDEX IF NOT EXISTS idx_proxies_alive ON proxies(is_alive);
CREATE INDEX IF NOT EXISTS idx_evidence_target ON evidence(target_id);
CREATE INDEX IF NOT EXISTS idx_log_time ON action_log(timestamp);
"""

class Database:
    def __init__(self, path: Path = DB_PATH):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    async def connect(self):
        self.db = await aiosqlite.connect(self.path)
        self.db.row_factory = aiosqlite.Row
        await self.db.executescript(SCHEMA)
        await self.db.commit()

    async def close(self):
        await self.db.close()

    async def log(self, level: str, message: str):
        await self.db.execute(
            "INSERT INTO action_log (level, message) VALUES (?, ?)",
            (level, message)
        )
        await self.db.commit()

    async def add_account(self, phone: str, api_id: int, api_hash_enc: str, session_path: str = None) -> int:
        cur = await self.db.execute(
            "INSERT OR REPLACE INTO accounts (phone, api_id, api_hash_enc, session_path) VALUES (?, ?, ?, ?)",
            (phone, api_id, api_hash_enc, session_path)
        )
        await self.db.commit()
        return cur.lastrowid

    async def get_accounts(self) -> List[Dict]:
        cur = await self.db.execute("SELECT * FROM accounts")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def update_account_status(self, account_id: int, status: str):
        await self.db.execute(
            "UPDATE accounts SET status=?, last_check=? WHERE id=?",
            (status, datetime.utcnow().isoformat(), account_id)
        )
        await self.db.commit()

    async def assign_proxy(self, account_id: int, proxy_id: int):
        await self.db.execute("UPDATE accounts SET proxy_id=? WHERE id=?", (proxy_id, account_id))
        await self.db.execute("UPDATE proxies SET assigned_account=? WHERE id=?", (account_id, proxy_id))
        await self.db.commit()

    async def add_proxy(self, type_: str, host: str, port: int, secret: str = None,
                        username: str = None, password: str = None, source: str = None) -> int:
        try:
            cur = await self.db.execute(
                "INSERT OR IGNORE INTO proxies (type, host, port, secret, username, password, source_channel) VALUES (?,?,?,?,?,?,?)",
                (type_, host, port, secret, username, password, source)
            )
            await self.db.commit()
            return cur.lastrowid
        except Exception:
            return 0

    async def get_alive_proxies(self) -> List[Dict]:
        cur = await self.db.execute("SELECT * FROM proxies WHERE is_alive=1")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def mark_proxy_alive(self, proxy_id: int, alive: bool):
        await self.db.execute(
            "UPDATE proxies SET is_alive=?, last_tested=? WHERE id=?",
            (1 if alive else 0, datetime.utcnow().isoformat(), proxy_id)
        )
        await self.db.commit()

    async def add_target(self, username: str, tme_link: str, type_: str) -> int:
        cur = await self.db.execute(
            "INSERT INTO targets (username, tme_link, type) VALUES (?,?,?)",
            (username, tme_link, type_)
        )
        await self.db.commit()
        return cur.lastrowid

    async def add_evidence(self, target_id: int, message_id: int, date: str, text: str,
                           media_type: str, views: int, post_link: str) -> int:
        cur = await self.db.execute(
            "INSERT INTO evidence (target_id, message_id, date, text, media_type, views, post_link) VALUES (?,?,?,?,?,?,?)",
            (target_id, message_id, date, text, media_type, views, post_link)
        )
        await self.db.commit()
        return cur.lastrowid

    async def get_selected_evidence(self, target_id: int = None) -> List[Dict]:
        if target_id:
            cur = await self.db.execute("SELECT * FROM evidence WHERE selected=1 AND target_id=?", (target_id,))
        else:
            cur = await self.db.execute("SELECT * FROM evidence WHERE selected=1")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def select_evidence(self, evidence_ids: List[int]):
        for eid in evidence_ids:
            await self.db.execute("UPDATE evidence SET selected=1 WHERE id=?", (eid,))
        await self.db.commit()

    async def add_report(self, evidence_ids: str, account_id: int, reason: str, status: str = "pending",
                         bot_used: str = None, result: str = None) -> int:
        cur = await self.db.execute(
            "INSERT INTO report_queue (evidence_ids, account_id, reason, status, bot_used, result) VALUES (?,?,?,?,?,?)",
            (evidence_ids, account_id, reason, status, bot_used, result)
        )
        await self.db.commit()
        return cur.lastrowid

    async def update_report(self, report_id: int, status: str, result: str = None):
        await self.db.execute(
            "UPDATE report_queue SET status=?, result=? WHERE id=?",
            (status, result, report_id)
        )
        await self.db.commit()

    async def add_email(self, to_address: str, subject: str, body_hash: str, attachments: str,
                        status: str, smtp_response: str) -> int:
        cur = await self.db.execute(
            "INSERT INTO emails_sent (to_address, subject, body_hash, attachments, status, smtp_response) VALUES (?,?,?,?,?,?)",
            (to_address, subject, body_hash, attachments, status, smtp_response)
        )
        await self.db.commit()
        return cur.lastrowid

    async def get_logs(self, limit: int = 500) -> List[Dict]:
        cur = await self.db.execute("SELECT * FROM action_log ORDER BY id DESC LIMIT ?", (limit,))
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
