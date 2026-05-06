import pytest
from datetime import timedelta
from django.urls import reverse
from django.utils import timezone

from apps.classifieds.forms import AdForm
from apps.classifieds.models import Ad, AdKind, AdReport, CarDealType, PhoneRevealLog
from apps.users.models import User


@pytest.mark.django_db
def test_reveal_phone_ok(client):
    owner = User.objects.create_user(phone="+79991120001", password="x")
    buyer = User.objects.create_user(
        phone="+79991120002",
        password="x",
        contact_phone="+79991120002",
        email="buyer@example.com",
        email_verified=True,
    )
    ad = Ad.objects.create(owner=owner, kind=AdKind.CAR, title="Car", price=1, car_deal_type=CarDealType.SALE, is_published=True)

    client.force_login(buyer)
    r = client.get(reverse("classifieds_api:ad_reveal_phone", kwargs={"pk": ad.pk}))
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["phone_e164"] == owner.phone
    assert PhoneRevealLog.objects.filter(user=buyer, ad=ad).count() == 1


@pytest.mark.django_db
def test_reveal_phone_limit_sets_block(client):
    owner = User.objects.create_user(phone="+79991120011", password="x")
    buyer = User.objects.create_user(
        phone="+79991120012",
        password="x",
        contact_phone="+79991120012",
        email="buyer2@example.com",
        email_verified=True,
    )
    ad = Ad.objects.create(owner=owner, kind=AdKind.PART, title="Part", price=1, is_published=True)

    # Pre-fill 5 reveals within the last hour.
    now = timezone.now()
    for _ in range(5):
        PhoneRevealLog.objects.create(user=buyer, ad=ad)

    client.force_login(buyer)
    r = client.get(reverse("classifieds_api:ad_reveal_phone", kwargs={"pk": ad.pk}))
    assert r.status_code == 429
    buyer.refresh_from_db()
    assert buyer.contact_view_blocked_until is not None
    assert buyer.contact_view_blocked_until > now


@pytest.mark.django_db
def test_reveal_phone_requires_verified_email(client):
    owner = User.objects.create_user(phone="+79991120021", password="x")
    buyer = User.objects.create_user(
        phone="+79991120022",
        password="x",
        contact_phone="+79991120022",
        email="buyer3@example.com",
        email_verified=False,
    )
    ad = Ad.objects.create(owner=owner, kind=AdKind.CAR, title="Car", price=1, car_deal_type=CarDealType.SALE, is_published=True)

    client.force_login(buyer)
    r = client.get(reverse("classifieds_api:ad_reveal_phone", kwargs={"pk": ad.pk}))
    assert r.status_code == 403
    data = r.json()
    assert data["ok"] is False


@pytest.mark.django_db
def test_reveal_phone_approved_business_bypasses_email(client):
    owner = User.objects.create_user(phone="+79991120031", password="x")
    buyer = User.objects.create_user(
        phone="+79991120032",
        password="x",
        contact_phone="+79991120032",
        email="biz@example.com",
        email_verified=False,
        business_role=User.BusinessRole.AUTOSHOP,
        is_sto_owner=True,
        sto_moderation_status=User.StoModerationStatus.APPROVED,
    )
    ad = Ad.objects.create(owner=owner, kind=AdKind.CAR, title="Car", price=1, car_deal_type=CarDealType.SALE, is_published=True)

    client.force_login(buyer)
    r = client.get(reverse("classifieds_api:ad_reveal_phone", kwargs={"pk": ad.pk}))
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["phone_e164"] == owner.phone


@pytest.mark.django_db
def test_report_unpublishes_after_three_unique_reports(client):
    owner = User.objects.create_user(phone="+79991120101", password="x")
    ad = Ad.objects.create(owner=owner, kind=AdKind.CAR, title="Car", price=1, car_deal_type=CarDealType.SALE, is_published=True)

    reporters = [
        User.objects.create_user(phone="+79991120102", password="x", contact_phone="+79991120102"),
        User.objects.create_user(phone="+79991120103", password="x", contact_phone="+79991120103"),
        User.objects.create_user(phone="+79991120104", password="x", contact_phone="+79991120104"),
    ]

    url = reverse("classifieds_api:ad_report", kwargs={"pk": ad.pk})
    for u in reporters:
        client.force_login(u)
        r = client.post(url, data={"reason": "spam"}, HTTP_HX_REQUEST="true")
        assert r.status_code == 200

    assert AdReport.objects.filter(ad=ad).count() == 3
    ad.refresh_from_db()
    assert ad.is_published is False


@pytest.mark.django_db
def test_text_moderation_sets_pending_and_unpublishes():
    u = User.objects.create_user(phone="+79991120201", password="x")
    # Для «старых» аккаунтов контакты в тексте не блокируют форму,
    # но объявление уходит на модерацию (pending) и снимается с публикации.
    u.date_joined = timezone.now() - timedelta(days=30)
    u.save(update_fields=["date_joined"])
    form = AdForm(
        data={
            "kind": AdKind.CAR,
            "title": "Продам, пишите в телеграм t.me/test",
            "price": 100,
            "city_label": "Владикавказ",
            "description": "Телефон 8 999 111-22-33",
            "is_published": True,
        },
        user=u,
    )
    assert form.is_valid()
    obj = form.save(commit=False)
    assert obj.is_published is False
    assert obj.moderation_status == Ad.ModerationStatus.PENDING

