from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings


@dataclass(frozen=True)
class CallsSettings:
    enabled: bool
    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str
    ring_timeout_sec: int
    token_ttl_sec: int


def calls_settings() -> CallsSettings:
    return CallsSettings(
        enabled=bool(getattr(settings, "CALLS_ENABLED", False)),
        livekit_url=str(getattr(settings, "LIVEKIT_URL", "") or "").strip(),
        livekit_api_key=str(getattr(settings, "LIVEKIT_API_KEY", "") or "").strip(),
        livekit_api_secret=str(getattr(settings, "LIVEKIT_API_SECRET", "") or "").strip(),
        ring_timeout_sec=int(getattr(settings, "CALLS_RING_TIMEOUT_SEC", 30) or 30),
        token_ttl_sec=int(getattr(settings, "CALLS_TOKEN_TTL_SEC", 300) or 300),
    )

