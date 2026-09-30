"""Account pool: phones file + random API keys + auto sessions + sticky proxy."""
import asyncio
import random
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    AuthKeyUnregisteredError, UserDeactivatedBanError, UserDeactivatedError,
    FloodWaitError, SessionPasswordNeededError,
)

import config
from core.logger import log
from core.db import StateDB
from core.helpers import device, delay, to_telethon_proxy, parse_proxy, load_api_keys, load_phones, random_api_key


class Account:
    def __init__(self, phone: str, api_id: int, api_hash: str):
        self.phone = phone
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = phone.replace("+", "p")
        self.session_path = str(config.SESSIONS / self.session_name)
        self.proxy_raw: Optional[str] = None
        self.proxy_dict: Optional[dict] = None
        self.client: Optional[TelegramClient] = None
        self.status = "unknown"
        self.reports_this_wave = 0
        self._dev = device()

    def create_client(self) -> TelegramClient:
        proxy = to_telethon_proxy(self.proxy_dict) if self.proxy_dict else None
        kw = dict(
            device_model=self._dev["device_model"],
            system_version=self._dev["system_version"],
            app_version=self._dev["app_version"],
            lang_code=self._dev["lang_code"],
            system_lang_code=self._dev["system_lang_code"],
        )
        if proxy:
            kw["proxy"] = proxy
        self.client = TelegramClient(self.session_path, self.api_id, self.api_hash, **kw)
        return self.client

    async def connect_check(self, db: StateDB) -> bool:
        try:
            c = self.create_client()
            await asyncio.wait_for(c.connect(), timeout=config.ACCOUNT_CONNECT_TIMEOUT)
            if not await c.is_user_authorized():
                self.status = "need_login"
                await db.upsert_account(self.phone, self.session_name, self.status, self.proxy_raw, "need login")
                log.warning(f"[{self.phone}] needs login (run Login tab)")
                return False
            me = await c.get_me()
            self.status = "alive"
            await db.upsert_account(self.phone, self.session_name, "alive", self.proxy_raw)
            log.info(f"[{self.phone}] alive @{getattr(me,'username', me.id)}")
            return True
        except (AuthKeyUnregisteredError, UserDeactivatedBanError, UserDeactivatedError) as e:
            self.status = "banned"
            await db.upsert_account(self.phone, self.session_name, "banned", self.proxy_raw, str(e)[:120])
            log.error(f"[{self.phone}] banned")
            if self.client:
                await self.client.disconnect()
            return False
        except FloodWaitError as e:
            self.status = "flood"
            await db.upsert_account(self.phone, self.session_name, "flood", self.proxy_raw, f"FW {e.seconds}")
            return False
        except Exception as e:
            self.status = "error"
            await db.upsert_account(self.phone, self.session_name, "error", self.proxy_raw, str(e)[:120])
            log.error(f"[{self.phone}] {e}")
            if self.client:
                try:
                    await self.client.disconnect()
                except Exception:
                    pass
            return False

    async def keep_alive(self):
        if self.client and self.client.is_connected():
            try:
                await self.client.get_me()
            except Exception:
                pass

    async def disconnect(self):
        if self.client:
            try:
                await self.client.disconnect()
            except Exception:
                pass
            self.client = None


class AccountPool:
    def __init__(self, db: StateDB, on_log: Callable = None):
        self.db = db
        self.accounts: List[Account] = []
        self._stop = asyncio.Event()
        self._ka_task = None
        self.on_log = on_log or (lambda m: None)

    def load(self):
        keys = load_api_keys()
        phones = load_phones()
        if not keys:
            raise RuntimeError("Put api_id:api_hash lines in data/api_keys.txt")
        if not phones:
            raise RuntimeError("Put phones in data/phones.txt")
        self.accounts = []
        for phone in phones:
            api_id, api_hash = random_api_key(keys)
            self.accounts.append(Account(phone, api_id, api_hash))
        log.info(f"Loaded {len(self.accounts)} phones × random API keys")
        self.on_log(f"Loaded {len(self.accounts)} accounts")

    async def health(self) -> List[Account]:
        sem = asyncio.Semaphore(5)

        async def one(a: Account):
            async with sem:
                await a.connect_check(self.db)

        await asyncio.gather(*[one(a) for a in self.accounts])
        alive = [a for a in self.accounts if a.status == "alive"]
        self.on_log(f"Health: {len(alive)}/{len(self.accounts)} alive")
        return alive

    def alive(self) -> List[Account]:
        return [a for a in self.accounts if a.status == "alive" and a.client]

    def set_proxy(self, acc: Account, raw: str):
        acc.proxy_raw = raw
        acc.proxy_dict = parse_proxy(raw)

    def start_keepalive(self):
        async def loop():
            while not self._stop.is_set():
                try:
                    await asyncio.wait_for(
                        self._stop.wait(),
                        timeout=random.uniform(config.SESSION_KEEPALIVE_MIN * 60, config.SESSION_KEEPALIVE_MAX * 60),
                    )
                    break
                except asyncio.TimeoutError:
                    pass
                for a in self.alive():
                    await a.keep_alive()
                    await delay(0.3, 1.0)

        self._ka_task = asyncio.create_task(loop())

    async def stop(self):
        self._stop.set()
        if self._ka_task:
            self._ka_task.cancel()
            try:
                await self._ka_task
            except asyncio.CancelledError:
                pass
        for a in self.accounts:
            await a.disconnect()


async def interactive_login(phone: str, api_id: int, api_hash: str, code_cb, password_cb=None):
    path = str(config.SESSIONS / phone.replace("+", "p"))
    client = TelegramClient(path, api_id, api_hash)
    await client.connect()
    if await client.is_user_authorized():
        await client.disconnect()
        return True, "already authorized"
    await client.send_code_request(phone)
    code = await code_cb()
    try:
        await client.sign_in(phone, code)
    except SessionPasswordNeededError:
        if not password_cb:
            await client.disconnect()
            return False, "2FA required"
        pw = await password_cb()
        await client.sign_in(password=pw)
    await client.disconnect()
    return True, "session saved"
