"""Главная страница и API подсказок поиска."""

from datetime import time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.bookings.constants import BookingStatus
from apps.bookings.models import Booking, TimeSlot
from apps.stations.homepage import build_homepage_context
from apps.stations.models import Promotion, ServiceCategory, ServiceStation, WorkBay
from apps.users.models import User


@pytest.mark.django_db
def test_homepage_renders(client):
    r = client.get(reverse("home"))
    assert r.status_code == 200
    body = r.content.decode()
    assert "Какой раздел услуг нужен" in body
    assert "Блок марок авто" in body
    assert "Смотреть объявления" in body


@pytest.mark.django_db
def test_build_homepage_context_empty_db():
    ctx = build_homepage_context()
    assert ctx["home_station_count"] == 0
    assert ctx["home_free_slots"] == []
    assert ctx["home_promotions"] == []


@pytest.mark.django_db
def test_search_suggest_empty_query(client):
    r = client.get(reverse("api_search_suggest"), {"q": ""})
    assert r.status_code == 200
    assert r.json()["results"] == []


@pytest.mark.django_db
def test_search_suggest_finds_station_and_category(client):
    today = timezone.localdate()
    owner = User.objects.create_user(phone="+79991112233", password="x")
    st = ServiceStation.objects.create(
        owner=owner,
        name="УникальныйАвтоСервисТест",
        slug="unique-auto-test",
        address="ул. Тестовая, 1",
        is_active=True,
        subscription_plan="free",
    )
    cat = ServiceCategory.objects.create(name="УникальнаяКатегорияТест", slug="unique-cat-test")
    st.categories.add(cat)

    r_st = client.get(reverse("api_search_suggest"), {"q": "УникальныйАвто"})
    assert r_st.status_code == 200
    data = r_st.json()["results"]
    assert any(x["type"] == "sto" and "Уникальный" in x["label"] for x in data)

    r_cat = client.get(reverse("api_search_suggest"), {"q": "УникальнаяКат"})
    assert r_cat.status_code == 200
    data_c = r_cat.json()["results"]
    assert any(x["type"] == "category" for x in data_c)


@pytest.mark.django_db
def test_homepage_free_slots_excludes_booked(client):
    today = timezone.localdate()
    day = today + timedelta(days=1)
    owner = User.objects.create_user(phone="+79994445566", password="x")
    client_user = User.objects.create_user(phone="+79997778899", password="x")
    st = ServiceStation.objects.create(
        owner=owner,
        name="СТО Слоты",
        slug="sto-slots-home",
        address="ул. Слотовая, 1",
        is_active=True,
        subscription_plan="free",
    )
    bay = WorkBay.objects.create(station=st, name="Пост 1")
    slot_free = TimeSlot.objects.create(
        bay=bay,
        date=day,
        start_time=time(14, 0),
        end_time=time(15, 0),
        is_available=True,
    )
    slot_booked = TimeSlot.objects.create(
        bay=bay,
        date=day,
        start_time=time(16, 0),
        end_time=time(17, 0),
        is_available=True,
    )
    Booking.objects.create(
        client=client_user,
        station=st,
        slot=slot_booked,
        car_info="A111AA",
        contact_phone="+79997778899",
        description="тест",
        status=BookingStatus.CONFIRMED,
    )

    ctx = build_homepage_context()
    ids = {s.pk for s in ctx["home_free_slots"]}
    assert slot_free.pk in ids
    assert slot_booked.pk not in ids

    r = client.get(reverse("home"))
    assert r.status_code == 200
    body = r.content.decode()
    assert "Примут сейчас" in body


@pytest.mark.django_db
def test_homepage_shows_active_promotion(client):
    today = timezone.localdate()
    Promotion.objects.create(
        title="Скидка тест",
        summary="Описание",
        discount_percent=10,
        valid_until=today + timedelta(days=7),
        is_active=True,
        sort_order=0,
    )
    ctx = build_homepage_context()
    titles = {p.title for p in ctx["home_promotions"]}
    assert "Скидка тест" in titles
    r = client.get(reverse("home"))
    assert r.status_code == 200
