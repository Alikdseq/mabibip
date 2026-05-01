from __future__ import annotations

import uuid
from decimal import Decimal

import requests
from django.conf import settings


class YooKassaError(RuntimeError):
    pass


def _auth_tuple() -> tuple[str, str]:
    shop_id = getattr(settings, "YOOKASSA_SHOP_ID", "").strip()
    secret = getattr(settings, "YOOKASSA_SECRET_KEY", "").strip()
    if not shop_id or not secret:
        raise YooKassaError("YOOKASSA_SHOP_ID/YOOKASSA_SECRET_KEY not configured")
    return shop_id, secret


def _api_base() -> str:
    return "https://api.yookassa.ru/v3"


def create_payment(
    *,
    amount: Decimal,
    currency: str,
    description: str,
    return_url: str,
    metadata: dict,
    idempotency_key: str | None = None,
) -> dict:
    """
    Создать платёж в ЮKassa. Возвращает JSON ответа провайдера.
    MVP: обычный платёж на магазин. «Холд» делаем на нашей стороне (wallet ledger).
    """
    idem = idempotency_key or uuid.uuid4().hex
    payload = {
        "amount": {"value": f"{amount:.2f}", "currency": currency},
        "confirmation": {"type": "redirect", "return_url": return_url},
        "capture": True,
        "description": description,
        "metadata": metadata or {},
    }
    r = requests.post(
        f"{_api_base()}/payments",
        json=payload,
        auth=_auth_tuple(),
        headers={"Idempotence-Key": idem},
        timeout=20,
    )
    if r.status_code >= 400:
        raise YooKassaError(f"create_payment failed status={r.status_code} body={r.text[:500]}")
    return r.json()


def create_refund(
    *,
    payment_id: str,
    amount: Decimal,
    currency: str,
    description: str,
    metadata: dict,
    idempotency_key: str | None = None,
) -> dict:
    """
    Возврат платежа через ЮKassa. Возвращает JSON ответа провайдера.
    """
    idem = idempotency_key or uuid.uuid4().hex
    payload = {
        "payment_id": payment_id,
        "amount": {"value": f"{amount:.2f}", "currency": currency},
        "description": description,
        "metadata": metadata or {},
    }
    r = requests.post(
        f"{_api_base()}/refunds",
        json=payload,
        auth=_auth_tuple(),
        headers={"Idempotence-Key": idem},
        timeout=20,
    )
    if r.status_code >= 400:
        raise YooKassaError(f"create_refund failed status={r.status_code} body={r.text[:500]}")
    return r.json()

