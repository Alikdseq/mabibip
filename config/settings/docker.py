"""Настройки для запуска в Docker (Gunicorn + PostgreSQL, HTTP без TLS внутри контейнера)."""

from __future__ import annotations

import os

from .base import *  # noqa: F403, F405
from .gis_database import postgres_gis_from_database_url

_db_url = os.environ.get("DATABASE_URL", "").strip()
if not _db_url:
    raise ValueError("DATABASE_URL is required (PostgreSQL URL)")

_pg = postgres_gis_from_database_url(_db_url)
if not _pg:
    raise ValueError("DATABASE_URL must be postgres:// or postgresql://")

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
        raise ValueError("DATABASE_REPLICA_URL must be postgres:// or postgresql://")
    DATABASES["replica"] = {**_rep, "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", "60"))}

DEBUG = os.environ.get("DEBUG", "0").strip().lower() in ("1", "true", "yes")

# Логи: в docker выводим traceback 500 в stdout (чтобы видеть причину OAuth ошибок).
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

# В Docker без .env часто нет ключей капчи — подключаем тестовые v3 (можно отключить RECAPTCHA_USE_GOOGLE_TEST_KEYS=0).
if (
    not RECAPTCHA_SITE_KEY  # noqa: F405
    and not RECAPTCHA_SECRET_KEY  # noqa: F405
    and not RECAPTCHA_SKIP  # noqa: F405
    and os.environ.get("RECAPTCHA_USE_GOOGLE_TEST_KEYS", "1").strip().lower() in ("1", "true", "yes")
):
    RECAPTCHA_SITE_KEY = "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"  # noqa: F405
    RECAPTCHA_SECRET_KEY = "6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe"  # noqa: F405
# В docker-compose (локально) медиа раздаём приложением, чтобы отображались загруженные фото.
# В проде медиа должен отдавать reverse-proxy / CDN.
SERVE_MEDIA = os.environ.get("SERVE_MEDIA", "1").strip().lower() in ("1", "true", "yes")

SECRET_KEY = os.environ.get("SECRET_KEY", "").strip()
if not SECRET_KEY:
    raise ValueError("SECRET_KEY is required")

_hosts = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1,web").strip()
ALLOWED_HOSTS = [h for h in (s.strip() for s in _hosts.split(",")) if h]

# По умолчанию HTTP (локальный docker compose). За HTTPS-прокси выставить в env.
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "0").strip().lower() in (
    "1",
    "true",
    "yes",
)
SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0").strip().lower() in (
    "1",
    "true",
    "yes",
)
CSRF_COOKIE_SECURE = os.environ.get("CSRF_COOKIE_SECURE", "0").strip().lower() in (
    "1",
    "true",
    "yes",
)

# Если контейнер стоит за HTTPS reverse-proxy (Nginx/Traefik), включите:
#   USE_X_FORWARDED_HOST=1
#   SECURE_PROXY_SSL_HEADER=1
USE_X_FORWARDED_HOST = os.environ.get("USE_X_FORWARDED_HOST", "0").strip().lower() in ("1", "true", "yes")
if os.environ.get("SECURE_PROXY_SSL_HEADER", "0").strip().lower() in ("1", "true", "yes"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

_csrf = os.environ.get(
    "CSRF_TRUSTED_ORIGINS",
    "http://localhost:8000,http://127.0.0.1:8000",
)
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf.split(",") if o.strip()]

_mw = list(MIDDLEWARE)
_ws = "whitenoise.middleware.WhiteNoiseMiddleware"
if _ws not in _mw:
    try:
        _i = _mw.index("django.middleware.security.SecurityMiddleware")
    except ValueError:
        _i = 0
    _mw.insert(_i + 1, _ws)
MIDDLEWARE = _mw

STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

_email_backend_env = os.environ.get("EMAIL_BACKEND")
if _email_backend_env:
    EMAIL_BACKEND = _email_backend_env
else:
    EMAIL_BACKEND = (
        "django.core.mail.backends.smtp.EmailBackend"
        if os.environ.get("EMAIL_HOST", "").strip()
        else "django.core.mail.backends.console.EmailBackend"
    )

# Фаза F3: Redis (hold) и брокер Celery.
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0").strip()
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/1").strip()
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)

# Pytest inside docker-compose often runs with DJANGO_SETTINGS_MODULE=config.settings.docker.
# Provide sane defaults for test runs (no external reCAPTCHA calls; Axes disabled because
# django.test.Client.login() authenticates without a request object).
# PYTEST_VERSION — на всю сессию; PYTEST_CURRENT_TEST — не во всех воркерах/этапах виден стабильно.
if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("PYTEST_VERSION"):
    RECAPTCHA_SKIP = True
    AXES_ENABLED = False
    AUTHENTICATION_BACKENDS = [
        "django.contrib.auth.backends.ModelBackend",
    ]
