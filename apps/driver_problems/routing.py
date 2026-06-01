from django.urls import re_path

from .consumers import ProblemsFeedConsumer

websocket_urlpatterns = [
    re_path(r"^ws/problems/feed/$", ProblemsFeedConsumer.as_asgi()),
]
