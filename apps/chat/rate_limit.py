from __future__ import annotations

from django.conf import settings


def _redis_client():
    fake = getattr(settings, "TEST_FAKEREDIS_CLIENT", None)
    if fake is not None:
        return fake
    import redis

    url = getattr(settings, "REDIS_URL", "") or ""
    if not url:
        raise RuntimeError("REDIS_URL не задан (или используйте TEST_FAKEREDIS_CLIENT в тестах).")
    return redis.Redis.from_url(url, decode_responses=True)


def allow_message_send(*, user_id: int) -> bool:
    """
    Простая защита от флуда: N сообщений за T секунд.
    Храним только счётчик (без ПДн).
    """
    limit = int(getattr(settings, "CHAT_RATE_LIMIT_COUNT", 20))
    window = int(getattr(settings, "CHAT_RATE_LIMIT_WINDOW_SECONDS", 10))
    key = f"chat_flood:{int(user_id)}"
    r = _redis_client()
    cur = r.incr(key)
    if cur == 1:
        r.expire(key, window)
    return cur <= limit

