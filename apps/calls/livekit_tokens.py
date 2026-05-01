from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model

from .settings import calls_settings


class LiveKitNotConfigured(RuntimeError):
    pass


def _identity_for_user(user_id: int) -> str:
    return f"user_{int(user_id)}"


def issue_room_token(*, user, room_name: str) -> str:
    """
    Выдаёт JWT для подключения к комнате LiveKit.

    Реализовано через пакет `livekit-api` (server SDK). Комната в LiveKit может быть создана
    лениво при первом подключении — отдельный вызов create_room не обязателен.
    """
    s = calls_settings()
    if not (s.livekit_api_key and s.livekit_api_secret and s.livekit_url):
        raise LiveKitNotConfigured("LiveKit не настроен (LIVEKIT_URL/LIVEKIT_API_KEY/LIVEKIT_API_SECRET).")

    # Импортируем лениво, чтобы проект мог стартовать даже без зависимости в окружении.
    try:
        from livekit import api  # type: ignore
    except Exception as e:  # pragma: no cover
        raise LiveKitNotConfigured("Не установлен пакет livekit-api.") from e

    User = get_user_model()
    display = ""
    try:
        display = (getattr(user, "get_full_name", lambda: "")() or "").strip()
    except Exception:
        display = ""
    if not display:
        display = (getattr(user, "phone", "") or getattr(user, "email", "") or f"User #{getattr(user, 'pk', '')}").strip()

    tok = (
        api.AccessToken(api_key=s.livekit_api_key, api_secret=s.livekit_api_secret)
        .with_identity(_identity_for_user(int(user.pk)))
        .with_name(display[:120])
        .with_ttl(timedelta(seconds=int(s.token_ttl_sec)))
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=str(room_name),
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
            )
        )
        .to_jwt()
    )
    return str(tok)

