from django.contrib import admin

from .models import ChatRoom, Message, StationDirectMessage, StationDirectThread


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ("booking", "is_closed", "created_at")
    list_filter = ("is_closed",)
    search_fields = ("booking__id", "booking__station__name", "booking__client__phone")
    autocomplete_fields = ("booking",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("room", "sender", "created_at", "read_by_client", "read_by_owner")
    list_filter = ("read_by_client", "read_by_owner")
    search_fields = ("text",)
    autocomplete_fields = ("room", "sender")


@admin.register(StationDirectThread)
class StationDirectThreadAdmin(admin.ModelAdmin):
    list_display = ("station", "client", "last_message_at", "owner_archived_at")
    list_filter = ("owner_archived_at",)
    search_fields = ("station__name", "station__slug", "client__phone")
    autocomplete_fields = ("station", "client")


@admin.register(StationDirectMessage)
class StationDirectMessageAdmin(admin.ModelAdmin):
    list_display = ("thread", "sender", "created_at")
    search_fields = ("text",)
    autocomplete_fields = ("thread", "sender")

