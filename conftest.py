from __future__ import annotations

import pytest
from django.utils import timezone


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """
    Проект использует read-replica роутинг даже в обычных view/middleware.
    pytest-django по умолчанию запрещает обращения к базам, не указанным в marker'е.

    Здесь автоматически разрешаем 'replica' для всех тестов, которые уже помечены
    django_db, но не объявили databases явно.
    """

    for item in items:
        m = item.get_closest_marker("django_db")
        if not m:
            continue

        databases = m.kwargs.get("databases")
        if databases is None:
            item.add_marker(pytest.mark.django_db(databases=["default", "replica"]))
            continue

        # Если тест сам указал databases, добавим replica, не ломая явный список.
        try:
            dbs = list(databases)
        except TypeError:
            dbs = [databases]
        if "replica" not in dbs:
            item.add_marker(pytest.mark.django_db(databases=[*dbs, "replica"]))

@pytest.fixture(autouse=True)
def _flush_fake_redis():
    """Фаза F3: чистый Redis-hold между тестами (fakeredis)."""
    from django.conf import settings

    client = getattr(settings, "TEST_FAKEREDIS_CLIENT", None)
    if client is not None:
        client.flushall()
    yield


@pytest.fixture(autouse=True)
def _seed_legal_documents_for_tests(db):
    """Версии по всем DocumentKey (как после seed_legal_documents в проде)."""
    from apps.legal.models import REGISTRATION_REQUIRED_KEYS, DocumentKey, LegalDocumentVersion

    now = timezone.now()
    effective = now - timezone.timedelta(days=1)
    for dk in DocumentKey:
        LegalDocumentVersion.objects.get_or_create(
            key=dk.value,
            version_label="seed-1.0",
            defaults={
                "title": dk.label,
                "effective_at": effective,
                "content_markdown": f"# {dk.label}\n\nТестовый фрагмент для CI.",
            },
        )
    from apps.legal.models import get_current_version

    for req in REGISTRATION_REQUIRED_KEYS:
        assert get_current_version(req) is not None, f"seed missing {req}"


@pytest.fixture
def owner(db, django_user_model):
    """Общий владелец СТО для тестов, которым он нужен."""
    return django_user_model.objects.create_user(
        phone="+79990000001",
        password="x",
        email="owner@test.local",
        is_sto_owner=True,
        is_phone_verified=True,
    )


@pytest.fixture
def client_user(db, django_user_model):
    """Общий клиент для тестов, которым он нужен."""
    return django_user_model.objects.create_user(
        phone="+79990000002",
        password="x",
        email="client@test.local",
        is_phone_verified=True,
    )


@pytest.fixture(autouse=True)
def _seed_test_city_labels(db):
    """
    Некоторые тесты используют произвольные city_label (например 'ТестГород').
    Форма регистрации СТО валидирует город по справочнику District, поэтому
    добавляем минимальные записи.
    """
    from apps.stations.models import District

    District.objects.get_or_create(
        slug="test-city-label-1",
        defaults={"name": "Тестовый район", "city_label": "ТестГород"},
    )
