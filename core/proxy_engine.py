"""Join proxy channel → fetch → test → save alive → auto-assign."""
import asyncio
from typing import List, Optional, Set, Callable
from pathlib import Path

from telethon import TelegramClient
from telethon.tl.types import Message
from telethon.tl.functions.channels import JoinChannelRequest
import aiohttp

import config
from core.logger import log
from core.db import StateDB
from core.helpers import extract_proxies, parse_proxy, delay


class ProxyEngine:
    def __init__(self, client: TelegramClient, db: StateDB, on_log: Callable = None):
        self.client = client
        self.db = db
        self.on_log = on_log or (lambda m: None)
        self._seen: Set[str] = set()
        self._stop = asyncio.Event()
        self._task = None
        self.alive_count = 0
        self.channels: List[str] = []

    async def test(self, p: dict) -> bool:
        if p.get("proto") == "mtproto":
            return True
        try:
            from aiohttp_socks import ProxyConnector
            url = p["raw"]
            conn = ProxyConnector.from_url(url)
            to = aiohttp.ClientTimeout(total=config.PROXY_TEST_TIMEOUT)
            async with aiohttp.ClientSession(connector=conn, timeout=to) as s:
                async with s.get("https://api.telegram.org") as r:
                    return r.status < 500
        except ImportError:
            try:
                r, w = await asyncio.wait_for(
                    asyncio.open_connection(p["host"], p["port"]),
                    timeout=config.PROXY_TEST_TIMEOUT,
                )
                w.close()
                await w.wait_closed()
                return True
            except Exception:
                return False
        except Exception:
            return False

    def _save_file(self, raw: str):
        config.PROXIES_DIR.mkdir(parents=True, exist_ok=True)
        path = config.PROXIES_FILE
        existing = set()
        if path.exists():
            existing = set(path.read_text(encoding="utf-8").splitlines())
        if raw not in existing:
            with path.open("a", encoding="utf-8") as f:
                f.write(raw + "\n")

    async def ingest(self, text: str):
        for p in extract_proxies(text):
            raw = p["raw"]
            if raw in self._seen:
                continue
            self._seen.add(raw)
            ok = await self.test(p)
            await self.db.upsert_proxy(raw, p["proto"], alive=ok)
            if ok:
                self.alive_count += 1
                self._save_file(raw)
                self.on_log(f"Proxy OK {raw}")
            else:
                self.on_log(f"Proxy dead {raw}")

    async def join_and_scrape(self, username: str, limit: int = 60):
        username = username.lstrip("@")
        try:
            entity = await self.client.get_entity(username)
            try:
                await self.client(JoinChannelRequest(entity))
                self.on_log(f"Joined @{username}")
            except Exception:
                pass
            msgs = await self.client.get_messages(entity, limit=limit)
            for m in msgs:
                if isinstance(m, Message) and m.message:
                    await self.ingest(m.message)
        except Exception as e:
            self.on_log(f"Proxy channel @{username}: {e}")
            log.warning(f"proxy scrape @{username}: {e}")

    async def load_seed(self):
        if not config.PROXIES_FILE.exists():
            return
        for line in config.PROXIES_FILE.read_text(encoding="utf-8").splitlines():
            p = parse_proxy(line)
            if not p:
                continue
            ok = await self.test(p)
            await self.db.upsert_proxy(p["raw"], p["proto"], alive=ok)
            if ok:
                self._seen.add(p["raw"])
                self.alive_count += 1

    def start_loop(self, channels: List[str]):
        self.channels = [c.lstrip("@") for c in channels if c.strip()]

        async def loop():
            self.on_log(f"Proxy engine watching: {self.channels}")
            while not self._stop.is_set():
                for ch in self.channels:
                    if self._stop.is_set():
                        break
                    await self.join_and_scrape(ch)
                    await delay(1, 2)
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=config.PROXY_REFRESH_SEC)
                    break
                except asyncio.TimeoutError:
                    pass

        self._task = asyncio.create_task(loop())

    async def stop(self):
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
