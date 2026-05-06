"""Логирование клика «Позвонить» и агрегаты ERP по объявлениям."""

import pytest
from django.urls import reverse

from apps.classifieds.erp_stats import platform_classifieds_stats_context
from apps.classifieds.models import Ad, AdCallClickEvent, AdKind, CarDealType
from apps.users.models import User


@pytest.mark.django_db
def test_ad_call_click_creates_event_for_non_owner(client):
    owner = User.objects.create_user(phone="+79991110010", password="x")
    buyer = User.objects.create_user(phone="+79991110011", password="x")
    ad = Ad.objects.create(
        owner=owner,
        kind=AdKind.PART,
        title="Bolt",
        price=100,
        is_published=True,
    )
    client.force_login(buyer)
    url = reverse("classifieds:ad_call_click", kwargs={"pk": ad.pk})
    r = client.post(url)
    assert r.status_code == 204
    assert AdCallClickEvent.objects.filter(ad=ad, user=buyer).count() == 1


@pytest.mark.django_db
def test_ad_call_click_owner_does_not_create_row(client):
    owner = User.objects.create_user(phone="+79991110012", password="x")
    ad = Ad.objects.create(
        owner=owner,
        kind=AdKind.CAR,
        title="Car",
        price=1,
        car_deal_type=CarDealType.SALE,
        is_published=True,
    )
    client.force_login(owner)
    url = reverse("classifieds:ad_call_click", kwargs={"pk": ad.pk})
    r = client.post(url)
    assert r.status_code == 204
    assert AdCallClickEvent.objects.count() == 0


@pytest.mark.django_db
def test_ad_call_click_requires_login(client):
    owner = User.objects.create_user(phone="+79991110013", password="x")
    ad = Ad.objects.create(
        owner=owner,
        kind=AdKind.PART,
        title="X",
        price=1,
        is_published=True,
    )
    url = reverse("classifieds:ad_call_click", kwargs={"pk": ad.pk})
    r = client.post(url)
    assert r.status_code == 302


@pytest.mark.django_db
def test_ad_call_click_post_only(client):
    owner = User.objects.create_user(phone="+79991110014", password="x")
    buyer = User.objects.create_user(phone="+79991110015", password="x")
    ad = Ad.objects.create(
        owner=owner,
        kind=AdKind.PART,
        title="Y",
        price=1,
        is_published=True,
    )
    client.force_login(buyer)
    url = reverse("classifieds:ad_call_click", kwargs={"pk": ad.pk})
    assert client.get(url).status_code == 405


@pytest.mark.django_db
def test_platform_classifieds_stats_active_ads():
    owner = User.objects.create_user(phone="+79991110016", password="x")
    Ad.objects.create(owner=owner, kind=AdKind.PART, title="P", price=1, is_published=True)
    Ad.objects.create(owner=owner, kind=AdKind.CAR, title="C", price=2, car_deal_type=CarDealType.SALE, is_published=True)
    Ad.objects.create(owner=owner, kind=AdKind.CAR, title="Draft", price=3, car_deal_type=CarDealType.SALE, is_published=False)
    ctx = platform_classifieds_stats_context()
    assert ctx["ads_active_published"] == {"part": 1, "car": 1, "total": 2}


@pytest.mark.django_db
def test_erp_classifieds_report_superuser_only(client):
    staff = User.objects.create_user(phone="+79991110017", password="x", is_superuser=False)
    admin = User.objects.create_user(phone="+79991110018", password="x", is_superuser=True)
    url = reverse("erp:classifieds_stats")
    assert client.get(url).status_code == 302
    client.force_login(staff)
    assert client.get(url).status_code == 403
    client.force_login(admin)
    assert client.get(url).status_code == 200
