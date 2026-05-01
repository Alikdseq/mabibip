"""Кабинет автомагазина/разборки/автосалона. Namespace: shop_owner."""

from django.urls import path

from . import shop_owner_views

app_name = "shop_owner"

urlpatterns = [
    path("", shop_owner_views.dashboard, name="dashboard"),
    path("products/", shop_owner_views.products, name="products"),
    path("branches/", shop_owner_views.branches, name="branches"),
    path("branches/add/", shop_owner_views.branch_add, name="branch_add"),
    path("branches/<int:pk>/edit/", shop_owner_views.branch_edit, name="branch_edit"),
    path("branches/<int:pk>/delete/", shop_owner_views.branch_delete, name="branch_delete"),
]

