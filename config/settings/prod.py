"""Продакшен (фаза 1.1.7)."""

import os

from .base import *  # noqa: F403, F405
from .gis_database import postgres_gis_from_database_url

DEBUG = False

# Static files in production:
# - Prefer serving /static via reverse-proxy/CDN.
# - WhiteNoise is a safe fallback inside the app (requires `collectstatic`).
_mw = list(MIDDLEWARE)  # noqa: F405
_ws = "whitenoise.middleware.WhiteNoiseMiddleware"
if _ws not in _mw:
    try:
        _i = _mw.index("django.middleware.security.SecurityMiddleware")
    except ValueError:
        _i = 0
    _mw.insert(_i + 1, _ws)
MIDDLEWARE = _mw  # noqa: F405

STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()]
if not ALLOWED_HOSTS:
    raise ValueError("ALLOWED_HOSTS must be set in production")

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY or SECRET_KEY == "django-insecure-dev-only-change-in-env":
    raise ValueError("SECRET_KEY must be set in production")
if SECRET_KEY.strip() == "change-me":
    raise ValueError("SECRET_KEY must not use placeholder value")

_db_url = os.environ.get("DATABASE_URL", "").strip()
if not _db_url:
    raise ValueError("DATABASE_URL must be set in production")

_pg = postgres_gis_from_database_url(_db_url)
if not _pg:
    raise ValueError("DATABASE_URL must be a postgres:// or postgresql:// URL")

DATABASES = {
    "default": {
        **_pg,
        "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", "60")),
    }
}

_replica_url = os.environ.get("DATABASE_REPLICA_URL", "").strip()
if _replica_url:
    _rep = postgres_gis_from_database_url(_replica_url)
    if not _rep:
        raise ValueError("DATABASE_REPLICA_URL must be a postgres:// or postgresql:// URL")
    DATABASES["replica"] = {**_rep, "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", "60"))}

_redis_url = os.environ.get("REDIS_URL", "").strip()
if not _redis_url:
    raise ValueError("REDIS_URL must be set in production (удержание слотов, см. фаза F3).")
REDIS_URL = _redis_url
_celery_broker = os.environ.get("CELERY_BROKER_URL", "").strip()
if _celery_broker:
    CELERY_BROKER_URL = _celery_broker
    CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", _celery_broker).strip() or _celery_broker

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Enable CSP in prod once inline scripts are moved out.
# Keep off by default to avoid breaking current templates during development.
CSP_ENABLED = os.environ.get("CSP_ENABLED", "0").strip().lower() in ("1", "true", "yes")

# Default CDN allowlists (override in env to self-host later).
if CSP_ENABLED:
    CSP_SCRIPT_SRC_ALLOW = [
        "https://cdn.jsdelivr.net",
        "https://unpkg.com",
        "https://www.google.com",
        "https://api-maps.yandex.ru",
    ]
    # VK ID SDK (UMD с unpkg) часто использует eval/new Function — без этого браузер режет скрипт.
    # Отключите явно: CSP_SCRIPT_ALLOW_UNSAFE_EVAL=0
    if os.environ.get("CSP_SCRIPT_ALLOW_UNSAFE_EVAL", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    ):
        CSP_SCRIPT_SRC_ALLOW.append("'unsafe-eval'")
    CSP_STYLE_SRC_ALLOW = [
        "https://cdn.jsdelivr.net",
        "https://fonts.googleapis.com",
        "https://unpkg.com",
    ]
    CSP_FONT_SRC_ALLOW = [
        "https://fonts.gstatic.com",
    ]
    CSP_CONNECT_SRC_ALLOW = [
        "https://id.vk.com",
        "https://id.vk.ru",
        "https://oauth.vk.com",
        "https://login.vk.ru",
        "https://api.vk.com",
    ]
    CSP_FRAME_SRC_ALLOW = [
        "https://id.vk.com",
        "https://id.vk.ru",
        "https://login.vk.ru",
        "https://oauth.vk.com",
    ]

# За HTTPS отвечает reverse-proxy (Nginx). Django должен корректно понимать исходный протокол/host.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# Раздача /media/ через Django, если фронт Nginx не проксирует файлы (staging). В проде обычно Nginx/CDN.
SERVE_MEDIA = os.environ.get("SERVE_MEDIA", "0").strip().lower() in ("1", "true", "yes")

_csrf = os.environ.get("CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf.split(",") if o.strip()]
if not CSRF_TRUSTED_ORIGINS:
    raise ValueError(
        "CSRF_TRUSTED_ORIGINS must be set in production "
        "(comma-separated HTTPS origins, e.g. https://example.com)"
    )

_email_host = os.environ.get("EMAIL_HOST", "").strip()
if _email_host:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"  # noqa: F405
    EMAIL_HOST = _email_host  # noqa: F405
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))  # noqa: F405
    EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")  # noqa: F405
    EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")  # noqa: F405
    EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").strip().lower() in (  # noqa: F405
        "1",
        "true",
        "yes",
    )
    _from = os.environ.get("DEFAULT_FROM_EMAIL", "").strip()
    if _from:
        DEFAULT_FROM_EMAIL = _from  # noqa: F405

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}
