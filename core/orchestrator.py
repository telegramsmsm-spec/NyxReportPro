"""Full campaign runner – used by UI and CLI."""
import asyncio
import shutil
from typing import Callable, Optional
from pathlib import Path

import config
from core.logger import log, utc_now
from core.db import StateDB
from core.accounts import AccountPool
from core.proxy_engine import ProxyEngine
from core.content import ContentHarvester
from core.reports import ReportEngine
from core.bots import BotEscalation
from core.email_layer import EmailLayer
from core.helpers import norm_user


class Orchestrator:
    def __init__(self, on_log: Callable = None, on_status: Callable = None):
        self.on_log = on_log or (lambda m: log.info(m))
        self.on_status = on_status or (lambda s: None)
        self._stop = asyncio.Event()
        self.running = False

    def clean_temp(self):
        if config.TEMP.exists():
            for p in config.TEMP.iterdir():
                try:
                    if p.is_file():
                        p.unlink()
                    else:
                        shutil.rmtree(p, ignore_errors=True)
                except Exception:
                    pass
        config.TEMP.mkdir(parents=True, exist_ok=True)
        self.on_log("Temp cleaned")

    async def run(
        self,
        target: str,
        proxy_channels: list,
        posts: int,
        emails: int,
        reports_per_acc: int,
    ):
        if self.running:
            self.on_log("Already running")
            return
        self.running = True
        self._stop.clear()
        target = norm_user(target)
        self.clean_temp()
        self.on_status("starting")
        self.on_log("=" * 50)
        self.on_log(f"START @{target} {utc_now()}")
        self.on_log(f"posts={posts} emails={emails} rpa={reports_per_acc} proxy_ch={proxy_channels}")

        db = StateDB()
        await db.connect()
        cid = await db.start_campaign(target)

        pool = AccountPool(db, on_log=self.on_log)
        try:
            pool.load()
        except Exception as e:
            self.on_log(f"Load accounts failed: {e}")
            await db.close()
            self.running = False
            self.on_status("error")
            return

        alive = await pool.health()
        if not alive:
            self.on_log("Zero alive accounts – use Login tab first")
            await db.finish_campaign(cid, 0, 0, 0, 0, "no alive")
            await db.close()
            self.running = False
            self.on_status("error")
            return

        pool.start_keepalive()
        client0 = alive[0].client

        proxy_eng = ProxyEngine(client0, db, on_log=self.on_log)
        await proxy_eng.load_seed()
        if proxy_channels:
            proxy_eng.start_loop(proxy_channels)

        free = await db.free_proxies(limit=len(alive))
        need = [a for a in alive if not a.proxy_raw]
        for a, px in zip(need, free):
            pool.set_proxy(a, px)
            await db.assign_proxy(px, a.phone)
            self.on_log(f"[{a.phone}] proxy assigned")

        harvester = ContentHarvester(client0)
        self.on_status("harvesting")
        evidence = await harvester.harvest(target, limit=posts)
        self.on_log(f"Evidence posts={evidence.get('posts_fetched',0)}")

        if self._stop.is_set():
            await self._shutdown(pool, proxy_eng, db, cid, 0, 0, 0, 0)
            return

        engine = ReportEngine(db, cid, on_log=self.on_log)
        bots = BotEscalation(on_log=self.on_log)
        mail = EmailLayer(on_log=self.on_log)

        self.on_status("reporting")
        self.on_log("Launching reports + bots + emails…")

        async def rjob():
            return await engine.wave(alive, target, evidence, reports_per_acc)

        async def bjob():
            return await bots.run(alive, target, evidence)

        async def ejob():
            return await mail.run(evidence, emails)

        results = await asyncio.gather(rjob(), bjob(), ejob(), return_exceptions=True)

        rok, rfail = (0, 0)
        bn, en = 0, 0
        if isinstance(results[0], tuple):
            rok, rfail = results[0]
        else:
            self.on_log(f"reports err: {results[0]}")
        if isinstance(results[1], int):
            bn = results[1]
        else:
            self.on_log(f"bots err: {results[1]}")
        if isinstance(results[2], int):
            en = results[2]
        else:
            self.on_log(f"email err: {results[2]}")

        await self._shutdown(pool, proxy_eng, db, cid, rok, rfail, en, bn)
        self.on_log("=" * 50)
        self.on_log(f"DONE reports_ok={rok} fail={rfail} bots={bn} emails={en}")
        self.on_log("=" * 50)
        self.on_status("done")
        self.running = False

    async def _shutdown(self, pool, proxy_eng, db, cid, ok, fail, emails, bots):
        try:
            await proxy_eng.stop()
        except Exception:
            pass
        try:
            await pool.stop()
        except Exception:
            pass
        try:
            await db.finish_campaign(cid, ok, fail, emails, bots, "ok")
            await db.close()
        except Exception:
            pass
        self.clean_temp()

    def request_stop(self):
        self._stop.set()
        self.on_log("Stop requested…")
