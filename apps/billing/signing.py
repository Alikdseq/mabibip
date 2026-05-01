from __future__ import annotations

import hmac
import hashlib


def hmac_sha256_hex(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest((a or "").strip().lower(), (b or "").strip().lower())

