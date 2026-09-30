import asyncio
import random
from typing import List, Dict, Any, Callable
from telethon.errors import FloodWaitError
import config
from core.helpers import delay, ref_id
from core.accounts import Account


class BotEscalation:
    def __init__(self, on_log: Callable = None):
        self.n = 0
        self.on_log = on_log or (lambda m: None)

    def _abuse(self, ev: dict, target: str) -> str:
        links = "\n".join(ev.get("sample_links", [])[:6])
        return (
            f"ABUSE REPORT – REF {ref_id()}\n"
            f"Target: @{ev.get('username', target.lstrip('@'))}\n"
            f"Type: {ev.get('entity_type')}\nLink: {ev.get('link')}\n"
            f"Violations: spam/scam/ToS/harmful content\n"
            f"Evidence:\n{links}\nDate: {ev.get('date_range')}\n"
            f"Request: permanent restriction.\nGood faith under ToS."
        )

    def _search(self, target: str, ev: dict) -> str:
        u = ev.get("username", target.lstrip("@"))
        return (
            f"Search surface – REF {ref_id()}\n"
            f"Terms: {u}, {ev.get('title','')}\n"
            f"https://t.me/{u}\nReview visibility."
        )

    def _scam(self, ev: dict, target: str) -> str:
        return (
            f"SCAM REPORT – REF {ref_id()}\n"
            f"Target: @{ev.get('username', target.lstrip('@'))}\n"
            f"Link: {ev.get('link')}\nIDs: {ev.get('sample_ids',[])[:5]}\nBan request."
        )

    async def _send(self, acc: Account, bot: str, text: str) -> bool:
        if not acc.client:
            return False
        try:
            await acc.client.send_message(bot, text[:4000])
            self.n += 1
            self.on_log(f"[{acc.phone}] → @{bot}")
            return True
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds + 1)
            return False
        except Exception as e:
            self.on_log(f"bot @{bot} fail: {e}")
            return False

    async def run(self, accounts: List[Account], target: str, evidence: dict) -> int:
        if not accounts:
            return 0
        sh = accounts.copy()
        random.shuffle(sh)
        jobs = [
            (config.ABUSE_BOT, self._abuse(evidence, target)),
            (config.SEARCH_BOT, self._search(target, evidence)),
            (config.SCAM_BOT, self._scam(evidence, target)),
        ]
        for i, (bot, text) in enumerate(jobs):
            await self._send(sh[i % len(sh)], bot, text)
            await delay(3, 7)
        return self.n
