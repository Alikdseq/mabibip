"""Фото профиля в ЛК."""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from apps.users.models import User


@pytest.mark.django_db
def test_profile_saves_avatar(client):
    user = User.objects.create_user(phone="+79994001101", password="secret12")
    client.force_login(user)
    url = reverse("cabinet:profile")
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color=(120, 40, 200)).save(buf, format="JPEG", quality=80)
    file = SimpleUploadedFile("tiny.jpg", buf.getvalue(), content_type="image/jpeg")
    response = client.post(
        url,
        {"first_name": "", "last_name": "", "email": "", "avatar": file},
        follow=True,
    )
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.avatar.name


@pytest.mark.django_db
def test_profile_rejects_oversized_avatar(settings, client):
    settings.USER_AVATAR_MAX_BYTES = 100
    user = User.objects.create_user(phone="+79994001102", password="secret12")
    client.force_login(user)
    url = reverse("cabinet:profile")
    big = SimpleUploadedFile("big.jpg", b"x" * 200, content_type="image/jpeg")
    response = client.post(url, {"first_name": "", "last_name": "", "email": "", "avatar": big})
    assert response.status_code == 200
    user.refresh_from_db()
    assert not user.avatar.name
