from .celery import app as celery_app

app = celery_app

__all__ = ("app", "celery_app")
