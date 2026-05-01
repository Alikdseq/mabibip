from __future__ import annotations

from typing import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse


def _csp_value() -> str:
    """
    Pragmatic CSP for server-rendered Django templates.
    - No 'unsafe-inline' for scripts: current templates include inline scripts, so this will likely
      require follow-up refactors (move scripts to static, or add nonce support).
    - For now, keep CSP opt-in via settings.CSP_ENABLED to avoid breaking UI unexpectedly.
    """
    def _join(directive: str, values: list[str]) -> str:
        parts = [directive, "'self'"] + values
        return " ".join([p for p in parts if p])

    script_allow = list(getattr(settings, "CSP_SCRIPT_SRC_ALLOW", []) or [])
    style_allow = list(getattr(settings, "CSP_STYLE_SRC_ALLOW", []) or [])
    font_allow = list(getattr(settings, "CSP_FONT_SRC_ALLOW", []) or [])
    connect_allow = list(getattr(settings, "CSP_CONNECT_SRC_ALLOW", []) or [])

    # Strict by default (no inline scripts). Inline styles remain allowed because Bootstrap/templates
    # currently include inline style blocks/attributes.
    return "; ".join(
        [
            "default-src 'self'",
            "base-uri 'self'",
            "object-src 'none'",
            "frame-ancestors 'none'",
            "img-src 'self' data: https:",
            _join("font-src", ["data:"] + font_allow),
            "style-src 'self' 'unsafe-inline' " + " ".join(style_allow),
            _join("script-src", script_allow),
            _join("connect-src", connect_allow),
            "form-action 'self'",
            "upgrade-insecure-requests",
        ]
    )


class SecurityHeadersMiddleware:
    """
    Centralized security headers.
    Keep app-level headers even if you also set them on Nginx (defense in depth).
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        resp = self.get_response(request)

        # Avoid overriding if upstream already sets them (e.g. Nginx).
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        resp.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")

        if getattr(settings, "CSP_ENABLED", False):
            resp.headers.setdefault("Content-Security-Policy", _csp_value())

        return resp

