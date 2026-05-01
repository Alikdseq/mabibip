# ПроМастер — веб-контейнер (Django + Gunicorn + WhiteNoise)
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DJANGO_SETTINGS_MODULE=config.settings.docker

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        binutils \
        libproj25 \
        gdal-bin \
        libgdal32 \
        libsqlite3-mod-spatialite \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/base.txt requirements/prod.txt requirements/dev.txt /app/requirements/
# Для локального docker compose держим dev-инструменты внутри образа (pytest/ruff/locust и т.д.).
RUN pip install --no-cache-dir -r requirements/base.txt -r requirements/prod.txt -r requirements/dev.txt

COPY . /app/

RUN mkdir -p /app/media /app/staticfiles \
    && addgroup --system app \
    && adduser --system --ingroup app --home /home/app --shell /usr/sbin/nologin app \
    && chown -R app:app /app /home/app

# entrypoint.py вместо .sh — на Windows не ломается из-за CRLF
EXPOSE 8000

USER app
ENTRYPOINT ["python", "/app/docker/entrypoint.py"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60", "config.wsgi:application"]
