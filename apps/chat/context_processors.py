"""Данные для шаблонов, связанные с чатом / Channels."""

from __future__ import annotations

from django.conf import settings


def channels_ws_client_base(request):
    return {
        "channels_ws_client_base": getattr(settings, "CHANNELS_WS_CLIENT_BASE_URL", "") or "",
    }
