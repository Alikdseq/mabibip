"""ЛК: поддержка (список, создание тикета, переписка)."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.support.models import SupportMessage, SupportTicket
from apps.users.models import User


@pytest.fixture
def client_user(db):
    return User.objects.create_user(phone="+79997770101", password="x", email="supp@t.test")


@pytest.fixture
def other_user(db):
    return User.objects.create_user(phone="+79997770102", password="x", email="other@t.test")


@pytest.mark.django_db
def test_support_list_requires_login():
    c = Client()
    r = c.get(reverse("cabinet:support"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_support_list_and_create_ticket(client_user):
    c = Client()
    c.force_login(client_user)
    r = c.get(reverse("cabinet:support"))
    assert r.status_code == 200

    r = c.post(
        reverse("cabinet:support_create"),
        {"body": "Коротко"},
    )
    assert r.status_code == 302
    assert SupportTicket.objects.filter(user=client_user).count() == 0

    text = "Достаточно длинный текст обращения в поддержку для прохождения валидации."
    r = c.post(
        reverse("cabinet:support_create"),
        {"body": text, "subject": "Тема теста"},
    )
    assert r.status_code == 302
    ticket = SupportTicket.objects.get(user=client_user)
    assert ticket.subject == "Тема теста"
    msgs = list(SupportMessage.objects.filter(ticket=ticket).order_by("pk"))
    assert len(msgs) == 2
    assert msgs[0].body == text
    assert not msgs[0].is_system_auto
    assert msgs[1].is_system_auto
    assert str(ticket.pk) in (r.get("Location") or "")


@pytest.mark.django_db
def test_support_detail_shows_thread(client_user):
    c = Client()
    c.force_login(client_user)
    c.post(
        reverse("cabinet:support_create"),
        {"body": "Обращение пользователя с достаточной длиной текста."},
    )
    ticket = SupportTicket.objects.get(user=client_user)
    r = c.get(reverse("cabinet:support_detail", kwargs={"pk": ticket.pk}))
    assert r.status_code == 200
    assert "Сообщение сервиса" in r.content.decode()


@pytest.mark.django_db
def test_support_detail_other_user_404(client_user, other_user):
    ticket = SupportTicket.objects.create(user=other_user, subject="Чужой")
    SupportMessage.objects.create(
        ticket=ticket,
        author=other_user,
        body="Текст от другого пользователя в тикете поддержки.",
        is_staff_reply=False,
    )
    c = Client()
    c.force_login(client_user)
    r = c.get(reverse("cabinet:support_detail", kwargs={"pk": ticket.pk}))
    assert r.status_code == 404
