# Продакшен: Nginx + Gunicorn + Uvicorn (WebSocket)

Клиент открывает **один** origin (`https://ваш-домен.ru`). Пути **`/ws/...`** должны попадать в **ASGI** (Uvicorn с `config.asgi:application`), остальное — в **WSGI** (Gunicorn). Иначе чаты и бейджи в реальном времени не заработают.

## Вариант 1: Nginx на VPS (systemd), приложение в Docker или на localhost

Используйте **`deploy/nginx/promaster.conf.example`** как основу:

1. Скопируйте в `/etc/nginx/sites-available/` (или `conf.d/`), замените `example.com`, пути к сертификатам Let’s Encrypt и при необходимости порты upstream.
2. Upstream:
   - **8000** — Gunicorn (`config.wsgi`);
   - **8001** — Uvicorn (`config.asgi:application`).
3. Блок **`location /ws/`** обязателен: `Upgrade`, `Connection`, `proxy_http_version 1.1`, увеличенные `proxy_read_timeout` / `proxy_send_timeout` для долгих сессий.
4. В `.env` продакшена: `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` с вашим доменом. В `config.settings.prod` уже заданы `SECURE_PROXY_SSL_HEADER` и `USE_X_FORWARDED_HOST` — Nginx должен передавать `X-Forwarded-Proto` и `Host`.

**Не задавайте** `CHANNELS_WS_CLIENT_BASE_URL`, если сайт и WebSocket с одного хоста (браузер сам возьмёт `wss://тот-же-домен/ws/...`).

## Вариант 2: Всё в Docker, Nginx — контейнер перед `web` и `asgi`

```bash
docker compose -f docker-compose.yml -f deploy/docker-compose.frontend.yml up -d
```

- Конфиг: **`deploy/nginx/docker-frontend.conf`** (`web:8000`, `asgi:8001`).
- Порт снаружи: **`NGINX_HTTP_PORT`** (по умолчанию **8080**; на чистом сервере можно **80**).

Если TLS терминирует **внешний** прокси (или второй Nginx на хосте) и до контейнера идёт HTTP, включите у **`web`** и **`asgi`** в окружении:

```env
USE_X_FORWARDED_HOST=1
SECURE_PROXY_SSL_HEADER=1
```

чтобы Django видел HTTPS и корректный хост (для `docker`-настроек; см. `config/settings/docker.py`).

## Загрузка файлов (объявления, фото СТО и т.д.)

Если при создании объявления с несколькими фото браузер показывает **`413 Request Entity Too Large`** (`nginx/...`), увеличьте в **`server { ... }`** директиву **`client_max_body_size`** до **`80m`** (в репозитории так задано в [`deploy/nginx/promaster.conf.example`](../deploy/nginx/promaster.conf.example) и [`deploy/nginx/docker-frontend.conf`](../deploy/nginx/docker-frontend.conf)). По умолчанию у Nginx часто **1 МБ** — этого недостаточно даже для одного крупного снимка.

После правки:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

## Redis

Channels использует **`CHANNEL_REDIS_URL`** / **`REDIS_URL`**. Без Redis WebSocket-процессы не увидят друг друга.

## Проверка после деплоя

1. Откройте сайт по HTTPS.
2. DevTools → Network → **WS**: подключение к `wss://ваш-домен/ws/user-inbox/` со статусом **101**.
3. Два браузера — сообщение в чате по записи без перезагрузки.
