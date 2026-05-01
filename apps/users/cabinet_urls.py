"""Личный кабинет клиента (фаза 6–B)."""

from django.urls import path

from . import cabinet_views
from apps.chat import booking_chat_views
from apps.chat import unified_chat_views

app_name = "cabinet"

urlpatterns = [
    path("bookings/", cabinet_views.ClientBookingListView.as_view(), name="bookings"),
    path("profile/", cabinet_views.ClientProfileView.as_view(), name="profile"),
    path("profile/contact-phone/change/", cabinet_views.ContactPhoneChangeRequestView.as_view(), name="contact_phone_change"),
    path("cars/", cabinet_views.SavedCarListView.as_view(), name="cars"),
    path("cars/add/", cabinet_views.SavedCarCreateView.as_view(), name="car_add"),
    path("cars/<int:pk>/edit/", cabinet_views.SavedCarUpdateView.as_view(), name="car_edit"),
    path("cars/<int:pk>/delete/", cabinet_views.SavedCarDeleteView.as_view(), name="car_delete"),
    path("favorites/", cabinet_views.FavoritesHubView.as_view(), name="favorites"),
    path("favorites/ads/", cabinet_views.FavoritesHubView.as_view(), name="favorite_ads"),
    path(
        "favorites/toggle/<slug:slug>/",
        cabinet_views.favorite_toggle,
        name="favorite_toggle",
    ),
    path(
        "favorites/shops/toggle/<slug:slug>/",
        cabinet_views.favorite_shop_toggle,
        name="favorite_shop_toggle",
    ),
    path("reviews/", cabinet_views.ClientReviewListView.as_view(), name="reviews"),
    path(
        "reviews/<int:booking_pk>/",
        cabinet_views.ClientReviewCreateView.as_view(),
        name="review_create",
    ),
    path(
        "reviews/<int:pk>/edit/",
        cabinet_views.ClientReviewUpdateView.as_view(),
        name="review_edit",
    ),
    path(
        "bookings/<int:pk>/cancel/",
        cabinet_views.client_booking_cancel,
        name="booking_cancel",
    ),
    path(
        "bookings/<int:pk>/reschedule/accept/",
        cabinet_views.client_booking_reschedule_accept,
        name="booking_reschedule_accept",
    ),
    path(
        "bookings/<int:pk>/reschedule/decline/",
        cabinet_views.client_booking_reschedule_decline,
        name="booking_reschedule_decline",
    ),
    path("chats/", unified_chat_views.cabinet_chats_unified, name="chats"),
    path("chats/<int:room_id>/", booking_chat_views.cabinet_chat_detail, name="chat_detail"),
    path("chats/direct/<int:thread_id>/", unified_chat_views.cabinet_direct_chat_detail, name="direct_chat_detail"),
    path("chats/ads/<int:thread_id>/", unified_chat_views.cabinet_ad_direct_chat_detail, name="ad_direct_chat_detail"),
    path("chats/ads/<int:thread_id>/send/", unified_chat_views.ad_direct_thread_send, name="ad_direct_thread_send"),
    path("support/", cabinet_views.ClientSupportListView.as_view(), name="support"),
    path("support/create/", cabinet_views.client_support_create, name="support_create"),
    path("support/<int:pk>/", cabinet_views.ClientSupportDetailView.as_view(), name="support_detail"),
    path("", cabinet_views.CabinetHubView.as_view(), name="index"),
]
