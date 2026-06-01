from django.urls import re_path

from .consumers import HelpFeedConsumer

websocket_urlpatterns = [
    re_path(r"^ws/help/feed/$", HelpFeedConsumer.as_asgi()),
]
