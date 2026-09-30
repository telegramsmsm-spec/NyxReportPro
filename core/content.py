from datetime import datetime, timezone
from typing import Dict, Any, List
from telethon import TelegramClient
from telethon.tl.types import Message, Channel, Chat, User
from core.logger import log
from core.helpers import norm_user


class ContentHarvester:
    def __init__(self, client: TelegramClient):
        self.client = client

    async def harvest(self, target: str, limit: int = 80) -> Dict[str, Any]:
        username = norm_user(target)
        log.info(f"Harvest @{username} limit={limit}")
        try:
            entity = await self.client.get_entity(username)
        except Exception as e:
            log.error(f"resolve @{username}: {e}")
            return self._empty(username)

        et = "channel"
        if isinstance(entity, Channel):
            et = "channel" if entity.broadcast else "group"
        elif isinstance(entity, Chat):
            et = "group"
        elif isinstance(entity, User):
            et = "user"

        title = getattr(entity, "title", None) or getattr(entity, "first_name", username)
        parts = getattr(entity, "participants_count", None)
        messages = await self.client.get_messages(entity, limit=limit)

        posts, ids, excerpts, dates = [], [], [], []
        views = 0
        for msg in messages:
            if not isinstance(msg, Message):
                continue
            ids.append(msg.id)
            text = (msg.message or "")[:300]
            ds = msg.date.strftime("%Y-%m-%d %H:%M") if msg.date else ""
            if msg.date:
                dates.append(msg.date)
            v = getattr(msg, "views", 0) or 0
            views += v
            link = f"https://t.me/{username}/{msg.id}"
            posts.append({"id": msg.id, "text": text, "date": ds, "views": v, "link": link})
            if text.strip():
                excerpts.append(text.strip()[:120])

        dr = ""
        if dates:
            s = sorted(dates)
            dr = f"{s[0].strftime('%Y-%m-%d')} → {s[-1].strftime('%Y-%m-%d')}"

        pack = {
            "username": username,
            "title": title,
            "entity_type": et,
            "link": f"https://t.me/{username}",
            "participants": parts,
            "posts_fetched": len(posts),
            "sample_ids": ids[:20],
            "sample_links": [p["link"] for p in posts[:10]],
            "excerpts": excerpts[:8],
            "date_range": dr,
            "total_views_sampled": views,
            "posts": posts,
            "harvested_at": datetime.now(timezone.utc).isoformat(),
        }
        log.info(f"Evidence: {len(posts)} posts type={et}")
        return pack

    def _empty(self, username: str) -> Dict[str, Any]:
        return {
            "username": username, "title": username, "entity_type": "unknown",
            "link": f"https://t.me/{username}", "participants": None,
            "posts_fetched": 0, "sample_ids": [], "sample_links": [],
            "excerpts": [], "date_range": "", "total_views_sampled": 0,
            "posts": [], "harvested_at": datetime.now(timezone.utc).isoformat(),
        }
