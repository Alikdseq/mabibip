"""Фаза A SEO: robots, sitemap, canonical (docs/seo/plan.md)."""

import pytest
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.stations.models import ServiceCategory, ServiceStation
from apps.users.models import User

pytestmark = pytest.mark.django_db(databases=["default"])


@override_settings(SITE_BASE_URL="")
def test_robots_txt_disallows_private_and_points_sitemap(client):
    r = client.get(reverse("robots_txt"))
    assert r.status_code == 200
    body = r.content.decode()
    assert "Disallow: /secure-admin/" in body
    assert "Disallow: /api/" in body
    assert "Sitemap: http://testserver/sitemap.xml" in body


def test_sitemap_index_and_static_section(client, db):
    r = client.get(reverse("seo_sitemap"))
    assert r.status_code == 200
    xml = r.content.decode()
    assert "sitemapindex" in xml or "urlset" in xml
    if "sitemapindex" in xml:
        assert "section=static" in xml
        r2 = client.get(reverse("seo_sitemap"), {"section": "static"})
        assert r2.status_code == 200
        assert "http://testserver/" in r2.content.decode()
        assert "/sto/" in r2.content.decode()


def test_sitemap_includes_visible_station(client, db):
    today = timezone.localdate()
    owner = User.objects.create_user(phone="+79990001122", password="x")
    st = ServiceStation.objects.create(
        owner=owner,
        name="СТО SiteMap",
        slug="sto-sitemap-seo",
        address="ул. Картографическая, 1",
        is_active=True,
        subscription_plan="free",
    )
    cat = ServiceCategory.objects.create(name="КатегорияSM", slug="cat-sm-seo")
    st.categories.add(cat)

    r = client.get(reverse("seo_sitemap"), {"section": "stations"})
    assert r.status_code == 200
    assert "sto-sitemap-seo" in r.content.decode()


@override_settings(SITE_BASE_URL="")
def test_home_has_canonical(client, db):
    r = client.get(reverse("home"))
    assert r.status_code == 200
    assert 'rel="canonical"' in r.content.decode()
    assert 'href="http://testserver/"' in r.content.decode()


@override_settings(SITE_BASE_URL="")
def test_catalog_canonical_strips_utm_keeps_brand(client, db):
    owner = User.objects.create_user(phone="+79990003344", password="x")
    ServiceStation.objects.create(
        owner=owner,
        name="СТО Канон",
        slug="sto-canonical",
        address="ул. Каноническая, 1",
        is_active=True,
        subscription_plan="free",
    )
    r = client.get(
        reverse("stations:list"),
        {"brand": "toyota", "utm_source": "test", "entry": "service"},
    )
    assert r.status_code == 200
    body = r.content.decode()
    assert "utm_source" not in body.split('rel="canonical"')[1].split(">")[0]
    assert "brand=toyota" in body
    assert "entry" not in body.split('rel="canonical"')[1].split(">")[0]


def test_cabinet_has_no_canonical(client, db):
    u = User.objects.create_user(phone="+79990005566", password="x")
    client.force_login(u)
    r = client.get(reverse("cabinet:profile"))
    assert r.status_code == 200
    assert 'rel="canonical"' not in r.content.decode()
