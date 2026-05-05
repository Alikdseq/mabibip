"""
Базовые настройки Django. Секреты и флаги — из окружения (фаза 1.1.2).
"""

import os
from datetime import timedelta
from pathlib import Path

from celery.schedules import crontab
from dotenv import load_dotenv
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_list(name: str) -> list[str]:
    return [h.strip() for h in os.environ.get(name, "").split(",") if h.strip()]

def _csp_list(name: str) -> list[str]:
    return [v.strip() for v in os.environ.get(name, "").split(",") if v.strip()]


SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-dev-only-change-in-env",
)

DEBUG = _env_bool("DEBUG", default=False)

ALLOWED_HOSTS: list[str] = _env_list("ALLOWED_HOSTS")

# CSRF: allow known https origins (e.g. ngrok on staging).
CSRF_TRUSTED_ORIGINS = _env_list("CSRF_TRUSTED_ORIGINS")

# Каталог и онлайн-запись: не требовать оплаченную подписку для тарифа Basic (все активные СТО «как Free»).
# Выключите (false), когда снова нужно скрывать Basic без subscription_paid_until / с просрочкой.
CATALOG_BYPASS_SUBSCRIPTION = _env_bool("CATALOG_BYPASS_SUBSCRIPTION", default=True)

# Объявления: подменный номер для звонков покупателя (нужен входящий номер платформы + АТС/Twilio).
CLASSIFIEDS_PROXY_CALL_ENABLED = _env_bool("CLASSIFIEDS_PROXY_CALL_ENABLED", default=False)
CLASSIFIEDS_PROXY_PUBLIC_PHONE_E164 = os.getenv("CLASSIFIEDS_PROXY_PUBLIC_PHONE_E164", "").strip()

# Карта на аналитическом дашборде (опционально)
YANDEX_MAPS_API_KEY = os.getenv("YANDEX_MAPS_API_KEY", "")

# Интерактивная карта каталога / «рядом» (выкл. на старте; включите MAP_FEATURE_ENABLED=1 в .env)
MAP_FEATURE_ENABLED = _env_bool("MAP_FEATURE_ENABLED", default=False)

INSTALLED_APPS = [
    "config.admin_apps.ProMasterAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.sitemaps",
    "django.contrib.humanize",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "channels",
    "simple_history",
    "imagekit",
    "axes",
    "import_export",
    "rest_framework",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.apple",
    "allauth.socialaccount.providers.vk",
    "apps.core",
    "apps.erp.apps.ErpConfig",
    "apps.users.apps.UsersConfig",
    "apps.legal",
    "apps.stations",
    "apps.bookings",
    "apps.reviews",
    "apps.audit.apps.AuditConfig",
    "apps.billing",
    "apps.chat",
    "apps.calls",
    "apps.classifieds",
    "apps.support.apps.SupportConfig",
]

# Порядок: SecurityMiddleware (заголовки), XFrameOptionsMiddleware (clickjacking) — фаза 9.1.1
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "apps.core.middleware.VisitorCityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
    "apps.core.security_headers.SecurityHeadersMiddleware",
    "apps.audit.middleware.AdminAuditMiddleware",
    "apps.legal.middleware.StoOfferConsentMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"

# django.contrib.sites: sitemap и абсолютные URL (домен синхронизируйте с SITE_BASE_URL).
SITE_ID = 1

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.users.context_processors.recaptcha_site_key",
                "apps.users.context_processors.vk_oauth",
                "apps.users.context_processors.email_verification_notice",
                "apps.users.context_processors.missing_email_notice",
                "apps.calls.context_processors.calls_flags",
                "apps.core.visitor_city.visitor_city_context",
                "apps.core.context_processors.nav_badges",
                "apps.core.context_processors.seo_canonical",
                "apps.core.context_processors.map_feature_enabled",
                "apps.core.context_processors.erp_city_expansion_banner",
                "apps.chat.context_processors.channels_ws_client_base",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [os.getenv("CHANNEL_REDIS_URL", "").strip() or os.getenv("REDIS_URL", "").strip() or "redis://127.0.0.1:6379/2"],
        },
    }
}

# Базовый URL WebSocket для браузера: wss://хост:порт (без пути). Пусто — из window.location
# (в dev при странице :8000 клиент сам подставляет :8001). За одним reverse-proxy/ngrok только на
# WSGI укажите URL до ASGI или настройте проксирование /ws/ на тот же хост.
CHANNELS_WS_CLIENT_BASE_URL = os.getenv("CHANNELS_WS_CLIENT_BASE_URL", "").strip()

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# Behind reverse-proxy/ngrok: trust X-Forwarded-* to build correct absolute URLs (OAuth redirect_uri must be https).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# Cookie hardening (works for both session auth + CSRF).
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SAMESITE = os.getenv("CSRF_COOKIE_SAMESITE", "Lax")

# CSP allowlists (when CSP_ENABLED=1)
CSP_SCRIPT_SRC_ALLOW = _csp_list("CSP_SCRIPT_SRC_ALLOW")
CSP_STYLE_SRC_ALLOW = _csp_list("CSP_STYLE_SRC_ALLOW")
CSP_FONT_SRC_ALLOW = _csp_list("CSP_FONT_SRC_ALLOW")
CSP_CONNECT_SRC_ALLOW = _csp_list("CSP_CONNECT_SRC_ALLOW")
CSP_FRAME_SRC_ALLOW = _csp_list("CSP_FRAME_SRC_ALLOW")

# Ведущий «/» обязателен: иначе на вложенных URL (например /sto/) относительные пути
# превращаются в /sto/static/... и дают 404.
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "users.User"

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesBackend",
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

AXES_FAILURE_LIMIT = int(os.getenv("AXES_FAILURE_LIMIT", "5"))
AXES_COOLOFF_TIME = timedelta(minutes=int(os.getenv("AXES_COOLOFF_MINUTES", "15")))
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_ENABLE_ADMIN = True
AXES_ENABLED = _env_bool("AXES_ENABLED", default=True)

LOGIN_URL = "users:login"
LOGIN_REDIRECT_URL = "/cabinet/"
LOGOUT_REDIRECT_URL = "/"

# Allauth (OAuth providers). Мы используем social-login как альтернативу телефону+паролю.
ACCOUNT_EMAIL_VERIFICATION = "none"
# Custom user uses phone as USERNAME_FIELD and has no `username`.
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
# Явно запрещаем username на уровне allauth (иначе system check падает).
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_USERNAME_MIN_LENGTH = 0
# Allauth must not require username; allow login by email only for allauth flows.
ACCOUNT_LOGIN_METHODS = {"email"}
# Поля формы `/oauth/.../signup/` (соцвход без email): только email — пароль задаётся через save_user соцадаптера.
ACCOUNT_SIGNUP_FIELDS = ["email*"]
ACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_AUTO_SIGNUP = True
# Если провайдер не отдал email — редирект на socialaccount_signup (шаблон socialaccount/signup.html).
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_ADAPTER = "apps.users.allauth_adapters.TachkiSocialAccountAdapter"
SOCIALACCOUNT_FORMS = {"signup": "apps.users.social_signup_form.TachkiSocialSignupForm"}
SOCIALACCOUNT_LOGIN_ON_GET = True

# Google OAuth: чтобы получать email (иначе allauth может создать user.email="",
# что конфликтует с уникальностью email в нашей модели).
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    }
}

# VK / VK ID (django-allauth): https://docs.allauth.org/en/latest/socialaccount/providers/vk.html
# В кабинете VK укажите redirect: https://<домен>/oauth/vk/login/callback/
# Дополнительно поддержан алиас /accounts/vk/login/callback/ → см. apps.users.views.vk_oauth_callback_alias
VK_CLIENT_ID = os.getenv("VK_CLIENT_ID", "").strip()
VK_CLIENT_SECRET = os.getenv("VK_CLIENT_SECRET", "").strip()
if VK_CLIENT_ID and VK_CLIENT_SECRET:
    SOCIALACCOUNT_PROVIDERS["vk"] = {
        "APP": [
            {
                "client_id": VK_CLIENT_ID,
                "secret": VK_CLIENT_SECRET,
                "key": "",
            }
        ],
        "SCOPE": ["email"],
    }

# Почта: если EMAIL_HOST задан — используем SMTP, иначе выводим письма в консоль (dev).
_email_backend_env = os.getenv("EMAIL_BACKEND")
if _email_backend_env:
    EMAIL_BACKEND = _email_backend_env
else:
    EMAIL_BACKEND = (
        "django.core.mail.backends.smtp.EmailBackend" if os.getenv("EMAIL_HOST", "").strip() else "django.core.mail.backends.console.EmailBackend"
    )
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = _env_bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = _env_bool("EMAIL_USE_SSL", default=False)
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "20"))
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "webmaster@localhost")

# F10: Sentry (опционально) — фильтрация ПДн.
SENTRY_DSN = os.getenv("SENTRY_DSN", "").strip()
SENTRY_ENVIRONMENT = os.getenv("SENTRY_ENVIRONMENT", "").strip() or ("prod" if not DEBUG else "dev")
SENTRY_TRACES_SAMPLE_RATE = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0"))

def _sentry_before_send(event, hint):
    # Минимизируем ПДн: телефон/email/ip/headers/cookies.
    request = event.get("request") or {}
    headers = request.get("headers") or {}
    for k in list(headers.keys()):
        lk = str(k).lower()
        if lk in {"cookie", "authorization", "x-csrftoken", "x-csrf-token"}:
            headers.pop(k, None)
    request["headers"] = headers
    request.pop("cookies", None)
    request.pop("query_string", None)
    event["request"] = request

    user = event.get("user") or {}
    for k in ("email", "ip_address", "username"):
        user.pop(k, None)
    event["user"] = user

    return event

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        environment=SENTRY_ENVIRONMENT,
        traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
        send_default_pii=False,
        before_send=_sentry_before_send,
    )

# Абсолютные ссылки в письмах, если нет HttpRequest (например тесты)
SITE_BASE_URL = os.getenv("SITE_BASE_URL", "").rstrip("/")
# VK ID One Tap: redirect_uri должен побайтно совпадать с URI в кабинете VK (иначе invalid_request).
# Если пусто — берётся origin текущего запроса + путь /accounts/vk/login/callback/ (см. context_processors.vk_oauth).
VK_ID_REDIRECT_URI = os.getenv("VK_ID_REDIRECT_URI", "").strip()

# Лимиты публичных форм (django-ratelimit); в тестах выключается в settings/tests.py.
RATELIMIT_ENABLE = _env_bool("RATELIMIT_ENABLE", default=True)

# WebRTC звонки (LiveKit + Channels). По умолчанию выключены до готовности инфраструктуры.
CALLS_ENABLED = _env_bool("CALLS_ENABLED", default=False)
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "").strip()
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "").strip()
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "").strip()
CALLS_RING_TIMEOUT_SEC = int(os.getenv("CALLS_RING_TIMEOUT_SEC", "30"))
CALLS_TOKEN_TTL_SEC = int(os.getenv("CALLS_TOKEN_TTL_SEC", "300"))

# Город по умолчанию в шапке/каталоге (District.city_label). Пустое значение в .env → первый город из справочника.
VISITOR_DEFAULT_CITY_LABEL = os.getenv("VISITOR_DEFAULT_CITY_LABEL", "Владикавказ").strip()
VISITOR_CITY_GUESS_FROM_IP = _env_bool("VISITOR_CITY_GUESS_FROM_IP", default=False)

# Объявления/антифрод: строгость правил для новых аккаунтов.
CONTACTS_STRICT_DAYS_FOR_NEW_USERS = int(os.getenv("CONTACTS_STRICT_DAYS_FOR_NEW_USERS", "7"))

# MVP: приложение только в одном городе — подпись как у District.city_label (напр. Владикавказ).
# Пустая строка в переменной окружения APP_FOCUS_CITY_LABEL= → показываются все города из БД (мультигород).
APP_FOCUS_CITY_LABEL = os.getenv("APP_FOCUS_CITY_LABEL", "Владикавказ").strip()

# GeoDjango: для локального dev без PostgreSQL — SpatiaLite (нужен модуль libspatialite в системе).
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.spatialite",
        "NAME": BASE_DIR / "db.sqlite3",
        "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "0")),
    }
}

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/day",
        "user": "1000/day",
        # Подсказки печатаются посимвольно (typeahead) → нужен высокий лимит.
        "search_suggest": "6000/hour",
        # Карта может дергать API при перемещении bbox.
        "map_places": "6000/hour",
        # Звонки (WebRTC): защита от спама на API уровне.
        "calls_initiate": "30/hour",
        "calls_action": "300/hour",
        # Объявления: раскрытие телефона по кнопке (дополнительно к DB-лимитам).
        "ads_reveal_phone": "120/hour",
        # Объявления: жалобы (HTMX).
        "ads_report": "30/hour",
    },
}

# Фаза F0: хранить IP при фиксации согласия — только по согласованию с юристом (минимизация ПДн, документ 07).
LEGAL_CONSENT_STORE_IP = _env_bool("LEGAL_CONSENT_STORE_IP", default=False)

# Фаза F1: SMS, капча, кэш для OTP rate limit
SMS_BACKEND = os.getenv("SMS_BACKEND", "console")

# Ключ сайта: RECAPTCHA_SITE_KEY или алиас из ТЗ RECAPTCHA_PUBLIC_KEY.
_RECAPTCHA_SITE = (
    os.getenv("RECAPTCHA_SITE_KEY", "").strip() or os.getenv("RECAPTCHA_PUBLIC_KEY", "").strip()
)
_RECAPTCHA_SECRET = (
    os.getenv("RECAPTCHA_SECRET_KEY", "").strip() or os.getenv("RECAPTCHA_PRIVATE_KEY", "").strip()
)
RECAPTCHA_SITE_KEY = _RECAPTCHA_SITE
# Секрет для verify_recaptcha (читается из settings и из os).
RECAPTCHA_SECRET_KEY = _RECAPTCHA_SECRET
RECAPTCHA_VERSION = os.getenv("RECAPTCHA_VERSION", "v3").strip().lower()  # v3 | v2
RECAPTCHA_MIN_SCORE = float(os.getenv("RECAPTCHA_MIN_SCORE", "0.5"))
RECAPTCHA_SKIP = _env_bool("RECAPTCHA_SKIP", default=False)
# Явно: RECAPTCHA_USE_GOOGLE_TEST_KEYS=1 — тестовые ключи Google v3 без отдельных RECAPTCHA_*.
if (
    not RECAPTCHA_SITE_KEY
    and not RECAPTCHA_SECRET_KEY
    and not RECAPTCHA_SKIP
    and _env_bool("RECAPTCHA_USE_GOOGLE_TEST_KEYS", default=False)
):
    RECAPTCHA_SITE_KEY = "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"
    RECAPTCHA_SECRET_KEY = "6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe"

# Caches / sessions: в prod/docker используем Redis; иначе LocMem.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-promaster",
    }
}

# Геокодирование адреса СТО (Nominatim; только фиксированный host в коде — см. apps/stations/geocoding.py, документ 07 B.1).
GEOCODING_ENABLED = _env_bool("GEOCODING_ENABLED", default=False)
GEOCODING_USER_AGENT = os.getenv(
    "GEOCODING_USER_AGENT",
    "ProMasterCatalog/1.0 (contact: support@example.com)",
)

# Кэш карточки СТО (фаза F2.1.5), секунды.
STATION_CARD_CACHE_TTL = int(os.getenv("STATION_CARD_CACHE_TTL", "900"))

# Фаза F3: Redis (hold слотов), Celery + Beat.
REDIS_URL = os.getenv("REDIS_URL", "").strip()
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "CONNECTION_POOL_KWARGS": {
                    "max_connections": int(os.getenv("REDIS_POOL_MAX_CONNECTIONS", "50")),
                    "retry_on_timeout": True,
                },
            },
            "TIMEOUT": int(os.getenv("CACHE_DEFAULT_TIMEOUT", "300")),
        }
    }
    SESSION_ENGINE = "django.contrib.sessions.backends.cache"
    SESSION_CACHE_ALIAS = "default"

SLOT_HOLD_KEY_PREFIX = os.getenv("SLOT_HOLD_KEY_PREFIX", "slot_hold:")
SLOT_HOLD_TTL_SECONDS = int(os.getenv("SLOT_HOLD_TTL_SECONDS", "900"))
SLOT_GENERATION_DAYS_AHEAD = int(os.getenv("SLOT_GENERATION_DAYS_AHEAD", "7"))

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/1")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True
CELERY_BEAT_SCHEDULE = {
    "expire-unconfirmed-bookings-every-10m": {
        "task": "apps.bookings.tasks.expire_unconfirmed_bookings",
        "schedule": crontab(minute="*/10"),
    },
    "booking-reminder-2h-every-10m": {
        "task": "apps.bookings.tasks.send_booking_reminders_2h",
        "schedule": crontab(minute="*/10"),
    },
    "generate-weekly-slots-msk-2am": {
        "task": "apps.bookings.tasks.generate_weekly_slots",
        "schedule": crontab(hour=2, minute=0),
    },
    "charge-due-subscriptions-msk-3am": {
        "task": "apps.billing.tasks.charge_due_subscriptions",
        "schedule": crontab(hour=3, minute=0),
    },
    "cancel-stale-classifieds-deals-every-5m": {
        "task": "apps.billing.tasks.cancel_stale_classifieds_deals",
        "schedule": crontab(minute="*/5"),
    },
    "auto-confirm-and-release-deals-every-5m": {
        "task": "apps.billing.tasks.auto_confirm_and_release_deals",
        "schedule": crontab(minute="*/5"),
    },
    "detect-review-anomalies-msk-4am": {
        "task": "apps.reviews.tasks.detect_review_anomalies",
        "schedule": crontab(hour=4, minute=0),
    },
    "prune-inactive-station-direct-chats-daily": {
        "task": "apps.chat.tasks.prune_inactive_station_direct_threads",
        "schedule": crontab(hour=5, minute=15),
    },
}

# Фаза F4: ЮKassa (вебхук / онлайн-оплата). Пока выключено — включите после настройки кабинета ЮKassa.
YOOKASSA_ENABLED = _env_bool("YOOKASSA_ENABLED", default=False)
YOOKASSA_WEBHOOK_SECRET = os.getenv("YOOKASSA_WEBHOOK_SECRET", "").strip()
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "").strip()
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "").strip()

# Safe Deal (classifieds): таймауты и авто-подтверждения
DEAL_PAYMENT_TIMEOUT_MINUTES = int(os.getenv("DEAL_PAYMENT_TIMEOUT_MINUTES", "30"))
DEAL_AUTO_CONFIRM_DAYS = int(os.getenv("DEAL_AUTO_CONFIRM_DAYS", "7"))

# ERP: подсветка «проблемных» сделок (пороги)
ERP_DEAL_PAYMENT_PENDING_MINUTES = int(os.getenv("ERP_DEAL_PAYMENT_PENDING_MINUTES", "30"))
ERP_DEAL_WAITING_SHIPMENT_HOURS = int(os.getenv("ERP_DEAL_WAITING_SHIPMENT_HOURS", "48"))

# Фаза F5: чат
CHAT_ATTACHMENT_MAX_BYTES = int(os.getenv("CHAT_ATTACHMENT_MAX_BYTES", str(5 * 1024 * 1024)))
CHAT_RATE_LIMIT_COUNT = int(os.getenv("CHAT_RATE_LIMIT_COUNT", "20"))
CHAT_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("CHAT_RATE_LIMIT_WINDOW_SECONDS", "10"))

# Фото профиля в ЛК (apps.users)
USER_AVATAR_MAX_BYTES = int(os.getenv("USER_AVATAR_MAX_BYTES", str(5 * 1024 * 1024)))

# Обращения в поддержку (apps.support)
SUPPORT_TICKET_BODY_MIN_LENGTH = int(os.getenv("SUPPORT_TICKET_BODY_MIN_LENGTH", "10"))
SUPPORT_MAX_NEW_TICKETS_PER_HOUR = int(os.getenv("SUPPORT_MAX_NEW_TICKETS_PER_HOUR", "5"))
# Полный текст авто-ответа; пусто в env → в services.py используется встроенный текст.
SUPPORT_TICKET_AUTO_ACK_TEXT = os.getenv("SUPPORT_TICKET_AUTO_ACK_TEXT", "").strip() or None

# F9: read replica feature flag (requires DATABASES["replica"]).
READ_REPLICA_ENABLED = _env_bool("READ_REPLICA_ENABLED", default=False)
DATABASE_ROUTERS = ["config.db_routers.PrimaryReplicaRouter"]
