import pytest
from django.urls import reverse
from django.utils import timezone

from apps.billing.models import ClassifiedsDeal
from apps.classifieds.models import Ad, AdKind
from apps.users.models import User


@pytest.mark.django_db
def test_deals_reports_redirects_non_superuser(client):
    u = User.objects.create_user(phone="+79990002101", password="x")
    client.force_login(u)
    r = client.get(reverse("erp:deals_report"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_deals_reports_render_for_superuser(client):
    admin = User.objects.create_user(phone="+79990002102", password="x", is_superuser=True)
    seller = User.objects.create_user(phone="+79990002103", password="x")
    buyer = User.objects.create_user(phone="+79990002104", password="x")
    ad = Ad.objects.create(
        owner=seller,
        kind=AdKind.PART,
        title="Двигатель",
        price=1000,
        city_label="Москва",
        is_published=True,
    )
    ClassifiedsDeal.objects.create(
        ad=ad,
        buyer=buyer,
        seller=seller,
        amount=1000,
        currency="RUB",
        status=ClassifiedsDeal.Status.WAITING_SHIPMENT,
        paid_at=timezone.now(),
        provider_payment_id="pay-erp-1",
    )

    client.force_login(admin)
    assert client.get(reverse("erp:deals_report")).status_code == 200
    assert client.get(reverse("erp:deals_report_xlsx")).status_code == 200
    assert client.get(reverse("erp:deals_users_report")).status_code == 200
    assert client.get(reverse("erp:deals_users_report_xlsx")).status_code == 200
    assert client.get(reverse("erp:deals_cities_report")).status_code == 200
    assert client.get(reverse("erp:deals_cities_report_xlsx")).status_code == 200

