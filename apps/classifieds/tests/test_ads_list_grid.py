"""Список объявлений: двухколоночная сетка на мобильных при большом числе результатов."""

import pytest
from django.urls import reverse

from apps.classifieds.models import Ad, AdKind
from apps.users.models import User


@pytest.mark.django_db
def test_ads_mobile_two_column_when_enough_ads(client):
    owner = User.objects.create_user(phone="+79992005001", password="x")
    for i in range(51):
        Ad.objects.create(
            owner=owner,
            kind=AdKind.PART,
            title=f"Запчасть тест {i}",
            price=100 + i,
            is_published=True,
        )
    r = client.get(reverse("classifieds:ads_list"))
    assert r.status_code == 200
    assert r.context["filtered_total"] == 51
    assert r.context["ads_mobile_two_column"] is True
    body = r.content.decode()
    assert "pm-ads-dense-mobile" in body
    assert "row-cols-2" in body


@pytest.mark.django_db
def test_ads_mobile_two_column_at_fifty_ads(client):
    """H4: порог мобильной сетки 2 колонки при filtered_total >= 50."""
    owner = User.objects.create_user(phone="+79992005003", password="x")
    for i in range(50):
        Ad.objects.create(
            owner=owner,
            kind=AdKind.PART,
            title=f"Ровно50 {i}",
            price=10,
            is_published=True,
        )
    r = client.get(reverse("classifieds:ads_list"))
    assert r.status_code == 200
    assert r.context["filtered_total"] == 50
    assert r.context["ads_mobile_two_column"] is True


@pytest.mark.django_db
def test_ads_single_column_when_few_ads(client):
    owner = User.objects.create_user(phone="+79992005002", password="x")
    for i in range(3):
        Ad.objects.create(
            owner=owner,
            kind=AdKind.PART,
            title=f"Мало {i}",
            price=50,
            is_published=True,
        )
    r = client.get(reverse("classifieds:ads_list"))
    assert r.status_code == 200
    assert r.context["filtered_total"] == 3
    assert r.context["ads_mobile_two_column"] is False
    body = r.content.decode()
    assert "pm-ads-dense-mobile" not in body
