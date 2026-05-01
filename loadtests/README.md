## Нагрузочные тесты (Locust) — F11

### Быстрый старт (Docker)

1) Подними сервисы и демо-данные:

```bash
docker compose up -d --build
docker compose run --rm web python manage.py seed_demo
```

2) Создай пользователя для нагрузочного теста (один на всех пользователей Locust допустимо для MVP):

```bash
docker compose run --rm web python manage.py shell -c "from apps.users.models import User; u,_=User.objects.get_or_create(phone='+79990009999', defaults={'is_active':True,'is_phone_verified':True}); u.set_password('loadtest-pass'); u.save()"
```

3) Запусти Locust локально (на хосте) или в отдельном окружении:

```bash
pip install -r requirements/dev.txt
set LOCUST_HOST=http://127.0.0.1:8000
set LOADTEST_PHONE=+79990009999
set LOADTEST_PASSWORD=loadtest-pass
locust -f loadtests/locustfile.py --host %LOCUST_HOST%
```

Открой UI Locust: `http://127.0.0.1:8089`.

### Сценарии

- **Каталог**: `/sto/` (поиск/фильтры)
- **Геопоиск**: `/api/stations/nearby/`
- **Бронь**: `/sto/<slug>/slots/` → `/book/<slot>/form/` → `/book/<slot>/submit/`
- **WebSocket чат**: `/ws/chat/<booking_id>/` (best-effort; требует валидной сессии и доступного ASGI)

### Отчёт

Шаблон отчёта: `loadtests/REPORT_TEMPLATE.md`.

