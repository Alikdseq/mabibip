import pytest
from django.urls import reverse

from apps.classifieds.models import Ad, AdKind
from apps.users.models import User


@pytest.mark.django_db
def test_ad_detail_does_not_show_safe_buy_button(client):
    seller = User.objects.create_user(phone="+79990003101", password="x")
    buyer = User.objects.create_user(phone="+79990003102", password="x")
    ad = Ad.objects.create(
        owner=seller,
        kind=AdKind.PART,
        title="Test",
        price=1000,
        city_label="Москва",
        is_published=True,
    )
    client.force_login(buyer)
    r = client.get(reverse("classifieds:ad_detail", args=[ad.pk]))
    assert r.status_code == 200
    body = r.content.decode("utf-8")
    assert "Купить безопасно" not in body


@pytest.mark.django_db
def test_cabinet_subnav_does_not_show_deals_or_wallet(client):
    u = User.objects.create_user(phone="+79990003103", password="x")
    client.force_login(u)
    r = client.get(reverse("classifieds:my_ads"))
    assert r.status_code == 200
    body = r.content.decode("utf-8")
    assert ">Сделки<" not in body
    assert ">Кошелёк<" not in body

