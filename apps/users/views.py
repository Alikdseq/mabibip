import secrets
import smtplib

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_http_methods

from django_ratelimit.decorators import ratelimit

from apps.legal.models import REGISTRATION_REQUIRED_KEYS, get_current_version
from apps.legal.services import record_user_consents

from apps.stations.constants import EXECUTOR_KIND_CHOICES
from apps.stations.models import District, ServiceStation
from apps.core.city_expansion import record_business_city

from .forms import (
    AccountDeleteForm,
    PhoneAuthenticationForm,
    RegisterForm,
    RoleRegisterForm,
    StoRegistrationForm,
)
from .sto_moderation_mail import mail_admins_sto_registration_pending
from .email_verification import send_registration_verification_email
from .recaptcha import RecaptchaError, verify_recaptcha
from .services_anonymize import anonymize_user

User = get_user_model()


def _executor_kind_display(raw: str) -> str:
    return dict(EXECUTOR_KIND_CHOICES).get(raw, raw)


def _recaptcha_ip(request: HttpRequest) -> str | None:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class CaptchaLoginView(LoginView):
    """Вход с серверной проверкой reCAPTCHA (v2/v3) (фаза F1.1.4)."""

    template_name = "users/login.html"
    authentication_form = PhoneAuthenticationForm

    def get_success_url(self) -> str:
        redirect_url = self.get_redirect_url()
        if redirect_url:
            return redirect_url
        user = self.request.user
        if getattr(user, "is_sto_owner", False):
            mod = getattr(user, "sto_moderation_status", User.StoModerationStatus.APPROVED)
            if mod == User.StoModerationStatus.PENDING:
                return reverse("sto_owner:pending_moderation")
            if mod == User.StoModerationStatus.REJECTED:
                return reverse("sto_owner:moderation_rejected")
            return reverse("sto_owner:dashboard")
        return reverse("home")

    def form_valid(self, form):
        token = self.request.POST.get("recaptcha_token", "")
        try:
            verify_recaptcha(
                token=token,
                action="login",
                remote_ip=_recaptcha_ip(self.request),
            )
        except RecaptchaError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)
        return super().form_valid(form)


@ratelimit(key="ip", rate="3/h", method="POST", block=False)
@require_http_methods(["GET", "POST"])
def register_start(request: HttpRequest) -> HttpResponse:
    """Регистрация: 4 роли (водитель/мастер/автосервис/автомагазин) одним экраном."""
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)

    if request.method == "POST":
        if getattr(settings, "RATELIMIT_ENABLE", True) and getattr(request, "limited", False):
            return render(request, "users/ratelimited.html", status=429)
        form = RoleRegisterForm(request.POST)
        if form.is_valid():
            token = form.cleaned_data.get("recaptcha_token") or ""
            try:
                verify_recaptcha(
                    token=token,
                    action="register",
                    remote_ip=_recaptcha_ip(request),
                )
            except RecaptchaError as e:
                messages.error(request, str(e))
            else:
                role = form.cleaned_data.get("role") or User.BusinessRole.DRIVER
                email = form.cleaned_data.get("email")
                ev_token = secrets.token_urlsafe(32) if email else ""
                with transaction.atomic():
                    user = User.objects.create_user(
                        phone=form.cleaned_data["phone"],
                        password=form.cleaned_data["password1"],
                        email=email,
                        is_active=True,
                        is_phone_verified=True,
                        business_role=role,
                        business_role_chosen=True,
                        contact_phone=form.cleaned_data["phone"],
                        email_verified=not bool(email),
                        email_verification_token=ev_token if email else "",
                    )
                    if role != User.BusinessRole.DRIVER:
                        user.is_sto_owner = True
                        user.sto_moderation_status = User.StoModerationStatus.PENDING
                        user.save(update_fields=["is_sto_owner", "sto_moderation_status"])
                        from apps.stations.constants import EXECUTOR_KIND_PRIVATE, EXECUTOR_KIND_STO

                        business_name = (form.cleaned_data.get("business_name") or "").strip()
                        city = (form.cleaned_data.get("city_label") or "").strip()
                        record_business_city(city)
                        district = District.objects.filter(city_label=city).order_by("pk").first()
                        if role in (User.BusinessRole.MASTER, User.BusinessRole.AUTOSERVICE):
                            executor_kind = EXECUTOR_KIND_PRIVATE if role == User.BusinessRole.MASTER else EXECUTOR_KIND_STO
                            ServiceStation.objects.create(
                                owner=user,
                                name=business_name,
                                address=f"{city}, адрес уточняется после модерации",
                                executor_kind=executor_kind,
                                is_active=False,
                                district=district,
                            )
                        else:
                            from apps.classifieds.models import AutoShopProfile

                            AutoShopProfile.objects.create(
                                owner=user,
                                name=business_name,
                                city_label=city,
                                contact_phone=user.phone,
                                kind=form.cleaned_data.get("autoshop_kind") or AutoShopProfile.Kind.SHOP,
                            )
                    versions = [get_current_version(k) for k in REGISTRATION_REQUIRED_KEYS]
                    record_user_consents(user, versions, request)
                if email:
                    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
                    try:
                        send_registration_verification_email(
                            request=request,
                            user=user,
                            uidb64=uidb64,
                            token=ev_token,
                        )
                    except Exception:
                        messages.warning(
                            request,
                            "Регистрация завершена, но письмо с подтверждением email не удалось отправить. "
                            "Проверьте настройки почты или обратитесь в поддержку.",
                        )
                    else:
                        messages.info(
                            request,
                            "На указанный email отправлена ссылка для подтверждения адреса.",
                        )
                login(
                    request,
                    user,
                    backend="django.contrib.auth.backends.ModelBackend",
                )
                if role == User.BusinessRole.DRIVER:
                    messages.success(request, "Регистрация завершена. Добро пожаловать!")
                    return redirect(reverse("home"))
                if role == User.BusinessRole.AUTOSHOP:
                    messages.success(request, "Регистрация завершена. Добро пожаловать в кабинет автомагазина!")
                    return redirect("shop_owner:dashboard")
                mail_admins_sto_registration_pending(
                    user=user,
                    station_name=(form.cleaned_data.get("business_name") or "").strip(),
                    city_label=(form.cleaned_data.get("city_label") or "").strip(),
                    executor_kind_display=_executor_kind_display(
                        EXECUTOR_KIND_PRIVATE if role == User.BusinessRole.MASTER else EXECUTOR_KIND_STO
                    )
                    if role != User.BusinessRole.AUTOSHOP
                    else "Автомагазин/разборка",
                )
                messages.success(
                    request,
                    "Заявка отправлена. После проверки модератором вы получите доступ к кабинету бизнеса.",
                )
                return redirect("sto_owner:pending_moderation")
    else:
        form = RoleRegisterForm(initial={"role": User.BusinessRole.DRIVER})

    return render(request, "users/register_start.html", {"form": form})


@ratelimit(key="ip", rate="3/h", method="POST", block=False)
@require_http_methods(["GET", "POST"])
def sto_register(request: HttpRequest) -> HttpResponse:
    """Регистрация исполнителя (СТО / частный мастер); аккаунт до модерации не имеет доступа к ЛК СТО."""
    if request.user.is_authenticated:
        u = request.user
        if getattr(u, "is_sto_owner", False):
            mod = getattr(u, "sto_moderation_status", User.StoModerationStatus.APPROVED)
            if mod == User.StoModerationStatus.PENDING:
                return redirect("sto_owner:pending_moderation")
            if mod == User.StoModerationStatus.REJECTED:
                return redirect("sto_owner:moderation_rejected")
            return redirect("sto_owner:dashboard")
        if request.method == "POST":
            messages.info(
                request,
                "Вы вошли как клиент. Чтобы отправить заявку для бизнеса, сначала выйдите из аккаунта.",
            )
            return redirect("users:sto_register")
        return render(
            request,
            "users/sto_register.html",
            {"form": None, "sto_register_need_logout": True},
        )

    if request.method == "POST":
        if getattr(settings, "RATELIMIT_ENABLE", True) and getattr(request, "limited", False):
            return render(request, "users/ratelimited.html", status=429)
        form = StoRegistrationForm(request.POST)
        if form.is_valid():
            token = form.cleaned_data.get("recaptcha_token") or ""
            try:
                verify_recaptcha(
                    token=token,
                    action="sto_register",
                    remote_ip=_recaptcha_ip(request),
                )
            except RecaptchaError as e:
                messages.error(request, str(e))
            else:
                cd = form.cleaned_data
                city = cd["city_label"].strip()
                record_business_city(city)
                executor_kind = cd["executor_kind"]
                station_title = cd["station_name"].strip()
                district = District.objects.filter(city_label=city).order_by("pk").first()
                ev_token = secrets.token_urlsafe(32)
                with transaction.atomic():
                    user = User.objects.create_user(
                        cd["phone"],
                        password=cd["password1"],
                        email=cd["email"],
                        is_active=True,
                        is_phone_verified=True,
                        business_role_chosen=True,
                        contact_phone=cd["phone"],
                        is_sto_owner=True,
                        sto_moderation_status=User.StoModerationStatus.PENDING,
                        email_verified=False,
                        email_verification_token=ev_token,
                    )
                    ServiceStation.objects.create(
                        owner=user,
                        name=station_title,
                        address=f"{city}, адрес уточняется после модерации",
                        executor_kind=executor_kind,
                        is_active=False,
                        district=district,
                    )
                    versions = [get_current_version(k) for k in REGISTRATION_REQUIRED_KEYS]
                    record_user_consents(user, versions, request)
                uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
                try:
                    send_registration_verification_email(
                        request=request,
                        user=user,
                        uidb64=uidb64,
                        token=ev_token,
                    )
                except Exception:
                    messages.warning(
                        request,
                        "Заявка принята, но письмо с подтверждением email не удалось отправить.",
                    )
                else:
                    messages.info(
                        request,
                        "На указанный email отправлена ссылка для подтверждения адреса.",
                    )
                mail_admins_sto_registration_pending(
                    user=user,
                    station_name=station_title,
                    city_label=city,
                    executor_kind_display=_executor_kind_display(executor_kind),
                )
                login(
                    request,
                    user,
                    backend="django.contrib.auth.backends.ModelBackend",
                )
                messages.success(
                    request,
                    "Заявка отправлена. После проверки модератором вы получите доступ к кабинету СТО.",
                )
                return redirect("sto_owner:pending_moderation")
    else:
        form = StoRegistrationForm()

    return render(request, "users/sto_register.html", {"form": form})


@login_required
@require_http_methods(["GET"])
def email_verification_notice(request: HttpRequest) -> HttpResponse:
    """Страница с напоминанием подтвердить email и кнопкой повторной отправки."""
    u = request.user
    if not u.email:
        messages.warning(
            request,
            "Укажите существующую почту в профиле — она нужна для подтверждения личности и доступа к телефонам.",
        )
        return redirect("cabinet:profile")
    if u.email_verified:
        messages.success(request, "Email уже подтверждён.")
        return redirect("home")
    return render(request, "users/email_verification_notice.html", {"user_obj": u})


@login_required
@require_http_methods(["POST"])
def resend_verification_email(request: HttpRequest) -> HttpResponse:
    """Повторная отправка письма с ссылкой (только для своего аккаунта)."""
    u = request.user
    if not u.email:
        messages.warning(
            request,
            "Укажите существующую почту в профиле — без неё невозможно отправить письмо для подтверждения.",
        )
        return redirect("cabinet:profile")
    if u.email_verified:
        return redirect("users:email_verification_notice")
    token = secrets.token_urlsafe(32)
    u.email_verification_token = token
    u.save(update_fields=["email_verification_token"])
    uidb64 = urlsafe_base64_encode(force_bytes(u.pk))
    try:
        send_registration_verification_email(
            request=request,
            user=u,
            uidb64=uidb64,
            token=token,
        )
    except (smtplib.SMTPRecipientsRefused, smtplib.SMTPDataError, smtplib.SMTPSenderRefused, smtplib.SMTPHeloError):
        messages.error(
            request,
            "Не удалось отправить письмо на этот адрес. Укажите существующую почту для подтверждения.",
        )
        return redirect("cabinet:profile")
    except Exception:
        messages.error(request, "Не удалось отправить письмо. Укажите существующую почту для подтверждения.")
        return redirect("cabinet:profile")
    else:
        messages.success(request, "Письмо со ссылкой отправлено на ваш email.")
    return redirect("users:email_verification_notice")


@require_http_methods(["GET"])
def verify_email(request: HttpRequest, uidb64: str, token: str) -> HttpResponse:
    """Подтверждение email по ссылке из письма (регистрация МаБибип)."""
    try:
        raw_uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=raw_uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    expected = (user.email_verification_token or "") if user is not None else ""
    if (
        user is not None
        and user.email
        and expected
        and len(token) == len(expected)
        and secrets.compare_digest(expected, token)
    ):
        user.email_verified = True
        user.email_verification_token = ""
        user.save(update_fields=["email_verified", "email_verification_token"])
        messages.success(request, "Email подтверждён. Спасибо!")
        return redirect("users:login")

    messages.error(
        request,
        "Ссылка подтверждения недействительна или устарела. "
        "Если вы уже подтверждали адрес, войдите в аккаунт как обычно.",
    )
    return redirect("users:login")


@require_http_methods(["GET", "HEAD"])
def register_confirm(request: HttpRequest) -> HttpResponse:
    """Старый URL второго шага (SMS): перенаправляем на единую форму регистрации."""
    return redirect("users:register")


@require_http_methods(["GET"])
def activate(request: HttpRequest, uidb64: str, token: str) -> HttpResponse:
    """Активация по ссылке из email (legacy). Новые пользователи активны сразу после регистрации."""
    try:
        raw_uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=raw_uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])
        messages.success(
            request,
            "Аккаунт активирован. Войдите, используя телефон и пароль.",
        )
        return redirect("users:login")

    messages.error(
        request,
        (
            "Ссылка активации недействительна или устарела. "
            "Зарегистрируйтесь снова или обратитесь в поддержку."
        ),
    )
    return redirect("users:login")


@require_http_methods(["GET", "POST"])
def account_delete(request: HttpRequest) -> HttpResponse:
    """Право на забвение: анонимизация учётной записи (фаза F1.1.7)."""
    if not request.user.is_authenticated:
        return redirect(settings.LOGIN_URL)

    if request.method == "POST":
        form = AccountDeleteForm(request.POST)
        if form.is_valid():
            anonymize_user(request.user)
            from django.contrib.auth import logout

            logout(request)
            messages.success(
                request,
                "Аккаунт обезличен. Вы вышли из системы.",
            )
            return redirect("home")
    else:
        form = AccountDeleteForm()

    return render(request, "users/account_delete.html", {"form": form})


@require_http_methods(["GET", "HEAD"])
def vk_oauth_callback_alias(request: HttpRequest) -> HttpResponse:
    """
    Редирект на callback django-allauth для VK.

    В кабинете VK ID часто указывают путь вида /accounts/vk/login/callback/,
    тогда как allauth монтируется на /oauth/... — этот алиас совмещает оба варианта.
    """
    from django.http import HttpResponseRedirect

    target = "/oauth/vk/login/callback/"
    if request.GET:
        target += "?" + request.GET.urlencode()
    return HttpResponseRedirect(target)
