from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from django.db import IntegrityError, transaction
from django.template.response import TemplateResponse
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.users.onboarding_access import ensure_completed_profile_api
from apps.users.email_verification_access import contacts_email_verification_needed

from .call_ui import format_phone_human, seller_phone_e164
from .models import Ad, AdReport, PhoneRevealLog


class RevealPhoneAPIView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ads_reveal_phone"

    def get(self, request, pk: int):
        blocked = ensure_completed_profile_api(request)
        if blocked is not None:
            return blocked

        if contacts_email_verification_needed(request.user):
            return Response(
                {
                    "ok": False,
                    "error": "Чтобы смотреть телефоны, добавьте email в профиле и подтвердите его по ссылке из письма.",
                },
                status=403,
            )

        ad = get_object_or_404(Ad.objects.select_related("owner", "shop"), pk=int(pk), is_published=True)

        # Автор объявления не «раскрывает» свой номер — он и так видит его в превью/профиле.
        if int(ad.owner_id) == int(request.user.pk):
            phone = seller_phone_e164(ad)
            return Response(
                {
                    "ok": True,
                    "ad_id": int(ad.pk),
                    "phone_e164": phone or "",
                    "phone_display": format_phone_human(phone),
                    "revealed_for_sec": 300,
                    "owner_preview": True,
                }
            )

        u = request.user
        now = timezone.now()

        blocked_until = getattr(u, "contact_view_blocked_until", None)
        if blocked_until and blocked_until > now:
            secs = int((blocked_until - now).total_seconds())
            return Response(
                {
                    "ok": False,
                    "error": "Вы превысили лимит раскрытия контактов. Попробуйте позже.",
                    "blocked_for_sec": max(0, secs),
                },
                status=429,
            )

        # Доп. ограничение антифрода: подозрительным аккаунтам запрещаем раскрытие.
        if bool(getattr(u, "is_suspicious", False)):
            return Response(
                {"ok": False, "error": "Действие временно ограничено системой безопасности."},
                status=403,
            )

        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        recent_hour = PhoneRevealLog.objects.filter(user=u, revealed_at__gte=hour_ago).count()
        recent_day = PhoneRevealLog.objects.filter(user=u, revealed_at__gte=day_ago).count()

        if recent_hour >= 5 or recent_day >= 20:
            # Автоблокировка на 24 часа
            u.contact_view_blocked_until = now + timedelta(hours=24)
            u.save(update_fields=["contact_view_blocked_until"])
            return Response(
                {
                    "ok": False,
                    "error": "Вы превысили лимит раскрытия контактов. Попробуйте позже.",
                    "blocked_for_sec": 24 * 3600,
                },
                status=429,
            )

        phone = seller_phone_e164(ad)
        if not phone:
            # Телефона нет — лог раскрытия не пишем.
            return Response(
                {
                    "ok": False,
                    "error": "Продавец не указал телефон.",
                },
                status=404,
            )

        PhoneRevealLog.objects.create(user=u, ad=ad)
        return Response(
            {
                "ok": True,
                "ad_id": int(ad.pk),
                "phone_e164": phone,
                "phone_display": format_phone_human(phone),
                "revealed_for_sec": 300,
                "server_time": now.isoformat(),
            }
        )


class AdReportAPIView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ads_report"

    def post(self, request, pk: int):
        ad = get_object_or_404(Ad.objects.select_related("owner"), pk=int(pk), is_published=True)
        if int(ad.owner_id) == int(request.user.pk):
            return Response({"ok": False, "error": "Нельзя пожаловаться на своё объявление."}, status=400)

        reason = (request.data.get("reason") or "").strip()
        try:
            with transaction.atomic():
                AdReport.objects.create(ad=ad, reported_by=request.user, reason=reason[:500])
        except IntegrityError:
            # Уже жаловался
            pass

        # Порог: 3 уникальные жалобы от разных пользователей за 7 дней → скрыть объявление.
        since = timezone.now() - timedelta(days=7)
        uniq_count = (
            AdReport.objects.filter(ad=ad, created_at__gte=since).values("reported_by_id").distinct().count()
        )
        if uniq_count >= 3 and ad.is_published:
            ad.is_published = False
            ad.save(update_fields=["is_published"])

        # HTMX: вернуть обновлённый слот кнопки.
        has_reported = AdReport.objects.filter(ad=ad, reported_by=request.user).exists()
        if (request.headers.get("HX-Request") or "").lower() == "true":
            return TemplateResponse(
                request,
                "classifieds/partials/ad_report_button.html",
                {"ad": ad, "has_reported": has_reported},
                status=200,
            )

        return Response({"ok": True, "has_reported": has_reported, "ad_hidden": not ad.is_published})

