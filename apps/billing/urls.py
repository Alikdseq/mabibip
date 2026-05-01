from django.urls import path

from . import checkout_views
from . import wallet_views
from .views import yookassa_webhook

app_name = "billing"

urlpatterns = [
    path("webhooks/yookassa/", yookassa_webhook, name="yookassa_webhook"),
    path("yookassa/", checkout_views.yookassa_checkout_info, name="yookassa_checkout"),
    path("wallet/", wallet_views.wallet_home, name="wallet_home"),
    path("wallet/withdraw/", wallet_views.withdrawal_request_create, name="withdrawal_request_create"),
]

