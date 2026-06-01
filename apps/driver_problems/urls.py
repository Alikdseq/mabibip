from django.urls import path

from . import views

app_name = "driver_problems"

urlpatterns = [
    path("", views.problems_board, name="board"),
    path("create/", views.problem_create, name="create"),
    path("<int:pk>/claim/", views.problem_claim, name="claim"),
]
