from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.users.email_verification_access import require_verified_email
from apps.users.onboarding_access import require_completed_profile

from .forms import AutoShopBranchForm, AutoShopProfileForm
from .models import Ad, AutoShopBranch
from .views import _ad_photos_prefetch


def _autoshop_required(user) -> bool:
    return bool(user.is_authenticated and getattr(user, "business_role", "") == "autoshop")


def _get_shop_or_404(request: HttpRequest):
    if not _autoshop_required(request.user):
        raise Http404
    shop = getattr(request.user, "autoshop_profile", None)
    if not shop:
        messages.info(request, "Профиль автомагазина не настроен.")
        raise Http404
    return shop


@login_required
@require_completed_profile
@require_verified_email
def dashboard(request: HttpRequest) -> HttpResponse:
    shop = _get_shop_or_404(request)
    return render(request, "autoshop_owner/dashboard.html", {"shop": shop})


@login_required
def profile_edit(request: HttpRequest) -> HttpResponse:
    if not _autoshop_required(request.user):
        raise Http404
    shop = _get_shop_or_404(request)
    if request.method == "POST":
        form = AutoShopProfileForm(request.POST, instance=shop)
        if form.is_valid():
            form.save()
            messages.success(request, "Профиль магазина сохранён.")
            return redirect("shop_owner:profile_edit")
    else:
        form = AutoShopProfileForm(instance=shop)
    return render(
        request,
        "autoshop_owner/profile_edit.html",
        {"shop": shop, "form": form},
    )


@login_required
@require_completed_profile
@require_verified_email
def products(request: HttpRequest) -> HttpResponse:
    shop = _get_shop_or_404(request)
    ads = Ad.objects.filter(shop=shop).prefetch_related(_ad_photos_prefetch()).order_by("-created_at", "-pk")
    return render(request, "autoshop_owner/products.html", {"ads": ads, "shop": shop})


@login_required
@require_completed_profile
@require_verified_email
def branches(request: HttpRequest) -> HttpResponse:
    shop = _get_shop_or_404(request)
    items = AutoShopBranch.objects.filter(shop=shop).order_by("name", "pk")
    return render(request, "autoshop_owner/branches.html", {"shop": shop, "branches": items})


@login_required
@require_completed_profile
@require_verified_email
def branch_add(request: HttpRequest) -> HttpResponse:
    shop = _get_shop_or_404(request)
    if request.method == "POST":
        form = AutoShopBranchForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.shop = shop
            obj.save()
            messages.success(request, "Филиал добавлен.")
            return redirect("shop_owner:branches")
    else:
        form = AutoShopBranchForm()
    return render(request, "autoshop_owner/branch_form.html", {"shop": shop, "form": form, "mode": "add"})


@login_required
@require_completed_profile
@require_verified_email
def branch_edit(request: HttpRequest, pk: int) -> HttpResponse:
    shop = _get_shop_or_404(request)
    obj = AutoShopBranch.objects.filter(shop=shop, pk=pk).first()
    if not obj:
        raise Http404
    if request.method == "POST":
        form = AutoShopBranchForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Филиал сохранён.")
            return redirect("shop_owner:branches")
    else:
        form = AutoShopBranchForm(instance=obj)
    return render(request, "autoshop_owner/branch_form.html", {"shop": shop, "form": form, "mode": "edit", "obj": obj})


@login_required
@require_completed_profile
@require_verified_email
def branch_delete(request: HttpRequest, pk: int) -> HttpResponse:
    shop = _get_shop_or_404(request)
    obj = AutoShopBranch.objects.filter(shop=shop, pk=pk).first()
    if not obj:
        raise Http404
    if request.method != "POST":
        raise Http404
    obj.delete()
    messages.success(request, "Филиал удалён.")
    return redirect("shop_owner:branches")

