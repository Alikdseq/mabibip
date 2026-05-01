from __future__ import annotations

from django.conf import settings


def calls_flags(request):
    return {
        "calls_enabled": bool(getattr(settings, "CALLS_ENABLED", False)),
    }

