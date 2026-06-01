# -*- coding: utf-8 -*-

from django.utils import timezone

from apps.driver_problems.models import DriverProblemPost, ProblemStatus
from apps.driver_problems.realtime import broadcast_problem_event
from apps.stations.display import _user_public_display_name


def open_problems_count() -> int:
    return DriverProblemPost.objects.filter(status=ProblemStatus.OPEN).count()


def problem_payload(post: DriverProblemPost) -> dict:
    return {
        "id": post.pk,
        "title": post.title,
        "description": post.description[:300],
        "car_brand": post.car_brand,
        "city_label": post.city_label,
        "author_label": _user_public_display_name(post.author),
        "created_at": post.created_at.isoformat(),
    }


def create_problem(*, author, title: str, description: str, car_brand: str = "", city_label: str = "") -> DriverProblemPost:
    if DriverProblemPost.objects.filter(author=author, status=ProblemStatus.OPEN).exists():
        raise ValueError("У вас уже есть открытая заявка. Дождитесь отклика мастера.")
    post = DriverProblemPost.objects.create(
        author=author,
        title=(title or "").strip()[:120],
        description=(description or "").strip()[:2000],
        car_brand=(car_brand or "").strip()[:80],
        city_label=(city_label or "").strip()[:120],
    )
    broadcast_problem_event("problem_new", problem_payload(post))
    return post


def claim_problem(*, post: DriverProblemPost, master) -> None:
    from apps.users.models import User

    if post.status != ProblemStatus.OPEN:
        raise ValueError("Заявка уже забрана.")
    if not getattr(master, "is_sto_owner", False):
        raise ValueError("Забирать заявки могут только мастера и СТО.")
    if getattr(master, "business_role", "") not in (
        User.BusinessRole.MASTER,
        User.BusinessRole.AUTOSERVICE,
    ):
        raise ValueError("Забирать заявки могут только мастера и СТО.")
    post.status = ProblemStatus.CLAIMED
    post.claimed_by = master
    post.claimed_at = timezone.now()
    post.save(update_fields=["status", "claimed_by", "claimed_at"])
    broadcast_problem_event("problem_claimed", {"id": post.pk})
