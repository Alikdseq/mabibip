"""Каталог: фильтры, HTMX-фрагмент, гео-метаданные."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.stations.catalog_city import filter_queryset_by_visitor_city
from apps.stations.constants import EXECUTOR_KIND_PRIVATE, SUBSCRIPTION_PLAN_FREE
from apps.core.visitor_city import SESSION_KEY as VISITOR_CITY_SESSION_KEY
from apps.stations.models import CarBrand, District, ServiceStation
from apps.users.models import User


def test_car_brand_logo_png_stem():
    assert CarBrand(slug="volkswagen", sprite_key="vw").logo_png_stem == "volkswagen"
    assert CarBrand(slug="mercedes-benz", sprite_key="mercedes").logo_png_stem == "mercedes"
    assert CarBrand(slug="audi", sprite_key="audi").logo_png_stem == "audi"
    assert CarBrand(slug="custom", sprite_key="").logo_png_stem == "custom"


def test_brand_logo_size_filter():
    from apps.stations.templatetags.station_catalog import brand_logo_size

    assert brand_logo_size("volkswagen") == 58
    assert brand_logo_size("vw") == 58
    assert brand_logo_size("renault") == 96
    assert brand_logo_size("bmw") == 96
    assert brand_logo_size("hyundai") == 100
    assert brand_logo_size("audi") == 96
    assert brand_logo_size("geely") == 100
    assert brand_logo_size("ford") == 96
    assert brand_logo_size("peugeot") == 104
    assert brand_logo_size("mercedes") == 80
    assert brand_logo_size("toyota") == 104


def test_brand_logo_relpath_case_insensitive(tmp_path, monkeypatch):
    """Файлы Peugeot.png / renault.PNG на диске → корректный путь при запросе в нижнем регистре."""
    d = tmp_path / "logo"
    d.mkdir(parents=True)
    (d / "Peugeot.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00")
    (d / "renault.PNG").write_bytes(b"\x89PNG\r\n\x1a\n\x00")
    monkeypatch.setattr(
        "apps.stations.templatetags.station_catalog._brand_logo_dir",
        lambda: d,
    )
    from apps.stations.templatetags.station_catalog import brand_logo_relpath

    assert brand_logo_relpath("peugeot") == "logo/Peugeot.png"
    assert brand_logo_relpath("renault") == "logo/renault.PNG"


def test_brand_logo_relpath_typo_filenames(tmp_path, monkeypatch):
    """Реальные имена pageut.png и reno.png подхватываются для peugeot и renault."""
    d = tmp_path / "logo"
    d.mkdir(parents=True)
    (d / "pageut.png").write_bytes(b"x")
    (d / "reno.png").write_bytes(b"x")
    monkeypatch.setattr(
        "apps.stations.templatetags.station_catalog._brand_logo_dir",
        lambda: d,
    )
    from apps.stations.templatetags.station_catalog import brand_logo_relpath

    assert brand_logo_relpath("peugeot") == "logo/pageut.png"
    assert brand_logo_relpath("renault") == "logo/reno.png"


def test_brand_logo_webp_relpath_when_webp_exists(tmp_path, monkeypatch):
    d = tmp_path / "logo"
    d.mkdir(parents=True)
    (d / "toyota.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00")
    (d / "toyota.webp").write_bytes(b"RIFF")
    monkeypatch.setattr(
        "apps.stations.templatetags.station_catalog._brand_logo_dir",
        lambda: d,
    )
    from apps.stations.templatetags.station_catalog import brand_logo_webp_relpath

    assert brand_logo_webp_relpath("toyota") == "logo/toyota.webp"


@pytest.fixture
def owner(db):
    return User.objects.create_user(phone="+79990003333", password="x", is_sto_owner=True)


@pytest.mark.django_db
def test_catalog_verified_filter(owner):
    d, _ = District.objects.get_or_create(name="Центр", slug="tsentr-test", defaults={"city_label": "Тестград"})
    v = ServiceStation.objects.create(
        owner=owner,
        name="Проверенный",
        slug="cat-ver",
        address="ул. 1",
        district=d,
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
        is_verified=True,
    )
    n = ServiceStation.objects.create(
        owner=owner,
        name="Обычный",
        slug="cat-norm",
        address="ул. 2",
        district=d,
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
        is_verified=False,
    )
    c = Client()
    s = c.session
    s[VISITOR_CITY_SESSION_KEY] = "Тестград"
    s.save()
    r = c.get(reverse("stations:list"), {"verified": "1"})
    assert r.status_code == 200
    slugs = [s.slug for s in r.context["stations"]]
    assert v.slug in slugs
    assert n.slug not in slugs


@pytest.mark.django_db
def test_catalog_executor_private_filter(owner):
    d, _ = District.objects.get_or_create(name="Центр", slug="tsentr-test2", defaults={"city_label": "Тестград"})
    st = ServiceStation.objects.create(
        owner=owner,
        name="Мастер Иван",
        slug="cat-priv",
        address="ул. 3",
        district=d,
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
        executor_kind=EXECUTOR_KIND_PRIVATE,
    )
    ServiceStation.objects.create(
        owner=owner,
        name="СТО Большое",
        slug="cat-sto",
        address="ул. 4",
        district=d,
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
    )
    c = Client()
    s = c.session
    s[VISITOR_CITY_SESSION_KEY] = "Тестград"
    s.save()
    r = c.get(reverse("stations:list"), {"exec": EXECUTOR_KIND_PRIVATE})
    assert r.status_code == 200
    slugs = [s.slug for s in r.context["stations"]]
    assert st.slug in slugs
    assert len(slugs) == 1


@pytest.mark.django_db
def test_catalog_htmx_returns_partial(owner):
    ServiceStation.objects.create(
        owner=owner,
        name="HTMX СТО",
        slug="cat-htmx",
        address="ул. 5",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
    )
    c = Client()
    r = c.get(reverse("stations:list"), HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    body = r.content.decode()
    assert "catalog-results-inner" in body
    assert "navbar-brand" not in body


@pytest.mark.django_db
def test_catalog_brand_filter_m2m(owner):
    d, _ = District.objects.get_or_create(name="Центр", slug="tsentr-test3", defaults={"city_label": "Тестград"})
    bmw, _ = CarBrand.objects.get_or_create(name="BMW", slug="bmw", defaults={"sprite_key": "bmw"})
    audi, _ = CarBrand.objects.get_or_create(name="Audi", slug="audi", defaults={"sprite_key": "audi"})
    st1 = ServiceStation.objects.create(
        owner=owner,
        name="СТО BMW",
        slug="sto-bmw",
        address="ул. 10",
        district=d,
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
    )
    st2 = ServiceStation.objects.create(
        owner=owner,
        name="СТО Audi",
        slug="sto-audi",
        address="ул. 11",
        district=d,
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
    )
    st1.car_brands.add(bmw)
    st2.car_brands.add(audi)

    c = Client()
    s = c.session
    s[VISITOR_CITY_SESSION_KEY] = "Тестград"
    s.save()
    r = c.get(reverse("stations:list"), {"brand": "bmw"})
    assert r.status_code == 200
    slugs = [s.slug for s in r.context["stations"]]
    assert st1.slug in slugs
    assert st2.slug not in slugs
    assert r.context["catalog_brand_obj"]["name"] == "BMW"


@pytest.mark.django_db
def test_catalog_filters_by_city_get_param(owner):
    d_a = District.objects.create(name="А", slug="dist-a", city_label="ГородА")
    d_b = District.objects.create(name="Б", slug="dist-b", city_label="ГородБ")
    st_a = ServiceStation.objects.create(
        owner=owner,
        name="СТО А",
        slug="city-a",
        address="ул. 1",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
        district=d_a,
    )
    st_b = ServiceStation.objects.create(
        owner=owner,
        name="СТО Б",
        slug="city-b",
        address="ул. 2",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
        district=d_b,
    )
    c = Client()
    r = c.get(reverse("stations:list"), {"city": "ГородБ"})
    assert r.status_code == 200
    slugs = [s.slug for s in r.context["stations"]]
    assert st_b.slug in slugs
    assert st_a.slug not in slugs


@pytest.mark.django_db
def test_catalog_city_includes_station_without_district_if_address_matches_city(owner):
    """Без района карточка всё же попадает в город, если название города есть в адресе."""
    District.objects.create(name="Центр", slug="dist-testgrad", city_label="Тестград")
    st = ServiceStation.objects.create(
        owner=owner,
        name="По адресу",
        slug="addr-only",
        address="Тестград, проспект Мира 1",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
        district=None,
    )
    c = Client()
    r = c.get(reverse("stations:list"), {"city": "Тестград"})
    assert r.status_code == 200
    slugs = [s.slug for s in r.context["stations"]]
    assert st.slug in slugs


@pytest.mark.django_db
def test_filter_queryset_by_visitor_city_or_logic():
    from apps.stations.models import ServiceStation
    from django.contrib.auth import get_user_model

    User = get_user_model()
    u = User.objects.create_user(phone="+79997776655", password="x")
    d = District.objects.create(name="Район", slug="r-io", city_label="ГородГ")
    ServiceStation.objects.create(
        owner=u,
        name="С районом",
        slug="with-d",
        address="ул. 1",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
        district=d,
    )
    st_addr = ServiceStation.objects.create(
        owner=u,
        name="Без района",
        slug="no-d",
        address="ГородГ, ул. 2",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
        district=None,
    )
    st_other = ServiceStation.objects.create(
        owner=u,
        name="Другой",
        slug="other",
        address="ДругойГород, ул. 3",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
        district=None,
    )
    qs = filter_queryset_by_visitor_city(ServiceStation.objects.all(), "ГородГ")
    ids = set(qs.values_list("slug", flat=True))
    assert "with-d" in ids
    assert "no-d" in ids
    assert "other" not in ids
