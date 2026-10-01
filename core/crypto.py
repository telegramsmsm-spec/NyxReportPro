"""Secret encryption helpers using Fernet."""
from __future__ import annotations
import base64
import os
from pathlib import Path
from cryptography.fernet import Fernet

KEY_FILE = Path(__file__).resolve().parent.parent / "data" / ".key"


def _get_or_create_key() -> bytes:
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    try:
        os.chmod(KEY_FILE, 0o600)
    except Exception:
        pass
    return key


def encrypt(text: str) -> str:
    if not text:
        return ""
    f = Fernet(_get_or_create_key())
    return f.encrypt(text.encode()).decode()


def decrypt(token: str) -> str:
    if not token:
        return ""
    f = Fernet(_get_or_create_key())
    return f.decrypt(token.encode()).decode()
