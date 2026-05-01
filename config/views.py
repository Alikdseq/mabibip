"""Обработчики ошибок и вспомогательные view (фаза 9)."""

from django.shortcuts import render


def handler404(request, exception):
    """Публичная 404 без технических деталей."""
    return render(request, "errors/404.html", status=404)


def handler500(request):
    """Публичная 500 без stack trace в ответе (детали — только в логах при DEBUG=False)."""
    return render(request, "errors/500.html", status=500)
