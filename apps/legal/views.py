"""Публичные страницы документов и принятие оферты СТО."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import FormView, ListView, TemplateView

from .forms import StoOfferAcceptForm
from .models import (
    DocumentKey,
    LegalDocumentVersion,
    UserConsent,
    get_current_version,
)
from .services import record_user_consents
from .utils import render_legal_markdown


class LegalArchiveView(ListView):
    """Архив: все опубликованные версии (прозрачность для пользователей и аудита)."""

    template_name = "legal/archive.html"
    context_object_name = "versions"
    queryset = LegalDocumentVersion.objects.all().order_by("key", "-effective_at", "-id")


class LegalDocumentCurrentView(TemplateView):
    """Актуальная версия документа по ключу (privacy, user_agreement, ...)."""

    template_name = "legal/document.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        key = self.kwargs["key"]
        if key not in DocumentKey.values:
            raise Http404("Неизвестный тип документа")
        version = get_current_version(key)
        if version is None:
            raise Http404("Документ ещё не опубликован")
        ctx["version"] = version
        ctx["html_content"] = render_legal_markdown(version.content_markdown)
        return ctx


class StoConsentView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    """Обязательное принятие лицензионной оферты СТО перед работой в кабинете."""

    template_name = "legal/sto_consent.html"
    form_class = StoOfferAcceptForm
    login_url = reverse_lazy("users:login")

    def test_func(self):
        u = self.request.user
        return u.is_authenticated and getattr(u, "is_sto_owner", False)

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        if not getattr(request.user, "is_sto_owner", False):
            raise PermissionDenied
        current = get_current_version(DocumentKey.STO_OFFER)
        if current is None:
            messages.warning(
                request,
                "Оферта для СТО ещё не опубликована администратором. Обратитесь в поддержку.",
            )
            return redirect("home")
        if UserConsent.objects.filter(user=request.user, document_version=current).exists():
            return redirect("sto_owner:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["sto_version"] = get_current_version(DocumentKey.STO_OFFER)
        return ctx

    def form_valid(self, form):
        current = get_current_version(DocumentKey.STO_OFFER)
        if current is None:
            messages.error(self.request, "Документ недоступен.")
            return redirect("home")
        record_user_consents(self.request.user, [current], self.request)
        messages.success(self.request, "Вы приняли условия оферты для СТО.")
        return redirect("sto_owner:dashboard")
