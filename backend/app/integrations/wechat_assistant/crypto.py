import base64
import hashlib
import hmac
import os
from itertools import count

from app.core.config import get_settings


_VERSION = "v1"


def _key() -> bytes:
    settings = get_settings()
    material = (settings.jwt_secret or "talon-dev-secret").encode("utf-8")
    return hashlib.sha256(material + b":wechat-assistant").digest()


def _keystream(length: int, nonce: bytes) -> bytes:
    key = _key()
    chunks: list[bytes] = []
    for idx in count():
        chunks.append(hashlib.sha256(key + nonce + idx.to_bytes(4, "big")).digest())
        if sum(len(chunk) for chunk in chunks) >= length:
            return b"".join(chunks)[:length]
    raise RuntimeError("unreachable")


def protect_secret(value: str | None) -> str | None:
    if not value:
        return value
    nonce = os.urandom(12)
    raw = value.encode("utf-8")
    cipher = bytes(a ^ b for a, b in zip(raw, _keystream(len(raw), nonce)))
    mac = hmac.new(_key(), nonce + cipher, hashlib.sha256).digest()[:16]
    payload = base64.urlsafe_b64encode(nonce + mac + cipher).decode("ascii")
    return f"{_VERSION}:{payload}"


def reveal_secret(value: str | None) -> str | None:
    if not value:
        return value
    if not value.startswith(f"{_VERSION}:"):
        return value
    payload = base64.urlsafe_b64decode(value.split(":", 1)[1].encode("ascii"))
    nonce, mac, cipher = payload[:12], payload[12:28], payload[28:]
    expected = hmac.new(_key(), nonce + cipher, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(mac, expected):
        return None
    raw = bytes(a ^ b for a, b in zip(cipher, _keystream(len(cipher), nonce)))
    return raw.decode("utf-8")
