import pytest
from django.urls import reverse

from apps.classifieds.models import AutoShopProfile
from apps.users.models import User


pytestmark = pytest.mark.django_db


def test_shop_detail_has_jsonld(client):
    owner = User.objects.create_user(phone="+79990009901", password="x")
    shop = AutoShopProfile.objects.create(owner=owner, name="Магазин 1", kind="shop", slug="shop-1", city_label="Владикавказ")
    r = client.get(reverse("classifieds:shop_detail", kwargs={"slug": shop.slug}))
    assert r.status_code == 200
    body = r.content.decode()
    assert "application/ld+json" in body
    assert "schema.org" in body

