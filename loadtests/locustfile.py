from __future__ import annotations

import json
import os
import random
import re
import time
from urllib.parse import urlparse

from locust import HttpUser, between, events, task
from websocket import create_connection


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _pick_booking_id(html: str) -> int | None:
    # Looks for /ws/chat/<booking_id>/ in page source.
    m = re.search(r"/ws/chat/(?P<id>\d+)/", html)
    if not m:
        return None
    try:
        return int(m.group("id"))
    except ValueError:
        return None


class PromasterUser(HttpUser):
    """
    F11 scenarios:
    - catalog list/search + filters
    - geo nearby API
    - booking flow (login + station detail + slots partial + book submit)
    - websocket chat connect + send (best-effort)
    """

    wait_time = between(0.3, 1.5)

    def on_start(self):
        # Assumes demo data exists. Recommended:
        #   python manage.py seed_demo
        # And a client user exists with password.
        self.phone = _env("LOADTEST_PHONE", "+79990009999")
        self.password = _env("LOADTEST_PASSWORD", "loadtest-pass")
        self.recaptcha_token = _env("LOADTEST_RECAPTCHA_TOKEN", "test")

        # best-effort login (recaptcha is often skipped in tests/dev)
        self.client.get("/accounts/login/")
        self.client.post(
            "/accounts/login/",
            data={"username": self.phone, "password": self.password, "recaptcha_token": self.recaptcha_token},
            name="/accounts/login/ (post)",
            allow_redirects=True,
        )

    @task(5)
    def catalog_browse(self):
        q = random.choice(["", "Сервис", "Юг", "Центр", "ул.", "шином", "льфа"])
        params = {}
        if q:
            params["q"] = q
        if random.random() < 0.3:
            params["slots_today"] = "1"
        if random.random() < 0.3:
            params["rating_gt"] = random.choice(["3", "4", "5"])
        self.client.get("/sto/", params=params, name="/sto/ (catalog)")

    @task(2)
    def geo_nearby_api(self):
        # Moscow-ish point; radius in km
        params = {"lat": "55.751244", "lng": "37.618423", "radius_km": "10"}
        self.client.get("/api/stations/nearby/", params=params, name="/api/stations/nearby/")

    @task(2)
    def station_detail(self):
        slug = random.choice(["demo-0", "demo-1", "demo-2"])
        self.client.get(f"/sto/{slug}/", name="/sto/<slug>/ (detail)")

    @task(1)
    def booking_flow(self):
        slug = random.choice(["demo-0", "demo-1", "demo-2"])
        r = self.client.get(f"/sto/{slug}/", name="/sto/<slug>/ (detail for booking)")
        if r.status_code != 200:
            return

        # slots partial for today
        r2 = self.client.get(f"/sto/{slug}/slots/", name="/sto/<slug>/slots/")
        if r2.status_code != 200:
            return

        # naive: pick first slot_id in HTML (data-slot-id="123" or /book/<id>/form/)
        m = re.search(r"/book/(?P<sid>\d+)/form/", r2.text)
        if not m:
            return
        slot_id = int(m.group("sid"))

        # open booking form (holds slot)
        self.client.get(f"/sto/{slug}/book/{slot_id}/form/", name="/sto/<slug>/book/<slot_id>/form/")

        # submit booking
        payload = {
            "car_info": "LOADTEST",
            "contact_phone": self.phone,
            "description": "load test booking",
        }
        self.client.post(
            f"/sto/{slug}/book/{slot_id}/submit/",
            data=payload,
            name="/sto/<slug>/book/<slot_id>/submit/",
            allow_redirects=True,
        )

    @task(1)
    def websocket_chat(self):
        """
        Best-effort WebSocket test:
        - opens a page that likely contains booking_id in links
        - connects to ws://<host>/ws/chat/<booking_id>/
        Requires:
        - ASGI server reachable
        - session cookie auth (Channels AuthMiddlewareStack)
        """
        # try to discover booking id from cabinet page (if present in project)
        r = self.client.get("/cabinet/bookings/", name="/cabinet/bookings/")
        if r.status_code != 200:
            return
        booking_id = _pick_booking_id(r.text)
        if not booking_id:
            return

        base = urlparse(self.host)
        ws_scheme = "wss" if base.scheme == "https" else "ws"
        ws_url = f"{ws_scheme}://{base.netloc}/ws/chat/{booking_id}/"

        # carry session cookie to WS
        cookies = self.client.cookies
        cookie_header = "; ".join([f"{k}={v}" for k, v in cookies.items()])

        start = time.time()
        try:
            ws = create_connection(ws_url, header=[f"Cookie: {cookie_header}"], timeout=3)
            ws.send(json.dumps({"type": "message", "text": "ping"}))
            ws.close()
            total_ms = (time.time() - start) * 1000
            events.request.fire(
                request_type="WS",
                name="/ws/chat/<booking_id>/",
                response_time=total_ms,
                response_length=0,
                exception=None,
            )
        except Exception as e:
            total_ms = (time.time() - start) * 1000
            events.request.fire(
                request_type="WS",
                name="/ws/chat/<booking_id>/",
                response_time=total_ms,
                response_length=0,
                exception=e,
            )

