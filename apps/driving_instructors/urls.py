from django.urls import path

from . import views

app_name = "driving_instructors"

urlpatterns = [
    path("", views.InstructorListView.as_view(), name="list"),
    path("<slug:slug>/", views.InstructorDetailView.as_view(), name="detail"),
]
