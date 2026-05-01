"""ЛК владельца СТО (фаза 5). Namespace: sto_owner."""

from django.urls import path

from apps.chat import station_chat_views
from apps.chat import booking_chat_views
from apps.chat import unified_chat_views

from . import owner_views

app_name = "sto_owner"

urlpatterns = [
    path(
        "pending-moderation/",
        owner_views.StoModerationPendingView.as_view(),
        name="pending_moderation",
    ),
    path(
        "moderation-rejected/",
        owner_views.StoModerationRejectedView.as_view(),
        name="moderation_rejected",
    ),
    path("", owner_views.StoOwnerDashboardView.as_view(), name="dashboard"),
    path(
        "dashboard/bookings-all-more/",
        owner_views.dashboard_bookings_all_more,
        name="dashboard_bookings_all_more",
    ),
    path("chats/", unified_chat_views.sto_owner_chats_unified, name="chats"),
    path("chats/direct/<int:thread_id>/", unified_chat_views.sto_owner_direct_chat_detail, name="direct_chat_detail"),
    path("booking-chats/", booking_chat_views.sto_owner_booking_chat_list, name="booking_chats"),
    path("booking-chats/<int:room_id>/", booking_chat_views.sto_owner_booking_chat_detail, name="booking_chat_detail"),
    path("chats/settings/", station_chat_views.sto_owner_chat_settings, name="direct_chat_settings"),
    path("chats/delete/", station_chat_views.sto_owner_chat_bulk_delete, name="direct_chat_bulk_delete"),
    path("chats/reply/", station_chat_views.sto_owner_chat_reply, name="direct_chat_reply"),
    path("billing-required/", owner_views.BillingRequiredView.as_view(), name="billing_required"),
    path("stations/", owner_views.OwnerStationsView.as_view(), name="stations"),
    path("masters/", owner_views.OwnerMastersView.as_view(), name="masters"),
    path("masters/add/", owner_views.MasterCreateView.as_view(), name="master_add"),
    path("masters/<int:pk>/update/", owner_views.master_update, name="master_update"),
    path("masters/<int:pk>/inherit/", owner_views.master_inherit, name="master_inherit"),
    path("masters/<int:pk>/delete/", owner_views.master_delete, name="master_delete"),
    path("bays/", owner_views.OwnerBaysView.as_view(), name="bays"),
    path("bays/add/", owner_views.WorkBayCreateView.as_view(), name="bay_add"),
    path("bays/<int:pk>/delete/", owner_views.bay_delete, name="bay_delete"),
    path(
        "stations/<slug:slug>/brands/",
        owner_views.StationBrandsUpdateView.as_view(),
        name="station_brands",
    ),
    path(
        "stations/<slug:slug>/profile/",
        owner_views.StationProfileEditView.as_view(),
        name="station_profile",
    ),
    path(
        "slots/quick-today/",
        owner_views.dashboard_quick_slot_today,
        name="dashboard_quick_slot",
    ),
    path("slots/add/", owner_views.TimeSlotCreateView.as_view(), name="slot_add"),
    path("slots/calendar/", owner_views.SlotCalendarView.as_view(), name="slot_calendar"),
    path("slots/<int:pk>/toggle/", owner_views.slot_toggle_block, name="slot_toggle_block"),
    path("bookings/<int:pk>/reschedule-slots/", owner_views.booking_reschedule_slots, name="booking_reschedule_slots"),
    path("bookings/<int:pk>/propose-reschedule/", owner_views.booking_propose_reschedule, name="booking_propose_reschedule"),
    path("bookings/<int:pk>/confirm/", owner_views.booking_confirm, name="booking_confirm"),
    path("bookings/<int:pk>/reject/", owner_views.booking_reject, name="booking_reject"),
    path("bookings/<int:pk>/start/", owner_views.booking_start, name="booking_start"),
    path("bookings/<int:pk>/complete/", owner_views.booking_complete, name="booking_complete"),
    path("reviews/", owner_views.OwnerReviewListView.as_view(), name="reviews"),
    path(
        "reviews/<int:review_pk>/reply/",
        owner_views.OwnerReviewReplyView.as_view(),
        name="review_reply",
    ),
    path(
        "reviews/<int:review_pk>/complaint/",
        owner_views.review_complaint,
        name="review_complaint",
    ),
]
