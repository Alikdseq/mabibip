# -*- coding: utf-8 -*-

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.driver_problems.forms import DriverProblemForm
from apps.driver_problems.models import DriverProblemPost, ProblemStatus
from apps.driver_problems.services import claim_problem, create_problem, open_problems_count
from apps.stations.display import _user_public_display_name


def _enabled():
    return bool(getattr(settings, "DRIVER_PROBLEMS_ENABLED", True))


@require_GET
def problems_board(request: HttpRequest) -> HttpResponse:
    if not _enabled():
        raise Http404
    posts = list(
        DriverProblemPost.objects.filter(status=ProblemStatus.OPEN)
        .select_related("author")
        .order_by("-created_at")[:80]
    )
    can_claim = (
        request.user.is_authenticated
        and getattr(request.user, "is_sto_owner", False)
        and getattr(request.user, "sto_moderation_status", "") == "approved"
    )
    ctx = {
        "problem_posts": posts,
        "problem_open_count": open_problems_count(),
        "problem_form": DriverProblemForm(),
        "can_claim_problems": can_claim,
        "seo_og_title": "Проблемы водителей — заявки для мастеров | МаБибип",
        "seo_meta_description": "Водители описывают поломки и неисправности — мастера и СТО забирают заявки в работу. МаБибип.",
    }
    return render(request, "driver_problems/board.html", ctx)


@login_required
@require_POST
def problem_create(request: HttpRequest) -> HttpResponse:
    if not _enabled():
        raise Http404
    form = DriverProblemForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Проверьте форму.")
        return redirect("driver_problems:board")
    try:
        create_problem(author=request.user, **form.cleaned_data)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("driver_problems:board")
    messages.success(request, "Заявка опубликована.")
    return redirect("driver_problems:board")


@login_required
@require_POST
def problem_claim(request: HttpRequest, pk: int) -> HttpResponse:
    if not _enabled():
        raise Http404
    post = get_object_or_404(
        DriverProblemPost.objects.select_related("author"),
        pk=pk,
        status=ProblemStatus.OPEN,
    )
    try:
        claim_problem(post=post, master=request.user)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("driver_problems:board")
    phone = (getattr(post.author, "contact_phone", None) or post.author.phone or "").strip()
    messages.success(
        request,
        f"Заявка забрана. Свяжитесь с клиентом: {_user_public_display_name(post.author)}.",
    )
    if phone:
        messages.info(request, f"Телефон клиента: {phone}")
    return redirect("driver_problems:board")
