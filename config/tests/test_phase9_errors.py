"""Фаза 9: публичные страницы ошибок без утечки stack trace."""

from django.urls import reverse

from config.views import handler500


def test_custom_404_uses_template(client):
    r = client.get("/no-such-path-promaster-9/")
    assert r.status_code == 404
    body = r.content.decode()
    assert "Страница не найдена" in body
    assert "Traceback" not in body


def test_handler500_response_has_no_traceback():
    from django.test import RequestFactory

    request = RequestFactory().get("/")
    response = handler500(request)
    assert response.status_code == 500
    body = response.content.decode()
    assert "Traceback" not in body
    assert "Не удалось обработать запрос" in body or "внутренняя ошибка" in body.lower()


def test_home_still_ok(client):
    assert client.get(reverse("home")).status_code == 200
