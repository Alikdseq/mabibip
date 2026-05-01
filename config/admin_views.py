from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from apps.audit.models import AuditLog
from apps.billing.models import PaymentIntent, PaymentIntentStatus, Subscription
from apps.bookings.constants import BookingStatus
from apps.bookings.models import Booking
from apps.reviews.models import ComplaintStatus, ModerationStatus, Review, ReviewComplaint
from apps.stations.constants import (
    EXECUTOR_KIND_PRIVATE,
    EXECUTOR_KIND_STO,
    SUBSCRIPTION_PLAN_BASIC,
)
from apps.stations.models import ServiceStation
from apps.users.models import User
from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.core.cache import cache
from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

DASHBOARD_CACHE_KEY = "promasterov.admin_dashboard.v1"
DASHBOARD_CACHE_TTL = 60


def _superuser(u):
    return bool(u.is_authenticated and u.is_superuser)


def _daterange_days(end: date, n: int) -> list[date]:
    return [end - timedelta(days=i) for i in range(n - 1, -1, -1)]


def _series_for_days(day_list: list, counts: dict) -> list[int]:
    return [counts.get(d, 0) for d in day_list]


def _build_dashboard_context() -> dict[str, Any]:
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    month_start = today - timedelta(days=30)
    month_ago = today - timedelta(days=30)

    # --- KPI: users ---
    users_qs = User.objects.all()
    total_users = users_qs.count()
    clients_qs = users_qs.filter(is_sto_owner=False)
    owners_qs = users_qs.filter(is_sto_owner=True)
    total_clients = clients_qs.count()
    total_owners = owners_qs.count()
    new_users_today = users_qs.filter(date_joined__date=today).count()
    new_users_week = users_qs.filter(date_joined__date__gte=week_ago).count()
    new_clients_week = clients_qs.filter(date_joined__date__gte=week_ago).count()

    sto_active = ServiceStation.objects.filter(executor_kind=EXECUTOR_KIND_STO, is_active=True)
    masters_active = ServiceStation.objects.filter(
        executor_kind=EXECUTOR_KIND_PRIVATE, is_active=True
    )
    total_sto = sto_active.count()
    total_masters = masters_active.count()
    stations_total = ServiceStation.objects.count()
    stations_inactive = ServiceStation.objects.filter(is_active=False).count()

    paid_basic = Q(
        subscription_plan=SUBSCRIPTION_PLAN_BASIC,
        subscription_paid_until__gte=today,
        is_active=True,
    )
    active_subscriptions = ServiceStation.objects.filter(paid_basic).count()
    paying_sto = sto_active.filter(paid_basic).count()
    paying_masters = masters_active.filter(paid_basic).count()

    # MRR: сумма последнего успешного платежа по каждой активной Basic-подписке (оценка)
    active_basic_stations = ServiceStation.objects.filter(paid_basic)
    sub_ids = list(
        Subscription.objects.filter(station__in=active_basic_stations).values_list("pk", flat=True)
    )
    mrr = Decimal("0.00")
    if sub_ids:
        intents = (
            PaymentIntent.objects.filter(
                subscription_id__in=sub_ids,
                status=PaymentIntentStatus.SUCCEEDED,
            )
            .values("subscription_id", "amount", "created_at")
            .order_by("subscription_id", "-created_at")
        )
        seen_sub: set[int] = set()
        for row in intents:
            sid = row["subscription_id"]
            if sid in seen_sub:
                continue
            seen_sub.add(sid)
            mrr += row["amount"]

    # --- KPI: bookings ---
    bookings_qs = Booking.objects.all()
    bookings_total = bookings_qs.count()
    bookings_by_status = {
        st: bookings_qs.filter(status=st).count() for st, _label in BookingStatus.choices
    }

    bookings_today = bookings_qs.filter(created_at__date=today)
    bookings_today_total = bookings_today.count()
    bookings_today_done = bookings_today.filter(status=BookingStatus.COMPLETED).count()
    bookings_today_canceled = bookings_today.filter(status=BookingStatus.CANCELED).count()
    bookings_week_total = bookings_qs.filter(created_at__date__gte=week_ago).count()

    pending_bookings = Booking.objects.filter(status=BookingStatus.PENDING).count()

    # --- Conversion: registration -> first booking (ever) ---
    users_with_booking = (
        User.objects.filter(bookings__isnull=False).distinct().count()
    )
    reg_to_booking_pct = round(100.0 * users_with_booking / total_users, 1) if total_users else 0.0

    reviews_today_qs = Review.objects.filter(created_at__date=today)
    reviews_today_count = reviews_today_qs.count()
    reviews_today_avg = reviews_today_qs.aggregate(v=Avg("rating"))["v"]

    complaints_pending = ReviewComplaint.objects.filter(status=ComplaintStatus.PENDING).count()

    # --- 30-day charts: registrations ---
    day_list = _daterange_days(today, 30)

    clients_by_day = dict(
        clients_qs.filter(date_joined__date__gte=month_start)
        .annotate(day=TruncDate("date_joined"))
        .values("day")
        .annotate(c=Count("id"))
        .values_list("day", "c")
    )
    owners_by_day = dict(
        User.objects.filter(is_sto_owner=True, date_joined__date__gte=month_start)
        .annotate(day=TruncDate("date_joined"))
        .values("day")
        .annotate(c=Count("id"))
        .values_list("day", "c")
    )
    stations_by_day = dict(
        ServiceStation.objects.filter(created_at__date__gte=month_start)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(c=Count("id"))
        .values_list("day", "c")
    )

    # Bookings created per day
    bookings_created_by_day = dict(
        Booking.objects.filter(created_at__date__gte=month_start)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(c=Count("id"))
        .values_list("day", "c")
    )

    # Bookings by status per day (created_at)
    bookings_status_by_day: dict[str, list[int]] = {}
    for st, _label in BookingStatus.choices:
        counts = dict(
            Booking.objects.filter(created_at__date__gte=month_start, status=st)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(c=Count("id"))
            .values_list("day", "c")
        )
        bookings_status_by_day[st] = _series_for_days(day_list, counts)

    # Completed: first day status became completed (history)
    Hist = Booking.history.model
    first_complete_by_booking: dict[int, date] = {}
    hist_qs = (
        Hist.objects.filter(
            status=BookingStatus.COMPLETED,
            history_date__date__gte=month_start,
        )
        .values("id", "history_date")
        .order_by("id", "history_date")
        .iterator(chunk_size=2000)
    )
    for row in hist_qs:
        bid = row["id"]
        if bid in first_complete_by_booking:
            continue
        first_complete_by_booking[bid] = row["history_date"].date()
    completed_by_day = Counter(first_complete_by_booking.values())

    # Review conversion (за 30 дней: впервые перешли в completed — с отзывом или без)
    completed_total_30d = len(first_complete_by_booking)
    completed_ids = list(first_complete_by_booking.keys())
    with_review_30d = (
        Booking.objects.filter(
            pk__in=completed_ids,
            review__moderation_status__in=[ModerationStatus.OK, ModerationStatus.UNDER_REVIEW],
        ).count()
        if completed_ids
        else 0
    )
    review_conversion_pct = (
        round(100.0 * with_review_30d / completed_total_30d, 1) if completed_total_30d else 0.0
    )

    # Top-5 stations by bookings (30d)
    top_stations = list(
        annotate_station_ratings_for_admin(
            ServiceStation.objects.filter(bookings__created_at__date__gte=month_start)
            .annotate(booking_cnt=Count("bookings", distinct=True))
            .order_by("-booking_cnt")[:5]
        )
    )

    # Map: new stations in 30d with coordinates
    map_stations = list(
        ServiceStation.objects.filter(
            created_at__date__gte=month_start, location__isnull=False
        ).only("id", "name", "slug", "location", "created_at")[:200]
    )
    map_points = []
    for st in map_stations:
        if st.location:
            map_points.append(
                {
                    "lat": st.location.y,
                    "lon": st.location.x,
                    "name": st.name,
                    "slug": st.slug,
                }
            )

    # Audit tail
    audit_recent = list(AuditLog.objects.select_related("actor").order_by("-created_at")[:25])

    admin_root = reverse("admin:index")
    today_start = timezone.make_aware(datetime.combine(today, time.min))
    tomorrow_start = timezone.make_aware(datetime.combine(today + timedelta(days=1), time.min))
    week_start = today - timedelta(days=7)

    admin_links = {
        "users_clients": f"{reverse('admin:users_user_changelist')}?is_sto_owner__exact=0",
        "users_clients_week": (
            f"{reverse('admin:users_user_changelist')}"
            f"?is_sto_owner__exact=0&date_joined__gte={week_start.isoformat()}"
        ),
        "stations_sto": (
            f"{reverse('admin:stations_servicestation_changelist')}"
            f"?executor_kind__exact={EXECUTOR_KIND_STO}&is_active__exact=1"
        ),
        "stations_private": (
            f"{reverse('admin:stations_servicestation_changelist')}"
            f"?executor_kind__exact={EXECUTOR_KIND_PRIVATE}&is_active__exact=1"
        ),
        "stations_paying_sto": (
            f"{reverse('admin:stations_servicestation_changelist')}"
            f"?executor_kind__exact={EXECUTOR_KIND_STO}&is_active__exact=1"
            f"&subscription_plan__exact={SUBSCRIPTION_PLAN_BASIC}"
            f"&subscription_paid_until__gte={today.isoformat()}"
        ),
        "stations_paying_private": (
            f"{reverse('admin:stations_servicestation_changelist')}"
            f"?executor_kind__exact={EXECUTOR_KIND_PRIVATE}&is_active__exact=1"
            f"&subscription_plan__exact={SUBSCRIPTION_PLAN_BASIC}"
            f"&subscription_paid_until__gte={today.isoformat()}"
        ),
        "stations_basic_active": (
            f"{reverse('admin:stations_servicestation_changelist')}"
            f"?subscription_plan__exact={SUBSCRIPTION_PLAN_BASIC}"
            f"&subscription_paid_until__gte={today.isoformat()}&is_active__exact=1"
        ),
        "stations_unpaid_basic": (
            f"{reverse('admin:stations_servicestation_changelist')}"
            f"?subscription_plan__exact={SUBSCRIPTION_PLAN_BASIC}"
            f"&subscription_paid_until__isnull=1"
        ),
        "bookings_today": (
            f"{reverse('admin:bookings_booking_changelist')}?created_at__gte={today_start.isoformat()}"
        ),
        "bookings_pending": f"{reverse('admin:bookings_booking_changelist')}?status__exact=pending",
        "reviews_today": (
            f"{reverse('admin:reviews_review_changelist')}"
            f"?created_at__gte={today_start.isoformat()}&created_at__lt={tomorrow_start.isoformat()}"
        ),
        "complaints_pending": (
            f"{reverse('admin:reviews_reviewcomplaint_changelist')}?status__exact=pending"
        ),
        "users_sto_owners": f"{reverse('admin:users_user_changelist')}?is_sto_owner__exact=1",
    }

    return {
        "today": today,
        "total_users": total_users,
        "total_clients": total_clients,
        "total_owners": total_owners,
        "new_users_today": new_users_today,
        "new_users_week": new_users_week,
        "new_clients_week": new_clients_week,
        "total_sto": total_sto,
        "total_masters": total_masters,
        "stations_total": stations_total,
        "stations_inactive": stations_inactive,
        "paying_sto": paying_sto,
        "paying_masters": paying_masters,
        "active_subscriptions": active_subscriptions,
        "mrr": mrr,
        "bookings_total": bookings_total,
        "bookings_by_status": bookings_by_status,
        "booking_status_choices": list(BookingStatus.choices),
        "bookings_week_total": bookings_week_total,
        "reg_to_booking_pct": reg_to_booking_pct,
        "bookings_today_total": bookings_today_total,
        "bookings_today_done": bookings_today_done,
        "bookings_today_canceled": bookings_today_canceled,
        "pending_bookings": pending_bookings,
        "reviews_today_count": reviews_today_count,
        "reviews_today_avg": reviews_today_avg,
        "complaints_pending": complaints_pending,
        "review_conversion_pct": review_conversion_pct,
        "with_review_30d": with_review_30d,
        "completed_total_30d": completed_total_30d,
        "top_stations": top_stations,
        "map_points_json": json.dumps(map_points, ensure_ascii=False),
        "yandex_maps_api_key": getattr(settings, "YANDEX_MAPS_API_KEY", "") or "",
        "chart_day_labels_json": json.dumps([d.isoformat() for d in day_list]),
        "reg_clients_json": json.dumps(_series_for_days(day_list, clients_by_day)),
        "reg_owners_json": json.dumps(_series_for_days(day_list, owners_by_day)),
        "reg_stations_json": json.dumps(_series_for_days(day_list, stations_by_day)),
        "book_created_json": json.dumps(_series_for_days(day_list, bookings_created_by_day)),
        "book_completed_json": json.dumps(_series_for_days(day_list, dict(completed_by_day))),
        "book_status_by_day_json": json.dumps(bookings_status_by_day),
        "review_pie_json": json.dumps(
            [
                with_review_30d,
                max(0, completed_total_30d - with_review_30d),
            ]
        ),
        "audit_recent": audit_recent,
        "admin_root": admin_root,
        "admin_links": admin_links,
        "cache_ttl": DASHBOARD_CACHE_TTL,
    }


def annotate_station_ratings_for_admin(qs):
    """Средний рейтинг для строк таблицы (как в каталоге)."""
    rev_ok = Q(
        bookings__status=BookingStatus.COMPLETED,
        bookings__review__moderation_status__in=[
            ModerationStatus.OK,
            ModerationStatus.UNDER_REVIEW,
        ],
    )
    return qs.annotate(
        station_avg_rating=Avg("bookings__review__rating", filter=rev_ok),
    )


def admin_dashboard(request):
    if request.GET.get("export") == "csv":
        return _dashboard_csv_export(request)

    ctx: dict[str, Any]
    if request.GET.get("nocache") == "1":
        ctx = _build_dashboard_context()
    else:
        ctx = cache.get(DASHBOARD_CACHE_KEY)
        if ctx is None:
            ctx = _build_dashboard_context()
            cache.set(DASHBOARD_CACHE_KEY, ctx, DASHBOARD_CACHE_TTL)

    ctx = {**ctx, "clear_cache_url": reverse("admin_dashboard_clear_cache")}
    return render(request, "analytics/dashboard.html", ctx)


def admin_dashboard_clear_cache(request):
    cache.delete(DASHBOARD_CACHE_KEY)
    return redirect(reverse("admin_dashboard"))


def _dashboard_csv_export(request):
    """Краткий CSV по основным сущностям для суперпользователя."""
    today = timezone.localdate()
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="promasterov_analytics_summary.csv"'
    w = csv.writer(response)
    w.writerow(["metric", "value"])
    w.writerow(["date", today.isoformat()])
    w.writerow(["users_clients", User.objects.filter(is_sto_owner=False).count()])
    w.writerow(["users_owners", User.objects.filter(is_sto_owner=True).count()])
    w.writerow(
        [
            "stations_sto_active",
            ServiceStation.objects.filter(executor_kind=EXECUTOR_KIND_STO, is_active=True).count(),
        ]
    )
    w.writerow(
        [
            "stations_private_active",
            ServiceStation.objects.filter(
                executor_kind=EXECUTOR_KIND_PRIVATE, is_active=True
            ).count(),
        ]
    )
    w.writerow(
        [
            "stations_basic_active",
            ServiceStation.objects.filter(
                subscription_plan=SUBSCRIPTION_PLAN_BASIC,
                subscription_paid_until__gte=today,
                is_active=True,
            ).count(),
        ]
    )
    w.writerow(["bookings_total", Booking.objects.count()])
    for st, label in BookingStatus.choices:
        w.writerow([f"bookings_{st}", Booking.objects.filter(status=st).count()])
    w.writerow(["reviews_total", Review.objects.count()])
    w.writerow(
        [
            "complaints_pending",
            ReviewComplaint.objects.filter(status=ComplaintStatus.PENDING).count(),
        ]
    )
    return response
