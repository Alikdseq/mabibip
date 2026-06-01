"""Доска «Проблемы водителей»."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.driver_problems.models import DriverProblemPost, ProblemStatus
from apps.users.models import User


@pytest.mark.django_db
def test_problems_board_lists_open_posts():
    author = User.objects.create_user(phone="+79992230001", password="x", is_active=True)
    DriverProblemPost.objects.create(
        author=author,
        title="Стук",
        description="Стук в подвеске",
        status=ProblemStatus.OPEN,
    )
    r = Client().get(reverse("driver_problems:board"))
    assert r.status_code == 200
    assert "Стук" in r.content.decode()


@pytest.mark.django_db
def test_master_can_claim_open_problem():
    author = User.objects.create_user(phone="+79992230002", password="x", is_active=True)
    master = User.objects.create_user(
        phone="+79992230003",
        password="x",
        is_active=True,
        is_sto_owner=True,
        sto_moderation_status=User.StoModerationStatus.APPROVED,
        business_role=User.BusinessRole.MASTER,
    )
    post = DriverProblemPost.objects.create(
        author=author,
        title="Двигатель",
        description="Горит Check Engine",
        status=ProblemStatus.OPEN,
    )
    c = Client()
    c.force_login(master)
    r = c.post(reverse("driver_problems:claim", kwargs={"pk": post.pk}))
    assert r.status_code == 302
    assert r.url == reverse("driver_problems:board")
    post.refresh_from_db()
    assert post.status == ProblemStatus.CLAIMED
    assert post.claimed_by_id == master.pk
