"""Central async rate limiter with FLOOD_WAIT respect."""
from __future__ import annotations
import asyncio
import time
from typing import Optional

class RateLimiter:
    def __init__(self, max_concurrent: int = 3, base_delay: float = 5.0):
        self.sem = asyncio.Semaphore(max_concurrent)
        self.base_delay = base_delay
        self._last_action = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        await self.sem.acquire()
        async with self._lock:
            now = time.monotonic()
            wait = self.base_delay - (now - self._last_action)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_action = time.monotonic()

    def release(self):
        self.sem.release()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, *args):
        self.release()

    async def handle_flood(self, seconds: int):
        await asyncio.sleep(seconds + 1)
