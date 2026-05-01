from django.urls import path

from apps.chat import api_views

app_name = "chat_api"

urlpatterns = [
    path("inbox/summary/", api_views.HeaderInboxSummaryAPIView.as_view(), name="inbox_summary"),
    path("chats/", api_views.ChatRoomListAPIView.as_view(), name="chat_list"),
    path("chats/<int:room_id>/messages/", api_views.ChatMessageListAPIView.as_view(), name="chat_messages"),
    path("chats/<int:room_id>/messages/send/", api_views.ChatMessageCreateAPIView.as_view(), name="chat_message_send"),
    path("chats/<int:room_id>/read/", api_views.ChatMarkReadAPIView.as_view(), name="chat_mark_read"),
    path("toast-events/seen/", api_views.ToastEventsMarkSeenAPIView.as_view(), name="toast_events_seen"),
]

