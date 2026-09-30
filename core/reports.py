import asyncio
from typing import List, Dict, Any, Optional, Callable
from telethon.tl.functions.messages import ReportRequest
from telethon.tl.functions.account import ReportPeerRequest
from telethon.tl.types import (
    InputReportReasonChildAbuse, InputReportReasonSpam,
    InputReportReasonViolence, InputReportReasonPornography,
    InputReportReasonCopyright, InputReportReasonOther, InputReportReasonFake,
)
from telethon.errors import FloodWaitError
import config
from core.logger import log
from core.db import StateDB
from core.helpers import delay, weighted_reason, report_comment
from core.accounts import Account

REASON_MAP = {
    "child_abuse": InputReportReasonChildAbuse(),
    "spam": InputReportReasonSpam(),
    "violence": InputReportReasonViolence(),
    "pornography": InputReportReasonPornography(),
    "copyright": InputReportReasonCopyright(),
    "scam": InputReportReasonFake(),
    "other": InputReportReasonOther(),
}


class ReportEngine:
    def __init__(self, db: StateDB, cid: int, on_log: Callable = None):
        self.db = db
        self.cid = cid
        self.ok = 0
        self.fail = 0
        self._pause = asyncio.Event()
        self._pause.set()
        self._lock = asyncio.Lock()
        self.on_log = on_log or (lambda m: None)

    async def _flood_pause(self, sec: int):
        async with self._lock:
            if not self._pause.is_set():
                return
            self._pause.clear()
            self.on_log(f"FloodWait global pause {sec}s")
            await asyncio.sleep(min(sec, config.FLOOD_GLOBAL_PAUSE))
            self._pause.set()

    async def one(self, acc: Account, target: str, evidence: dict) -> bool:
        await self._pause.wait()
        if not acc.client:
            return False
        reason = weighted_reason()
        comment = report_comment(reason, evidence, target)
        tl = REASON_MAP.get(reason, InputReportReasonOther())
        try:
            entity = await acc.client.get_entity(target.lstrip("@"))
            ids = evidence.get("sample_ids", [])[:5]
            if ids:
                await acc.client(ReportRequest(peer=entity, id=ids, reason=tl, message=comment[:200]))
            else:
                await acc.client(ReportPeerRequest(peer=entity, reason=tl, message=comment[:200]))
            self.ok += 1
            acc.reports_this_wave += 1
            await self.db.inc_reports(acc.phone)
            await self.db.log_report(self.cid, acc.phone, target, reason, True, comment[:80])
            self.on_log(f"[{acc.phone}] report OK ({reason})")
            return True
        except FloodWaitError as e:
            self.fail += 1
            await self.db.log_report(self.cid, acc.phone, target, reason, False, f"FW {e.seconds}")
            if e.seconds > 30:
                await self._flood_pause(e.seconds)
            else:
                await asyncio.sleep(e.seconds + 1)
            return False
        except Exception as e:
            self.fail += 1
            await self.db.log_report(self.cid, acc.phone, target, reason, False, str(e)[:100])
            self.on_log(f"[{acc.phone}] report fail: {e}")
            return False

    async def wave(self, accounts: List[Account], target: str, evidence: dict, per_acc: int):
        workers = min(config.REPORT_WORKERS, max(1, len(accounts)))
        self.on_log(f"Report wave {len(accounts)} acc × {per_acc} | workers={workers}")
        q: asyncio.Queue = asyncio.Queue()
        for a in accounts:
            for _ in range(per_acc):
                await q.put(a)

        async def worker():
            while True:
                try:
                    a = q.get_nowait()
                except asyncio.QueueEmpty:
                    break
                if a.reports_this_wave >= per_acc:
                    q.task_done()
                    continue
                await self.one(a, target, evidence)
                await delay()
                q.task_done()

        await asyncio.gather(*[asyncio.create_task(worker()) for _ in range(workers)])
        self.on_log(f"Wave done OK={self.ok} FAIL={self.fail}")
        return self.ok, self.fail
