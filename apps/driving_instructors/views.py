# -*- coding: utf-8 -*-

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import DetailView, ListView

from apps.driving_instructors.forms import InstructorProfileForm
from apps.driving_instructors.models import DrivingInstructorProfile


class InstructorListView(ListView):
    model = DrivingInstructorProfile
    template_name = "driving_instructors/list.html"
    context_object_name = "instructors"
    paginate_by = 24

    def get_queryset(self):
        return DrivingInstructorProfile.objects.filter(is_published=True).order_by("name")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["seo_og_title"] = "Автоинструкторы — обучение вождению | МаБибип"
        ctx["seo_meta_description"] = (
            "Частные автоинструкторы: цены, опыт, механика и автомат. Связь по телефону — МаБибип."
        )
        return ctx


class InstructorDetailView(DetailView):
    model = DrivingInstructorProfile
    template_name = "driving_instructors/detail.html"
    context_object_name = "instructor"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return DrivingInstructorProfile.objects.filter(is_published=True)


def _instructor_owner_required(user) -> bool:
    return bool(
        user.is_authenticated and getattr(user, "business_role", "") == "instructor"
    )


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    if not _instructor_owner_required(request.user):
        raise Http404
    return redirect("instructor_owner:profile_edit")


@login_required
def profile_edit(request: HttpRequest) -> HttpResponse:
    if not _instructor_owner_required(request.user):
        raise Http404
    profile = getattr(request.user, "instructor_profile", None)
    if not profile:
        raise Http404
    if request.method == "POST":
        form = InstructorProfileForm(request.POST, instance=profile)
        if form.is_valid():
            inst = form.save(commit=False)
            if not (inst.contact_phone or "").strip():
                inst.contact_phone = request.user.phone
            from apps.users.profile_completion import instructor_profile_complete

            if instructor_profile_complete(inst):
                inst.is_published = True
            inst.save()
            messages.success(request, "Профиль сохранён.")
            return redirect("instructor_owner:profile_edit")
    else:
        form = InstructorProfileForm(instance=profile)
    return render(
        request,
        "instructor_owner/profile_edit.html",
        {"form": form, "instructor": profile},
    )
