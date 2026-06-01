from django.urls import path

from . import views

app_name = "instructor_owner"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("profile/", views.profile_edit, name="profile_edit"),
]
