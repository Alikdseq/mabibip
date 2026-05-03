from __future__ import annotations

import hashlib
import logging

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.utils import perform_login
from allauth.exceptions import ImmediateHttpResponse
from allauth.socialaccount.models import SocialLogin
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.shortcuts import redirect
from django.utils import timezone

logger = logging.getLogger(__name__)


class TachkiSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Проект использует кастомного пользователя с обязательным `phone`.
    Для OAuth-аккаунтов создаём уникальный placeholder в `User.phone`,
    чтобы не ломать существующую архитектуру входа по телефону.
    """

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)

        provider = (sociallogin.account.provider or "oauth").strip()
        uid = (sociallogin.account.uid or "").strip() or "unknown"
        # phone — обязательное и unique. Placeholder не должен пересекаться с E.164.
        # Делаем короткий стабильный идентификатор (без обрезания uid, чтобы избежать коллизий).
        digest = hashlib.sha256(f"{provider}:{uid}".encode("utf-8")).hexdigest()[:16]
        user.phone = f"oauth_{provider}_{digest}"[:32]

        # Если провайдер отдал email — считаем подтверждённым на стороне «МаБибип».
        # Важно: если email не отдан, allauth может поставить "" (пустую строку),
        # а в БД email unique (NULL допускается, а "" конфликтует).
        if not (getattr(user, "email", None) or "").strip():
            user.email = None
        if getattr(user, "email", None):
            user.email_verified = True

        # Новые OAuth-аккаунты считаем «новыми» по date_joined; доп. антифрод уже завязан на возраст.
        return user

    def save_user(self, request, sociallogin, form=None):
        """
        Делает social-login устойчивым к:
        - уникальности email (если email уже есть в системе)
        - потенциальным коллизиям placeholder-логина (phone) у OAuth-пользователя
        """
        User = get_user_model()

        email = (getattr(sociallogin.user, "email", "") or "").strip().lower()
        if not email:
            sociallogin.user.email = None
        if email:
            existing = User.objects.filter(email__iexact=email).first()
            if existing:
                # При совпадении email — привязываем соц.аккаунт к существующему пользователю.
                sociallogin.connect(request, existing)
                return existing

        # Страхуемся от коллизий `phone` (unique).
        base_phone = (getattr(sociallogin.user, "phone", "") or "").strip()
        if base_phone:
            if User.objects.filter(phone=base_phone).exists():
                # добавляем небольшой хэш-соль (в пределах 32 символов)
                digest = hashlib.sha256((base_phone + ":salt").encode("utf-8")).hexdigest()[:6]
                sociallogin.user.phone = f"{base_phone[:25]}{digest}"

        try:
            with transaction.atomic():
                return super().save_user(request, sociallogin, form=form)
        except IntegrityError:
            # Последний шанс: коллизия unique (чаще всего phone/email)
            digest = hashlib.sha256(f"fallback:{timezone.now().isoformat()}".encode("utf-8")).hexdigest()[:8]
            sociallogin.user.phone = f"oauth_{digest}"[:32]
            with transaction.atomic():
                return super().save_user(request, sociallogin, form=form)

    def pre_social_login(self, request, sociallogin: SocialLogin):
        """
        Если email от провайдера уже существует в БД — автоматически:
        - привязываем соц.аккаунт к существующему пользователю
        - выполняем логин в этот аккаунт

        Это убирает промежуточную страницу allauth `/socialaccount/signup/` и делает UX «моментально».
        """
        email = (getattr(sociallogin.user, "email", "") or "").strip().lower()
        if not email:
            return

        User = get_user_model()
        existing = User.objects.filter(email__iexact=email).first()
        if not existing:
            return

        # Если соц.аккаунт уже связан с каким-то пользователем — обычный путь.
        if getattr(sociallogin, "is_existing", False):
            return

        # Привязываем и логиним.
        try:
            sociallogin.connect(request, existing)
        except Exception as exc:
            logger.warning(
                "pre_social_login: connect failed provider=%s email=%s: %s",
                getattr(sociallogin.account, "provider", ""),
                email,
                exc,
                exc_info=True,
            )
            messages.error(
                request,
                "Не удалось привязать соцсеть к аккаунту с этим email. "
                "Попробуйте ещё раз или войдите по телефону и обратитесь в поддержку.",
            )
            return

        resp = perform_login(
            request,
            existing,
            email_verification="optional",
            redirect_url=self.get_login_redirect_url(request),
        )
        raise ImmediateHttpResponse(resp)

    def get_login_redirect_url(self, request):
        """
        После social-login сразу ведём на онбординг, если роль/контакт не заполнены.
        Это решает UX: «после Google входа пользователь должен выбрать роль и телефон».
        """
        try:
            from .onboarding_access import onboarding_needed

            if onboarding_needed(getattr(request, "user", None)):
                return "/cabinet/profile/"
        except Exception:
            pass
        return super().get_login_redirect_url(request)

    def is_auto_signup_allowed(self, request, sociallogin):
        """
        True — разрешаем автосоздание, если у провайдера уже есть валидные данные (email и т.д.).
        Если email нет, а SOCIALACCOUNT_EMAIL_REQUIRED=True, allauth сам отправит на /oauth/.../signup/.
        """
        return True

    def is_open_for_signup(self, request, sociallogin: SocialLogin) -> bool:
        """
        Разводим oauth login и signup.

        - process=login: разрешаем вход ТОЛЬКО в существующий аккаунт по email (иначе запрет).
        - process=signup: разрешаем создание нового аккаунта (для водителей).
        """
        process = (request.GET.get("process") or "").strip().lower()
        if process != "login":
            return True

        email = (getattr(sociallogin.user, "email", "") or "").strip().lower()
        acct = getattr(sociallogin, "account", None)
        provider = (getattr(acct, "provider", None) or "").strip().lower()
        if not email:
            if provider == "vk":
                messages.error(
                    request,
                    "Для входа через VK нужен email в профиле VK: разрешите доступ «email» при авторизации "
                    "или привяжите почту в настройках VK. Или войдите по телефону.",
                )
            else:
                messages.error(
                    request,
                    "Для входа через Google нужен email. Укажите email при регистрации по форме.",
                )
            return False

        User = get_user_model()
        exists = User.objects.filter(email__iexact=email).exists()
        if not exists:
            messages.error(
                request,
                "Аккаунт с таким email не найден. "
                "Для бизнеса регистрация только через форму; для входа через соцсеть сначала зарегистрируйтесь с тем же email.",
            )
            return False
        return True

