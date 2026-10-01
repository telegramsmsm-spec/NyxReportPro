"""Unique natural-language report message generator."""
from __future__ import annotations
import json
import random
from pathlib import Path
from typing import List, Dict

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

OPENERS = [
    "I would like to report the following public channel for clear violations of Telegram Terms of Service.",
    "Please review this public channel that is distributing prohibited content.",
    "Reporting a public Telegram channel that appears to violate platform rules.",
    "This is a formal report regarding public content that breaks Telegram's terms.",
    "I am submitting evidence of ToS violations found in a public channel.",
    "Kindly investigate the linked public channel for repeated rule breaches.",
]

CLOSERS = [
    "Thank you for reviewing this report.",
    "I appreciate your attention to this matter.",
    "Please take appropriate action based on the evidence provided.",
    "Looking forward to your moderation decision.",
    "Evidence links are included above for verification.",
]

class TemplateEngine:
    def __init__(self):
        self.report_templates = {}
        self.email_templates = {}
        self._load()

    def _load(self):
        rp = TEMPLATES_DIR / "report_messages.json"
        ep = TEMPLATES_DIR / "email_bodies.json"
        if rp.exists():
            self.report_templates = json.loads(rp.read_text(encoding="utf-8"))
        if ep.exists():
            self.email_templates = json.loads(ep.read_text(encoding="utf-8"))

    def generate_report_message(self, reason: str, target_link: str, evidence_links: List[str], account_idx: int = 0) -> str:
        base = self.report_templates.get(reason, self.report_templates.get("other", "Report for {reason}: {target}"))
        opener = OPENERS[account_idx % len(OPENERS)]
        closer = CLOSERS[account_idx % len(CLOSERS)]
        links = evidence_links[:]
        random.seed(account_idx + hash(target_link) % 10000)
        random.shuffle(links)
        evidence_block = "\n".join(f"- {l}" for l in links[:15])
        body = base.format(reason=reason, target=target_link, evidence=evidence_block)
        return f"{opener}\n\nTarget: {target_link}\n\nEvidence posts:\n{evidence_block}\n\n{body}\n\n{closer}"

    def generate_email(self, reason: str, target_link: str, evidence_links: List[str], idx: int = 0) -> tuple:
        tpl = self.email_templates.get(reason, self.email_templates.get("other", {}))
        subject = tpl.get("subject", "Report: Telegram channel ToS violation").format(target=target_link, reason=reason)
        body_tpl = tpl.get("body", "Please review {target}\n\n{evidence}")
        links = evidence_links[:]
        random.seed(idx + 42)
        random.shuffle(links)
        evidence_block = "\n".join(links[:20])
        body = body_tpl.format(target=target_link, evidence=evidence_block, reason=reason)
        if idx % 2 == 0:
            body = "Dear Telegram Moderation Team,\n\n" + body
        else:
            body = "To the Telegram Abuse Desk,\n\n" + body
        body += "\n\nThis report is submitted in good faith with publicly available evidence."
        return subject, body
