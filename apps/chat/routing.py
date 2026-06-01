from django.urls import re_path

from .consumers import ChatConsumer
from .ad_direct_consumer import AdDirectChatConsumer
from .station_direct_consumer import StationDirectChatConsumer
from .sto_owner_inbox_consumer import StoOwnerInboxConsumer
from .user_inbox_consumer import UserInboxConsumer
from apps.calls.consumer import CallsConsumer
from apps.driver_help.routing import websocket_urlpatterns as help_ws
from apps.driver_problems.routing import websocket_urlpatterns as problems_ws

websocket_urlpatterns = [
    re_path(r"^ws/chat/(?P<booking_id>\d+)/$", ChatConsumer.as_asgi()),
    re_path(r"^ws/station-direct/(?P<thread_id>\d+)/$", StationDirectChatConsumer.as_asgi()),
    re_path(r"^ws/ad-direct/(?P<thread_id>\d+)/$", AdDirectChatConsumer.as_asgi()),
    re_path(r"^ws/sto-owner/inbox/$", StoOwnerInboxConsumer.as_asgi()),
    re_path(r"^ws/user-inbox/$", UserInboxConsumer.as_asgi()),
    re_path(r"^ws/calls/$", CallsConsumer.as_asgi()),
] + help_ws + problems_ws

