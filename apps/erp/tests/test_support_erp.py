"""ERP: раздел поддержки (список, ответ, статусы)."""

import pytest
from django.urls import reverse

from apps.support.models import SupportMessage, SupportTicket, SupportTicketStatus
from apps.support.unread import support_unread_tickets_for_staff_qs
from apps.users.models import User


@pytest.mark.django_db
def test_support_list_redirects_non_superuser(client):
    u = User.objects.create_user(phone="+79990001101", password="x")
    client.force_login(u)
    r = client.get(reverse("erp:support"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_support_list_ok_for_superuser(client):
    admin = User.objects.create_user(phone="+79990001102", password="x", is_superuser=True)
    client.force_login(admin)
    r = client.get(reverse("erp:support"))
    assert r.status_code == 200


@pytest.mark.django_db
def test_support_staff_reply_sets_in_progress(client):
    admin = User.objects.create_user(phone="+79990001103", password="x", is_superuser=True)
    user = User.objects.create_user(phone="+79990001104", password="x")
    ticket = SupportTicket.objects.create(user=user, subject="Тест", status=SupportTicketStatus.OPEN)
    SupportMessage.objects.create(
        ticket=ticket,
        author=user,
        body="Вопрос пользователя в поддержку, текст достаточной длины.",
        is_staff_reply=False,
    )

    client.force_login(admin)
    r = client.post(
        reverse("erp:support_ticket_reply", args=[ticket.id]),
        {"body": "Ответ сотрудника поддержки для пользователя."},
    )
    assert r.status_code == 302

    ticket.refresh_from_db()
    assert ticket.status == SupportTicketStatus.IN_PROGRESS
    assert SupportMessage.objects.filter(
        ticket=ticket,
        is_staff_reply=True,
        is_system_auto=False,
        author=admin,
    ).exists()


@pytest.mark.django_db
def test_support_set_status_resolved(client):
    admin = User.objects.create_user(phone="+79990001105", password="x", is_superuser=True)
    user = User.objects.create_user(phone="+79990001106", password="x")
    ticket = SupportTicket.objects.create(
        user=user,
        subject="Тест",
        status=SupportTicketStatus.IN_PROGRESS,
    )

    client.force_login(admin)
    r = client.post(
        reverse("erp:support_ticket_set_status", args=[ticket.id]),
        {"status": SupportTicketStatus.RESOLVED},
    )
    assert r.status_code == 302
    ticket.refresh_from_db()
    assert ticket.status == SupportTicketStatus.RESOLVED


@pytest.mark.django_db
def test_support_staff_unread_until_ticket_opened(client):
    admin = User.objects.create_user(phone="+79990001107", password="x", is_superuser=True)
    user = User.objects.create_user(phone="+79990001108", password="x")
    ticket = SupportTicket.objects.create(user=user, subject="Новый", status=SupportTicketStatus.OPEN)
    SupportMessage.objects.create(
        ticket=ticket,
        author=user,
        body="Сообщение пользователя в поддержку, достаточно длинное.",
        is_staff_reply=False,
        is_system_auto=False,
    )
    assert ticket.pk in set(support_unread_tickets_for_staff_qs().values_list("pk", flat=True))
    client.force_login(admin)
    client.get(reverse("erp:support_ticket_detail", args=[ticket.id]))
    ticket.refresh_from_db()
    assert ticket.staff_last_read_at is not None
    assert ticket.pk not in set(support_unread_tickets_for_staff_qs().values_list("pk", flat=True))


@pytest.mark.django_db
def test_support_staff_reply_makes_user_unread(client):
    from django.test import Client as DjangoClient

    admin = User.objects.create_user(phone="+79990001109", password="x", is_superuser=True)
    user = User.objects.create_user(phone="+79990001110", password="x")
    ticket = SupportTicket.objects.create(user=user, subject="Тест", status=SupportTicketStatus.OPEN)
    SupportMessage.objects.create(
        ticket=ticket,
        author=user,
        body="Вопрос пользователя в поддержку, текст достаточной длины.",
        is_staff_reply=False,
        is_system_auto=False,
    )
    ticket.user_last_read_at = ticket.updated_at
    ticket.staff_last_read_at = ticket.updated_at
    ticket.save(update_fields=["user_last_read_at", "staff_last_read_at"])

    client = DjangoClient()
    client.force_login(admin)
    client.post(
        reverse("erp:support_ticket_reply", args=[ticket.id]),
        {"body": "Ответ поддержки для теста непрочитанного."},
    )

    from apps.support.unread import support_unread_count_for_user

    assert support_unread_count_for_user(user) == 1
    client.logout()
    client.force_login(user)
    client.get(reverse("cabinet:support_detail", kwargs={"pk": ticket.pk}))
    assert support_unread_count_for_user(user) == 0
