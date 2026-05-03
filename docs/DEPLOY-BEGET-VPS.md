# Деплой МаБибип на Beget VPS (Docker Compose + Nginx + HTTPS)

Ниже — пошаговый runbook для Ubuntu (рекомендуется **22.04 LTS** или **24.04 LTS**) под домен `mabibip.ru`.

## 0) Предварительно (DNS)

- A‑record `mabibip.ru` → `185.225.35.109`
- A‑record `www.mabibip.ru` → `185.225.35.109` (или CNAME на `mabibip.ru`)

Проверьте, что DNS уже отдает IP:

```bash
dig +short mabibip.ru
dig +short www.mabibip.ru
```

## 1) Подготовка сервера

### 1.1 Обновления + базовые пакеты

```bash
sudo apt update && sudo apt -y upgrade
sudo apt -y install ca-certificates curl gnupg git ufw
```

### 1.2 Firewall (ufw)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status
```

### 1.3 Docker + docker compose

Официальный Docker Engine:

```bash
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
docker --version
docker compose version
```

## 2) Клонирование проекта

```bash
sudo mkdir -p /opt/mabibip
sudo chown -R $USER:$USER /opt/mabibip
cd /opt/mabibip

git clone <YOUR_REPO_URL> app
cd app
```

## 3) Production env (`.env.prod`)

Создайте файл `.env.prod` рядом с `docker-compose.yml`.

Минимальный пример (подстройте пароли/секреты):

```dotenv
DJANGO_SETTINGS_MODULE=config.settings.prod
DEBUG=False
SECRET_KEY=sjfuoshdh37yr32gguwy8dgg283gdibshdbbi2j3897823yevghv34685y23vdhg

SITE_BASE_URL=https://mabibip.ru
ALLOWED_HOSTS=mabibip.ru,www.mabibip.ru,185.225.35.109
CSRF_TRUSTED_ORIGINS=https://mabibip.ru,https://www.mabibip.ru

# Postgres (docker compose db)
POSTGRES_USER=promaster
POSTGRES_PASSWORD=sdijbwuhfu34uri2gruhvdbfjheufg2urroiwbdfhb
POSTGRES_DB=promaster

DATABASE_URL=postgres://promaster:sdijbwuhfu34uri2gruhvdbfjheufg2urroiwbdfhb@db:5432/promaster

REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1

# Email (SMTP) — взято из вашего текущего .env
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=alihanskaev@gmail.com
EMAIL_HOST_PASSWORD=npik jlcg eiga nboj
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=alihanskaev@gmail.com

# reCAPTCHA (БОЕВЫЕ ключи; в проде RECAPTCHA_SKIP НЕ ставим)
RECAPTCHA_SITE_KEY=6Le2X9QsAAAAADQB5j5A8uPO0jS2vIz_ErJl1KUY
RECAPTCHA_SECRET_KEY=6Le2X9QsAAAAAK4TOlV1zP3jMYnUgRE8OR37wHpy

# ЮKassa (на старте выключено)
YOOKASSA_ENABLED=0
YOOKASSA_SHOP_ID=
YOOKASSA_SECRET_KEY=
YOOKASSA_WEBHOOK_SECRET=
```

## 4) Запуск контейнеров

```bash
docker compose --env-file .env.prod up -d --build
docker compose ps
```

Проверка логов:

```bash
docker compose logs -n 200 --no-color web
docker compose logs -n 200 --no-color asgi
```

## 5) Миграции + статика + legal seed

```bash
docker compose --env-file .env.prod run --rm web python manage.py migrate
docker compose --env-file .env.prod run --rm web python manage.py collectstatic --noinput
docker compose --env-file .env.prod run --rm web python manage.py seed_legal_documents --version-label=prod-1 --effective-now
docker compose --env-file .env.prod run --rm web python manage.py sync_site_domain
```

## 6) Nginx + HTTPS (Let’s Encrypt)

### 6.1 Установка Nginx + certbot

```bash
sudo apt -y install nginx certbot python3-certbot-nginx
sudo systemctl enable nginx
sudo systemctl start nginx
```

### 6.2 Конфиг Nginx

- Возьмите пример `deploy/nginx/promaster.conf.example` из репозитория и адаптируйте.
- В блоке `server { ... }` для HTTPS должно быть **`client_max_body_size 80m;`** (объявления с до 15 фото по 5 МБ). Если стоит **`10m`**, **`1m`** или директива отсутствует (дефолт 1 МБ), при создании объявления возможен **`413 Request Entity Too Large`** от Nginx.
- Важно: проксирование на Docker‑сервисы `web:8000` и `asgi:8001` (если у вас websocket `/ws/`).

Вариант: положить конфиг в `/etc/nginx/sites-available/mabibip` и включить:

```bash
sudo ln -s /etc/nginx/sites-available/mabibip /etc/nginx/sites-enabled/mabibip
sudo nginx -t
sudo systemctl reload nginx
```

### 6.3 Выпуск сертификата

```bash
sudo certbot --nginx -d mabibip.ru -d www.mabibip.ru
```

Проверка автообновления:

```bash
sudo certbot renew --dry-run
```

### 6.4 Gzip (меньше трафика на мобильном интернете)

В `server { ... }` для HTTPS добавьте сжатие текстовых типов (пример уже в [`deploy/nginx/promaster.conf.example`](../deploy/nginx/promaster.conf.example)):

- `gzip on;`
- `gzip_types text/css application/javascript ...`

Проверка:

```bash
curl -H "Accept-Encoding: gzip" -I https://mabibip.ru/static/theme.css
```

В ответе должно быть `Content-Encoding: gzip` (для подходящих типов).

### 6.5 Логотипы марок: WebP для `<picture>`

Логотипы лежат в **`static/logo/`** (в контейнере: **`/app/static/logo/`**). В шаблонах марки выводятся через [`templates/stations/includes/car_brand_choice_tile.html`](../templates/stations/includes/car_brand_choice_tile.html) — там уже есть `<picture>` / WebP при наличии файла рядом с PNG.

**Рекомендуемый способ (Pillow внутри образа, без `apt` и без пользователя `root`):**

```bash
cd /opt/mabibip/app
docker compose --env-file .env.prod run --rm web python manage.py optimize_brand_logos
docker compose --env-file .env.prod run --rm web python manage.py collectstatic --noinput
docker compose --env-file .env.prod restart web
```

Параметры качества: `python manage.py optimize_brand_logos --quality 80`  
Пересоздать все `.webp`: `--force`

Проверка пути к файлам:

```bash
docker compose --env-file .env.prod exec web ls -la /app/static/logo/ | head
```

**Важно:** в образе контейнер по умолчанию работает от пользователя **`app`** — команды вида `apt install` через `exec web` без `-u root` **не сработают**. Не используйте `static/images/` для марок — в проекте это **`static/logo/`**.

**Альтернатива — `cwebp` от root** (если принципиально нужна утилита Google):

```bash
docker compose --env-file .env.prod exec -u root web bash -lc \
  "apt-get update && apt-get install -y --no-install-recommends webp && \
   cd /app/static/logo && for f in *.png; do [ -f \"\$f\" ] && cwebp -q 80 \"\$f\" -o \"\${f%.png}.webp\"; done"
docker compose --env-file .env.prod run --rm web python manage.py collectstatic --noinput
docker compose --env-file .env.prod restart web
```

После генерации WebP при отсутствии bind-mount каталога с кодом закоммитьте новые `*.webp` в Git — иначе они пропадут при пересборке образа без копии файлов в образ.

### Про скрипты `webcomponents-bundle` / `main.tsx`

В репозитории шаблоны **не подключают** такие имена — см. раздел **6.6** (расширения браузера). Добавлять `defer` к несуществующим в проекте скриптам не нужно.

### 6.6 DevTools Network: не путать сайт с расширениями

Если в Network видны скрипты с именами вроде `webcomponents-bundle-*.js`, `main.tsx-*`, `client-*.js` (хэши Vite) — проверьте колонку **Initiator**:

- если источник `chrome-extension://` или не ваш домен — это часто **расширение браузера**, а не проект;
- повторите замер в **режиме инкогнито без расширений**.

## 6.7) Вход через VK (опционально)

См. **[VK-OAUTH.md](VK-OAUTH.md)**: переменные `VK_CLIENT_ID` / `VK_CLIENT_SECRET` в `.env.prod`, redirect URI в кабинете VK.

## 7) Проверка после деплоя (checklist)

- `https://mabibip.ru/` открывается, есть редирект с http → https
- `/accounts/login/` и `/accounts/register/` работают
- Письма уходят (если SMTP задан), ссылки ведут на `https://mabibip.ru/...`
- Статика отдается (CSS/JS без 404)
- Для CSS/JS включён gzip: `curl -H "Accept-Encoding: gzip" -I https://mabibip.ru/static/theme.css` → при необходимости `Content-Encoding: gzip`
- ERP/админка: `/secure-admin/` (или ваш admin URL) доступна суперпользователю
- `python manage.py sync_site_domain` отработал, `django_site.domain` = `mabibip.ru`

## 8) Типовые команды обслуживания

```bash
# Обновить код
cd /opt/mabibip/app
git pull

# Пересобрать/перезапустить
docker compose --env-file .env.prod up -d --build

# Логи
docker compose logs -f web
```

