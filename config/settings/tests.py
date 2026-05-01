"""Pytest / CI: PostGIS (TEST_DATABASE_URL) или SpatiaLite на файле (фаза F2)."""

import os

import fakeredis

from .base import *  # noqa: F403
from .gis_database import postgres_gis_from_database_url

SECRET_KEY = "test-secret-key-not-for-production"

DEBUG = True
ALLOWED_HOSTS = ["testserver", "localhost"]

_test_pg_url = os.getenv("TEST_DATABASE_URL", "").strip()
_pg = postgres_gis_from_database_url(_test_pg_url) if _test_pg_url else None
if _pg:
    # pytest-django создаёт БД с префиксом test_; на том же хосте, что и URL (Docker: db).
    DATABASES = {"default": _pg}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.contrib.gis.db.backends.spatialite",
            "NAME": BASE_DIR / "test_gis.sqlite3",  # noqa: F405
        }
    }

# F9: в тестах добавляем "replica" (sqlite fallback) для проверки router logic.
if _pg:
    # Replica uses the same Postgres connection in CI/docker tests.
    DATABASES["replica"] = {**_pg}
else:
    DATABASES["replica"] = {
        "ENGINE": DATABASES["default"]["ENGINE"],
        "NAME": (BASE_DIR / "test_replica.sqlite3"),  # noqa: F405
    }

READ_REPLICA_ENABLED = False

# Регрессии каталога / тарифов Basic должны выполняться со строгой видимостью (как в проде без bypass).
CATALOG_BYPASS_SUBSCRIPTION = False

# Тесты создают города «Тестград», «ГородА», «Москва» и т.д. — без одного города.
APP_FOCUS_CITY_LABEL = ""
VISITOR_DEFAULT_CITY_LABEL = ""

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Фаза F1: тесты без внешних вызовов Google reCAPTCHA; axes отключаем в общем прогоне (включается в test_f1).
RECAPTCHA_SKIP = True
AXES_ENABLED = False
# Иначе регрессионные тесты регистрации упрутся в лимит 3/час с одного IP.
RATELIMIT_ENABLE = False
# Один backend по умолчанию в тестах (login() без явного backend); axes включается точечно в test_f1.
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

# Фаза F3: изолированный Redis для тестов hold (без реального сервера).
TEST_FAKEREDIS_CLIENT = fakeredis.FakeRedis(decode_responses=True)
