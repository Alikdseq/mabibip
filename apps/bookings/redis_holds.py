"""
Redis-hold слота на 15 минут (фаза F3.1.4, документ 07: TTL, в ключе только user_id).

SET slot_hold:{slot_id} {user_id} NX EX ttl; продление TTL, если hold уже у того же пользователя.
"""

from __future__ import annotations

import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def _redis_client():
    fake = getattr(settings, "TEST_FAKEREDIS_CLIENT", None)
    if fake is not None:
        return fake
    import redis

    url = getattr(settings, "REDIS_URL", "") or ""
    if not url:
        raise RuntimeError("REDIS_URL не задан (или используйте TEST_FAKEREDIS_CLIENT в тестах).")
    return redis.Redis.from_url(url, decode_responses=True)


def _hold_key(slot_id: int) -> str:
    prefix = getattr(settings, "SLOT_HOLD_KEY_PREFIX", "slot_hold:")
    return f"{prefix}{slot_id}"


def hold_ttl_seconds() -> int:
    return int(getattr(settings, "SLOT_HOLD_TTL_SECONDS", 900))


def acquire_or_refresh_slot_hold(slot_id: int, user_id: int) -> bool:
    """
    Пытается захватить hold. True — можно показывать форму записи.
    False — слот удерживает другой пользователь.
    """
    r = _redis_client()
    key = _hold_key(slot_id)
    ttl = hold_ttl_seconds()
    uid = str(int(user_id))
    try:
        if r.set(key, uid, nx=True, ex=ttl):
            return True
        owner = r.get(key)
        if owner is not None and owner == uid:
            r.expire(key, ttl)
            return True
    except Exception:
        logger.exception("redis hold acquire slot_id=%s", slot_id)
        raise
    return False


def delete_slot_hold(slot_id: int) -> None:
    """Снимает hold (после успешного создания заявки)."""
    try:
        _redis_client().delete(_hold_key(slot_id))
    except Exception:
        logger.exception("redis hold delete slot_id=%s", slot_id)
        raise


def get_slot_hold_user_id(slot_id: int) -> int | None:
    """ID пользователя, удержавшего слот, или None."""
    try:
        raw = _redis_client().get(_hold_key(slot_id))
    except Exception:
        logger.exception("redis hold get slot_id=%s", slot_id)
        raise
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None
