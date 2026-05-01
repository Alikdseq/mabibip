from django.urls import path

from apps.chat import station_chat_views

from . import views

app_name = "stations"

urlpatterns = [
    path("", views.StationListView.as_view(), name="list"),
    path("nearby/", views.NearbyStationsMapView.as_view(), name="nearby_map"),
    path("<slug:slug>/chat/panel/", station_chat_views.station_chat_panel, name="station_chat_panel"),
    path("<slug:slug>/chat/send/", station_chat_views.station_chat_send, name="station_chat_send"),
    path("<slug:slug>/book/done/", views.BookingSuccessView.as_view(), name="booking_success"),
    path("<slug:slug>/slots/", views.station_slots_partial, name="slots_partial"),
    path("<slug:slug>/book/<int:slot_id>/form/", views.booking_form_partial, name="booking_form"),
    path("<slug:slug>/book/<int:slot_id>/submit/", views.booking_submit, name="booking_submit"),
    path("<slug:slug>/", views.StationDetailView.as_view(), name="detail"),
]
