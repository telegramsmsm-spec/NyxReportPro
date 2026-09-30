import json
import random
from email.message import EmailMessage
from pathlib import Path
from typing import Dict, Any, Callable
import aiosmtplib
import config
from core.logger import log, utc_now
from core.helpers import delay, ref_id

SUBJECTS = [
    "URGENT ABUSE REPORT – @{target} – {vtype} – {ts}",
    "Child safety / illegal content – @{target}",
    "Scam & fraud – ban request – @{target}",
    "Copyright + ToS – @{target}",
    "Spam / ToS breach – @{target}",
]


class EmailLayer:
    def __init__(self, on_log: Callable = None):
        self.smtp = []
        self.sent = 0
        self.failed = 0
        self.on_log = on_log or (lambda m: None)

    def load(self):
        if not config.SMTP_FILE.exists():
            return
        self.smtp = json.loads(config.SMTP_FILE.read_text(encoding="utf-8"))

    def _body(self, ev: dict, vtype: str) -> str:
        links = "\n".join(f"- {l}" for l in ev.get("sample_links", [])[:10])
        ids = ", ".join(str(i) for i in ev.get("sample_ids", [])[:15])
        excerpts = "\n".join(f'  "{e}"' for e in ev.get("excerpts", [])[:5])
        return f"""Hello Telegram Abuse / Trust & Safety,

Target: @{ev.get('username')} / {ev.get('link')}
Type: {ev.get('entity_type')}
Title: {ev.get('title')}
Violations: {vtype}

Evidence:
{links or '- (see IDs)'}
Message IDs: {ids or 'n/a'}
Excerpts:
{excerpts or 'n/a'}
Dates: {ev.get('date_range') or 'n/a'}
Views sample: {ev.get('total_views_sampled', 0)}
Participants: {ev.get('participants') or 'n/a'}

Request: permanent restriction / removal / ban.
Submitted in good faith under Telegram ToS.

Ref: {ref_id()}
Time: {utc_now()}

Compliance System
"""

    async def _send(self, smtp, to, subject, body) -> bool:
        msg = EmailMessage()
        msg["From"] = f"{smtp.get('from_name','Reporter')} <{smtp['user']}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        try:
            await aiosmtplib.send(
                msg, hostname=smtp["host"], port=int(smtp.get("port", 587)),
                username=smtp["user"], password=smtp["password"],
                start_tls=smtp.get("use_tls", True), timeout=30,
            )
            self.sent += 1
            self.on_log(f"Email → {to}")
            return True
        except Exception as e:
            self.failed += 1
            self.on_log(f"Email fail {to}: {e}")
            return False

    async def run(self, evidence: dict, volume: int) -> int:
        self.load()
        if not self.smtp:
            self.on_log("No SMTP – skip email layer")
            return 0
        target = evidence.get("username", "target")
        vtypes = ["spam/scam", "ToS", "harmful content", "copyright", "child safety", "violence"]
        for i in range(volume):
            smtp = self.smtp[i % len(self.smtp)]
            box = config.MAILBOXES[i % len(config.MAILBOXES)]
            vt = random.choice(vtypes)
            sub = random.choice(SUBJECTS).format(target=target, vtype=vt.split("/")[0], ts=utc_now())
            body = self._body(evidence, vt)
            await self._send(smtp, box, sub, body)
            await delay(1.5, 5.0)
        self.on_log(f"Emails sent={self.sent} fail={self.failed}")
        return self.sent
