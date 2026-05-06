"""Просмотры и избранное на деталке объявления."""

import pytest
from django.urls import reverse

from apps.classifieds.models import Ad, AdKind, CarDealType, FavoriteAd
from apps.users.models import User


@pytest.mark.django_db
def test_ad_detail_increments_view_count_once_per_session(client):
    owner = User.objects.create_user(phone="+79991110001", password="x")
    ad = Ad.objects.create(
        owner=owner,
        kind=AdKind.CAR,
        title="Test car",
        price=100_000,
        car_deal_type=CarDealType.SALE,
        is_published=True,
    )
    url = reverse("classifieds:ad_detail", kwargs={"pk": ad.pk})

    assert ad.view_count == 0

    client.get(url)
    ad.refresh_from_db()
    assert ad.view_count == 1

    client.get(url)
    ad.refresh_from_db()
    assert ad.view_count == 1


@pytest.mark.django_db
def test_ad_detail_favorite_count_in_context(client):
    owner = User.objects.create_user(phone="+79991110002", password="x")
    fan = User.objects.create_user(phone="+79991110003", password="x")
    ad = Ad.objects.create(
        owner=owner,
        kind=AdKind.PART,
        title="Bolt",
        price=500,
        is_published=True,
    )
    FavoriteAd.objects.create(user=fan, ad=ad)
    FavoriteAd.objects.create(user=owner, ad=ad)

    url = reverse("classifieds:ad_detail", kwargs={"pk": ad.pk})
    response = client.get(url)
    assert response.status_code == 200
    assert response.context["ad_favorite_count"] == 2


@pytest.mark.django_db
def test_ad_detail_seller_public_ads_count(client):
    owner = User.objects.create_user(phone="+79991110004", password="x")
    ad1 = Ad.objects.create(
        owner=owner,
        kind=AdKind.CAR,
        title="One",
        price=1,
        car_deal_type=CarDealType.SALE,
        is_published=True,
    )
    Ad.objects.create(
        owner=owner,
        kind=AdKind.PART,
        title="Two",
        price=2,
        is_published=True,
    )
    Ad.objects.create(
        owner=owner,
        kind=AdKind.CAR,
        title="Draft",
        price=3,
        car_deal_type=CarDealType.SALE,
        is_published=False,
    )
    r = client.get(reverse("classifieds:ad_detail", kwargs={"pk": ad1.pk}))
    assert r.status_code == 200
    assert r.context["seller_public_ads_count"] == 2
