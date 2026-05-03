"""
Завершение входа после VK ID SDK (One Tap): обмен кода на фронте, затем проверка access_token на бэкенде.
https://id.vk.com/about/business/go/docs/ru/vkid/latest/vk-id/connection/work-with-user-info/user-info
"""

from __future__ import annotations

import json
import logging
from typing import Any

import requests
from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST

from allauth.socialaccount.models import SocialAccount, SocialLogin
from django_ratelimit.decorators import ratelimit

from apps.users.allauth_adapters import TachkiSocialAccountAdapter

logger = logging.getLogger(__name__)

VK_USER_INFO_URL = "https://id.vk.ru/oauth2/user_info"


class VkidSessionError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


def vkid_oauth_configured() -> bool:
    cid = (getattr(settings, "VK_CLIENT_ID", None) or "").strip()
    secret = (getattr(settings, "VK_CLIENT_SECRET", None) or "").strip()
    return bool(cid and secret)


def fetch_vkid_user_info(access_token: str) -> dict[str, Any]:
    client_id = (getattr(settings, "VK_CLIENT_ID", None) or "").strip()
    if not client_id:
        raise VkidSessionError("disabled", "VK не настроен.", 503)

    try:
        r = requests.post(
            VK_USER_INFO_URL,
            data={"client_id": client_id, "access_token": access_token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
    except requests.RequestException as e:
        logger.warning("vkid user_info request failed: %s", e)
        raise VkidSessionError("vk_unreachable", "Сервис VK временно недоступен.", 502) from e

    try:
        payload = r.json()
    except ValueError as e:
        logger.warning("vkid user_info invalid json status=%s body=%s", r.status_code, r.text[:500])
        raise VkidSessionError("vk_bad_response", "Некорректный ответ VK.", 502) from e

    if r.status_code >= 400 or payload.get("error"):
        desc = (payload.get("error_description") or payload.get("error") or r.text or "")[:300]
        logger.info("vkid user_info error status=%s payload=%s", r.status_code, desc)
        raise VkidSessionError("vk_api", "Не удалось получить профиль VK. Повторите вход.", 401)

    user_blob = payload.get("user")
    if not isinstance(user_blob, dict):
        raise VkidSessionError("vk_bad_response", "В ответе VK нет данных пользователя.", 502)

    return user_blob


def _uid_str(user_blob: dict[str, Any]) -> str:
    raw = user_blob.get("user_id")
    if raw is None:
        raise VkidSessionError("vk_bad_response", "В ответе VK нет user_id.", 502)
    return str(raw).strip()


def _normalize_email(user_blob: dict[str, Any]) -> str:
    return (user_blob.get("email") or "").strip().lower()


def complete_vkid_session(request: HttpRequest, access_token: str, process: str) -> Any:
    """
    Возвращает User после валидации access_token у VK ID и применения тех же правил входа/регистрации, что и OAuth-редирект.
    """
    User = get_user_model()
    user_blob = fetch_vkid_user_info(access_token)
    uid = _uid_str(user_blob)
    email = _normalize_email(user_blob)

    existing_sa = SocialAccount.objects.filter(provider="vk", uid=uid).select_related("user").first()
    if existing_sa and existing_sa.user_id:
        return existing_sa.user

    adapter = TachkiSocialAccountAdapter()

    if process == "login":
        if not email:
            raise VkidSessionError(
                "email_required",
                "Для входа через VK нужен email: разрешите доступ «email» при авторизации "
                "или привяжите почту в VK. Или войдите по телефону.",
                403,
            )
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            raise VkidSessionError(
                "no_account",
                "Аккаунт с таким email не найден. Зарегистрируйтесь с тем же email или войдите по телефону.",
                403,
            )
        try:
            with transaction.atomic():
                SocialAccount.objects.create(user=user, provider="vk", uid=uid, extra_data=user_blob)
        except IntegrityError:
            sa3 = SocialAccount.objects.filter(provider="vk", uid=uid).select_related("user").first()
            if not sa3:
                raise
            if sa3.user_id != user.id:
                raise VkidSessionError(
                    "vk_already_linked",
                    "Этот аккаунт VK уже привязан к другому пользователю.",
                    409,
                ) from None
            return sa3.user
        return user

    # signup
    if not email:
        raise VkidSessionError(
            "email_required",
            "Для регистрации через VK нужен email: разрешите доступ «email» в окне VK.",
            403,
        )

    account = SocialAccount(provider="vk", uid=uid, extra_data=user_blob)
    u = User()
    u.email = email
    u.first_name = (user_blob.get("first_name") or "")[:150]
    u.last_name = (user_blob.get("last_name") or "")[:150]
    sociallogin = SocialLogin(user=u, account=account)
    adapter.populate_user(request, sociallogin, dict(user_blob))
    sociallogin.user.email = email or sociallogin.user.email
    if sociallogin.user.email:
        sociallogin.user.email_verified = True
    with transaction.atomic():
        saved = adapter.save_user(request, sociallogin, form=None)
    return saved


def _login_user_and_redirect_url(request: HttpRequest, user) -> str:
    adapter = TachkiSocialAccountAdapter()
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return adapter.get_login_redirect_url(request)


@ratelimit(key="ip", rate="30/h", method="POST", block=False)
@require_POST
def vkid_session_complete(request: HttpRequest) -> HttpResponse:
    if not vkid_oauth_configured():
        return JsonResponse({"ok": False, "error": "disabled", "message": "VK не настроен."}, status=404)

    if getattr(settings, "RATELIMIT_ENABLE", True) and getattr(request, "limited", False):
        return JsonResponse(
            {"ok": False, "error": "ratelimited", "message": "Слишком много попыток. Попробуйте позже."},
            status=429,
        )

    try:
        data = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "bad_json", "message": "Некорректный запрос."}, status=400)

    access_token = (data.get("access_token") or "").strip()
    process = (data.get("process") or "login").strip().lower()
    if process not in ("login", "signup"):
        process = "login"
    if not access_token:
        return JsonResponse({"ok": False, "error": "no_token", "message": "Нет токена VK."}, status=400)

    try:
        user = complete_vkid_session(request, access_token, process)
    except VkidSessionError as e:
        return JsonResponse({"ok": False, "error": e.code, "message": e.message}, status=e.status)

    redirect_url = _login_user_and_redirect_url(request, user)
    return JsonResponse({"ok": True, "redirect": redirect_url})
