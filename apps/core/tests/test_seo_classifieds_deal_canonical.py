import pytest
from django.test.utils import override_settings
from django.urls import reverse


pytestmark = pytest.mark.django_db


@override_settings(SITE_BASE_URL="")
def test_ads_list_canonical_includes_deal_for_car(client):
    url = reverse("classifieds:ads_list")
    r = client.get(url, {"tab": "car", "deal": "rent_car"})
    assert r.status_code == 200
    body = r.content.decode()
    assert 'rel="canonical"' in body
    assert "tab=car" in body
    assert "deal=rent_car" in body

