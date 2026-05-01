"""Создание тикета поддержки и авто-сообщения."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.support.models import SupportMessage, SupportTicket
from apps.support.services import create_ticket_with_initial_message
from apps.users.models import User


@pytest.mark.django_db
def test_create_ticket_atomic_three_rows():
    """H2: тикет + первое сообщение пользователя + авто-сообщение поддержки."""
    user = User.objects.create_user(phone="+79993001001", password="x")
    ticket = create_ticket_with_initial_message(user, "Нужна помощь с записью в сервис, спасибо.")
    assert SupportTicket.objects.count() == 1
    assert SupportMessage.objects.filter(ticket=ticket).count() == 2
    msgs = list(SupportMessage.objects.filter(ticket=ticket).order_by("pk"))
    assert msgs[0].author_id == user.pk
    assert not msgs[0].is_system_auto
    assert msgs[1].author_id is None
    assert msgs[1].is_system_auto
    assert "МаБибип" in msgs[1].body
    ticket.refresh_from_db()
    assert ticket.user_last_read_at is not None


@pytest.mark.django_db
def test_create_ticket_too_short():
    user = User.objects.create_user(phone="+79993001002", password="x")
    with pytest.raises(ValueError, match="коротк"):
        create_ticket_with_initial_message(user, "short")


@pytest.mark.django_db
def test_create_ticket_rate_limit(settings):
    settings.SUPPORT_MAX_NEW_TICKETS_PER_HOUR = 2
    user = User.objects.create_user(phone="+79993001003", password="x")
    create_ticket_with_initial_message(user, "Первое обращение в поддержку тест.")
    create_ticket_with_initial_message(user, "Второе обращение в поддержку тест.")
    with pytest.raises(ValueError, match="Слишком много"):
        create_ticket_with_initial_message(user, "Третье обращение в поддержку тест.")


@pytest.mark.django_db
def test_rate_limit_resets_after_hour(settings):
    settings.SUPPORT_MAX_NEW_TICKETS_PER_HOUR = 1
    user = User.objects.create_user(phone="+79993001004", password="x")
    create_ticket_with_initial_message(user, "Одно обращение за час достаточно длинное.")
    old = timezone.now() - timedelta(hours=2)
    SupportTicket.objects.filter(user=user).update(created_at=old, updated_at=old)
    create_ticket_with_initial_message(user, "Новое обращение после сброса окна по времени.")
