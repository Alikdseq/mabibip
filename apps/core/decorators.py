"""Общие декораторы представлений."""

from functools import wraps
from urllib.parse import urlencode

from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponse
from django.urls import reverse


def htmx_login_required(view_func):
    """
    Как login_required, но для HTMX-запросов отдаёт HX-Redirect на страницу входа,
    чтобы браузер выполнил полную навигацию (а не подменил фрагмент модалки HTML логина).
    """

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        next_path = request.get_full_path()
        login_url = reverse("users:login")
        target = f"{login_url}?{urlencode({'next': next_path})}"
        if (request.headers.get("HX-Request") or "").lower() == "true":
            resp = HttpResponse(status=200)
            resp["HX-Redirect"] = target
            return resp
        return redirect_to_login(next_path)

    return _wrapped
