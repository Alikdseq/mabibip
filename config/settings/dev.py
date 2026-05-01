"""Локальная разработка (фаза 1.1.6)."""

import os
from pathlib import Path

from .base import *  # noqa: F403, F405
from .gis_database import postgres_gis_from_database_url

# GeoDjango (SpatiaLite/PostGIS) на Windows требует явный путь к GDAL/GEOS DLL, иначе
# ImproperlyConfigured: Could not find the GDAL library.
_gdal = os.environ.get("GDAL_LIBRARY_PATH", "").strip()
_geos = os.environ.get("GEOS_LIBRARY_PATH", "").strip()
if _gdal:
    GDAL_LIBRARY_PATH = _gdal  # noqa: F405
if _geos:
    GEOS_LIBRARY_PATH = _geos  # noqa: F405
if not _gdal and os.name == "nt":
    _osgeo_bin = Path(r"C:\OSGeo4W\bin")
    if _osgeo_bin.is_dir():
        _cands = sorted(_osgeo_bin.glob("gdal3*.dll"), reverse=True)
        if not _cands:
            _cands = list(_osgeo_bin.glob("gdal.dll"))
        if _cands:
            GDAL_LIBRARY_PATH = str(_cands[0])  # noqa: F405
        _geos_dll = _osgeo_bin / "geos_c.dll"
        if _geos_dll.is_file():
            GEOS_LIBRARY_PATH = str(_geos_dll)  # noqa: F405

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

# reCAPTCHA v3: без ключей в .env подставляем тестовые Google (иначе скрипт api.js не грузится).
if (
    not RECAPTCHA_SITE_KEY  # noqa: F405
    and not RECAPTCHA_SECRET_KEY  # noqa: F405
    and not RECAPTCHA_SKIP  # noqa: F405
):
    RECAPTCHA_SITE_KEY = "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"  # noqa: F405
    RECAPTCHA_SECRET_KEY = "6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe"  # noqa: F405

if not os.environ.get("REDIS_URL", "").strip():
    import fakeredis

    TEST_FAKEREDIS_CLIENT = fakeredis.FakeRedis(decode_responses=True)

_db_url = os.environ.get("DATABASE_URL", "").strip()
if _db_url:
    pg = postgres_gis_from_database_url(_db_url)
    if pg:
        DATABASES = {"default": pg}  # noqa: F405

INSTALLED_APPS = [
    *INSTALLED_APPS,  # noqa: F405
    "django_extensions",
]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
