from __future__ import annotations

import re


PHONE_LIKE_RE = re.compile(r"(?<!\d)(?:\+?7|8)?\s*\(?\s*\d{3}\s*\)?[\s\-]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}(?!\d)")
EMAIL_RE = re.compile(r"\b[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}\b", re.IGNORECASE)
MESSENGER_RE = re.compile(
    r"(?i)\b(?:t\.me/|telegram\.me/|wa\.me/|whatsapp|viber|vk\.me/|instagram\.com/|ig\.me/)\S+"
)


def validate_listing_text(text: str) -> list[str]:
    """
    Возвращает список причин, почему текст нужно отправить на модерацию/ограничить.
    Не бросаем исключения, чтобы callers могли выбирать стратегию (блок/премодерация).
    """
    t = (text or "").strip()
    if not t:
        return []
    reasons: list[str] = []
    if PHONE_LIKE_RE.search(t):
        reasons.append("phone")
    if EMAIL_RE.search(t):
        reasons.append("email")
    if MESSENGER_RE.search(t):
        reasons.append("messenger")
    return reasons

