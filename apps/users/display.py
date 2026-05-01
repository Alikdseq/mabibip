"""Как показывать пользователя в интерфейсе: имя из профиля, иначе телефон."""

from __future__ import annotations


def user_display_name(user, *, fallback: str = "") -> str:
    if user is None:
        return (fallback or "Пользователь").strip() or "Пользователь"
    fn = (getattr(user, "first_name", None) or "").strip()
    ln = (getattr(user, "last_name", None) or "").strip()
    composed = " ".join(p for p in (fn, ln) if p).strip()
    if composed:
        return composed
    ph = (getattr(user, "phone", None) or "").strip()
    if ph:
        return ph
    fb = (fallback or "Пользователь").strip()
    return fb or "Пользователь"


def user_avatar_url(user) -> str | None:
    if user is None:
        return None
    av = getattr(user, "avatar", None)
    if not av:
        return None
    try:
        return av.url
    except (ValueError, AttributeError):
        return None
