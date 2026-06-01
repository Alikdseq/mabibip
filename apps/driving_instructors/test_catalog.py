"""Публичный каталог автоинструкторов."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.driving_instructors.models import DrivingInstructorProfile
from apps.users.models import User


@pytest.mark.django_db
def test_instructor_list_shows_published_profile():
    owner = User.objects.create_user(
        phone="+79992240001",
        password="x",
        is_active=True,
        business_role=User.BusinessRole.INSTRUCTOR,
    )
    DrivingInstructorProfile.objects.create(
        owner=owner,
        name="Иван Инструктор",
        slug="ivan-instr",
        city_label="Москва",
        description="Опытный инструктор с большим стажем вождения.",
        contact_phone=owner.phone,
        price_per_hour=1500,
        is_published=True,
    )
    r = Client().get(reverse("driving_instructors:list"))
    assert r.status_code == 200
    assert "Иван Инструктор" in r.content.decode()
