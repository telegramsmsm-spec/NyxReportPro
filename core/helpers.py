import asyncio
import random
import re
import string
from typing import Optional, Dict, Any, Tuple, List

import config


async def delay(lo=None, hi=None):
    lo = lo if lo is not None else config.REPORT_DELAY_MIN
    hi = hi if hi is not None else config.REPORT_DELAY_MAX
    await asyncio.sleep(random.uniform(lo, hi))


def device():
    return {
        "device_model": random.choice(config.DEVICE_MODELS),
        "system_version": random.choice(config.SYSTEM_VERSIONS),
        "app_version": random.choice(config.APP_VERSIONS),
        "lang_code": random.choice(["en", "en", "es", "de", "ar"]),
        "system_lang_code": "en-US",
    }


def weighted_reason():
    return random.choices(
        list(config.REPORT_REASONS.keys()),
        weights=list(config.REPORT_REASONS.values()),
        k=1,
    )[0]


def report_comment(reason: str, evidence: dict, target: str) -> str:
    templates = [
        "This {type} distributes {reason} material. Posts {ids}. Action required.",
        "Repeated {reason} on @{target}. Evidence IDs: {ids}. Restrict please.",
        "ToS breach ({reason}) on this {type}. Sample IDs {ids}. Ban requested.",
        "Users flagging {reason} from @{target}. Links/IDs: {ids}. Take down.",
        "Documented {reason} activity. Posts {ids}. Permanent restriction request.",
    ]
    ids = evidence.get("sample_ids", [])[:5]
    id_str = ", ".join(str(i) for i in ids) if ids else "recent"
    return random.choice(templates).format(
        type=evidence.get("entity_type", "channel"),
        reason=reason.replace("_", " "),
        target=target.lstrip("@"),
        ids=id_str,
    )


def ref_id():
    return "NX-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))


PROXY_RE = re.compile(
    r"(?:(?P<proto>socks5|socks4|http|https|mtproto)://)?"
    r"(?:(?P<user>[^:@\s]+):(?P<pass>[^@\s]+)@)?"
    r"(?P<host>[\w\.\-]+):(?P<port>\d{2,5})",
    re.I,
)


def parse_proxy(line: str) -> Optional[Dict[str, Any]]:
    line = (line or "").strip()
    if not line or line.startswith("#"):
        return None
    m = PROXY_RE.search(line)
    if not m:
        return None
    d = m.groupdict()
    proto = (d.get("proto") or "socks5").lower()
    raw = (
        f"{proto}://{d['user']}:{d['pass']}@{d['host']}:{d['port']}"
        if d.get("user")
        else f"{proto}://{d['host']}:{d['port']}"
    )
    return {
        "proto": proto,
        "host": d["host"],
        "port": int(d["port"]),
        "user": d.get("user"),
        "password": d.get("pass"),
        "raw": raw,
    }


def to_telethon_proxy(p: Optional[dict]):
    if not p or p.get("proto") == "mtproto":
        return None
    import socks
    mp = {"socks5": socks.SOCKS5, "socks4": socks.SOCKS4, "http": socks.HTTP, "https": socks.HTTP}
    return (mp.get(p["proto"], socks.SOCKS5), p["host"], p["port"], True, p.get("user"), p.get("password"))


def extract_proxies(text: str) -> List[dict]:
    out = []
    for m in PROXY_RE.finditer(text or ""):
        p = parse_proxy(m.group(0))
        if p:
            out.append(p)
    return out


def norm_user(u: str) -> str:
    u = (u or "").strip()
    if "t.me/" in u:
        u = u.split("t.me/")[-1].split("/")[0].split("?")[0]
    return u.lstrip("@")


def load_api_keys() -> List[Tuple[int, str]]:
    keys = []
    if not config.API_KEYS_FILE.exists():
        return keys
    for line in config.API_KEYS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        a, h = line.split(":", 1)
        try:
            keys.append((int(a.strip()), h.strip()))
        except ValueError:
            continue
    return keys


def load_phones() -> List[str]:
    if not config.PHONES_FILE.exists():
        return []
    out = []
    for line in config.PHONES_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            if not line.startswith("+"):
                line = "+" + line
            out.append(line)
    return out


def random_api_key(keys: List[Tuple[int, str]]) -> Tuple[int, str]:
    if not keys:
        raise RuntimeError("No API keys in data/api_keys.txt")
    return random.choice(keys)
