"""ASGI config (F5: Django Channels + WebSocket)."""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.conf import settings
from django.core.asgi import get_asgi_application
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

django_asgi_app = get_asgi_application()

# Импорт роутинга после инициализации Django, иначе модели могут загрузиться раньше времени
# и упасть с AppRegistryNotReady.
import apps.chat.routing  # noqa: E402

# In production, static should be served by reverse-proxy/CDN.
# For local docker-compose / staging, allow serving /static from ASGI too.
if settings.DEBUG or os.environ.get("SERVE_ASGI_STATIC", "0").strip().lower() in ("1", "true", "yes"):
    django_asgi_app = ASGIStaticFilesHandler(django_asgi_app)

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(URLRouter(apps.chat.routing.websocket_urlpatterns)),
    }
)
