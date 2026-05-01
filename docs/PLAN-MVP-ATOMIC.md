# Атомарный план разработки MVP «ПроМастер»

**Назначение:** пошаговый чеклист от пустой машины до продакшена. Каждый пункт — одно логически завершённое действие с указанием артефакта, теста и контроля безопасности.  
**База требований:** `docs/ТЗ-MVP-ПроМастер.md`.  
**Принцип:** сначала архитектура и тестовый каркас, затем вертикальные срезы по фичам.

---

## 0. Договорённости по качеству (прочитать один раз, применять всегда)

### 0.1. Структура репозитория (целевая)

```text
promaster/ # корень репозитория
├── manage.py
├── requirements/
│   ├── base.txt
│   ├── dev.txt
│   └── prod.txt
├── config/                     # настройки проекта (имя может быть core/ settings/)
│   ├── __init__.py
│   ├── urls.py
│   ├── wsgi.py
│   └── settings/
│       ├── __init__.py
│       ├── base.py
│       ├── dev.py
│       └── prod.py
├── apps/
│   ├── users/
│   ├── stations/
│   ├── bookings/
│   └── reviews/
├── templates/
├── static/
├── tests/                      # опционально: сквозные / e2e заготовки
└── locale/                     # при необходимости i18n
```

**Шаг 0.1.1.** Создать репозиторий Git, ветки `main` (защищённая) и рабочая `develop` (или прямой `main` при соло — зафиксировать правило).  
**Шаг 0.1.2.** Добавить `.gitignore` (Python, Django, `.env`, `__pycache__`, `media/`, `db.sqlite3` если не используется).  
**Шаг 0.1.3.** Добавить `.env.example` со **всеми** переменными без секретов (шаблон значений-плейсхолдеров).

### 0.2. Инструменты разработки

**Шаг 0.2.1.** Установить Python **3.12+** (совместимо с Django 5).  
**Шаг 0.2.2.** Создать виртуальное окружение `venv` в корне проекта.  
**Шаг 0.2.3.** Зафиксировать версии в `requirements/base.txt`: `Django>=5.0,<6`, `djangorestframework`, `psycopg[binary]`, `python-dotenv`, `Pillow` (для ImageField фото).  
**Шаг 0.2.4.** В `requirements/dev.txt`: `pytest`, `pytest-django`, `pytest-cov`, `factory-boy`, `ruff` (или `flake8`+`black`), `pre-commit` (опционально).  
**Шаг 0.2.5.** В `requirements/prod.txt`: `gunicorn`, `whitenoise` (опционально для статики).

### 0.3. Конфигурация pytest

**Шаг 0.3.1.** В корне создать `pytest.ini`:

- `DJANGO_SETTINGS_MODULE=config.settings.dev` (или `tests`)
- `python_files = tests.py test_*.py *_tests.py`
- `addopts = --reuse-db` (ускорение)

**Шаг 0.3.2.** Создать `config/settings/tests.py`, наследник `base.py`: БД — SQLite in-memory **или** отдельная тестовая Postgres (предпочтительно SQLite для скорости MVP, с оговоркой о различиях с Postgres).

**Шаг 0.3.3.** Убедиться, что `python -m pytest` запускается с нулевыми тестами (exit0).

### 0.4. Единые бизнес-константы (вынести в код с первого дня)

**Шаг 0.4.1.** Файл `apps/stations/constants.py` (или `config/constants.py`):`SUBSCRIPTION_PLAN_FREE = "free"`, `SUBSCRIPTION_PLAN_BASIC = "basic"`.  
**Шаг 0.4.2.** Файл `apps/bookings/constants.py`: статусы `BookingStatus.PENDING`, `CONFIRMED`, `COMPLETED`, `CANCELED` — **только** через `TextChoices` (см. фазу моделей).  
**Шаг 0.4.3.** Константа `PENDING_BOOKING_EXPIRE_MINUTES = 30` (слот / бронь).  
**Шаг 0.4.4.** Константа `CATALOG_DAY_RANGE = 7` (сетка дней на карточке СТО).

### 0.5. Безопасность: нулевой этап

**Шаг 0.5.1.** Запрет хранения секретов в коде; чтение из `os.environ` в `base.py` через безопасные дефолты только для некритичных вещей.  
**Шаг 0.5.2.** В `prod.py`: `DEBUG=False`, `ALLOWED_HOSTS` только из env, `SECURE_*` cookie и HSTS — включить по чеклисту фазы деплоя.  
**Шаг 0.5.3.** Решить политику паролей: `AUTH_PASSWORD_VALIDATORS` — стандартные Django **без ослабления** на проде.  
**Шаг 0.5.4.** Запланировать нестандартный путь админки (например `/secure-admin/`) — реализовать в фазе URL.

---

## Фаза 1. Каркас Django-проекта и настройки

**Шаг 1.1.1.** Выполнить `django-admin startproject` так, чтобы пакет настроек совпал с выбранной структурой (`config` + `settings` package).  
**Шаг 1.1.2.** Перенести `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, параметры БД в переменные окружения; в `base.py` читать через `os.getenv`.  
**Шаг 1.1.3.** В `base.py` зарегистрировать `apps.*` в `INSTALLED_APPS` (пока пустые приложения создадим в шаге 1.2).  
**Шаг 1.1.4.** Настроить `TIME_ZONE = "Europe/Moscow"`, `USE_TZ = True`, язык `ru-ru` (по желанию).  
**Шаг 1.1.5.** Настроить `STATIC_URL`, `STATIC_ROOT`, `MEDIA_URL`, `MEDIA_ROOT` (например `BASE_DIR / "media"`).  
**Шаг 1.1.6.** В `dev.py`: `DEBUG=True`, `ALLOWED_HOSTS=["localhost","127.0.0.1"]`, подключить `django_extensions` **опционально**.  
**Шаг 1.1.7.** В `prod.py`: импорт из base, принудительно `DEBUG=False`, строгие `ALLOWED_HOSTS`.

**Тест 1.1.T1.** `manage.py check` без ошибок на `dev` и `prod` settings.  
**Тест 1.1.T2.** Минимальный тест pytest: импорт `django` и `settings`, assert `SECRET_KEY` не равен строке `"change-me"` в prod-конфиге при загрузке из env mock.

**Шаг 1.2.1.** `python manage.py startapp users` → переместить в `apps/users`.  
**Шаг 1.2.2.** `startapp stations` → `apps/stations`.  
**Шаг 1.2.3.** `startapp bookings` → `apps/bookings`.  
**Шаг 1.2.4.** `startapp reviews` → `apps/reviews`.  
**Шаг 1.2.5.** Добавить в каждый `apps.py` осмысленные `verbose_name` на русском.  
**Шаг 1.2.6.** Создать пустой `apps/core/` **опционально** для общих утилит (`mixins.py`, `permissions.py`) — либо класть в `stations` до появления третьего потребителя.

---

## Фаза 2. Модель пользователя и аутентификация

### 2.1. Модель

**Шаг 2.1.1.** В `apps/users/models.py` объявить `User(AbstractUser)`:  
- убрать `username` из использования: `username = None`  
- `email = EmailField(unique=True)`  
- `USERNAME_FIELD = "email"`  
- `REQUIRED_FIELDS = []`  
- `phone = CharField(max_length=20, blank=True)`  
- `is_sto_owner = BooleanField(default=False)`  
**Шаг 2.1.2.** `AUTH_USER_MODEL = "users.User"` в `base.py`.  
**Шаг 2.1.3.** Создать миграции; применить к dev БД.

**Тест 2.1.T1.** Создание пользователя через `User.objects.create_user(email="a@b.c", password="x")` — успех.  
**Тест 2.1.T2.** Уникальность email — `IntegrityError` при дубле.

### 2.2. Админка пользователя

**Шаг 2.2.1.** Зарегистрировать `User` в `admin.py` с полями: email, is_sto_owner, is_staff, is_active, даты.  
**Шаг 2.2.2.** Форма создания пользователя через админку должна задавать пароль хешированно (`UserAdmin` из документации Django для email-user).

### 2.3. Регистрация клиента и подтверждение email

**Шаг 2.3.1.** Выбрать стратегию активации: **рекомендация MVP** — `django-allauth` **не** подключать ради экономии времени; использовать связку:  
- при регистрации `User.is_active = False`  
- генерация токена `default_token_generator` + `uid`  
- ссылка в письме ведёт на view `activate` → `is_active=True`  

**Шаг 2.3.2.** Создать форму `UserRegistrationForm` (email, password1, password2) с валидацией email.  
**Шаг 2.3.3.** View `register` (GET/POST), шаблон `templates/users/register.html`.  
**Шаг 2.3.4.** View `activate(request, uidb64, token)` — при успехе редирект на login с сообщением.  
**Шаг 2.3.5.** Настроить `EMAIL_BACKEND` в dev: `console`; в prod — SMTP env (`EMAIL_HOST`, `PORT`, `USER`, `PASSWORD`, `USE_TLS`).  
**Шаг 2.3.6.** Шаблон письма: текстовый + простой HTML без внешних ресурсов.

**Тест 2.3.T1.** POST регистрации создаёт неактивного пользователя.  
**Тест 2.3.T2.** Валидный токен активирует; невалидный — нет.  
**Тест 2.3.T3.** CSRF: форма содержит `{% csrf_token %}` — проверка клиентом вручную + тест view с `csrf_exempt` **не** использовать.

### 2.4. Вход, выход, сброс пароля

**Шаг 2.4.1.** Подключить `LoginView` / `LogoutView` из `django.contrib.auth.views` с шаблонами `users/login.html`.  
**Шаг 2.4.2.** `LOGIN_REDIRECT_URL` — личный кабинет клиента `/cabinet/` (создадим позже; временно `/`).  
**Шаг 2.4.3.** Включить стандартные URL сброса пароля Django (`PasswordResetView` и т.д.) + шаблоны с Bootstrap.

**Тест 2.4.T1.** Логин активного пользователя редиректит.  
**Тест 2.4.T2.** Неактивный не может войти.

### 2.5. URL и базовый шаблон

**Шаг 2.5.1.** `config/urls.py`: включить `path("accounts/", include(...))` для auth views + кастомные `register`, `activate`.  
**Шаг 2.5.2.** Создать `templates/base.html`: Bootstrap 5 CDN, блоки `title`, `content`, `extra_js`, подключение HTMX (`<script src="https://unpkg.com/htmx.org@..."></script>`) и Alpine (`defer`).  
**Шаг 2.5.3.** Navbar: ссылки Каталог, Вход/Регистрация или ЛК / Выход в зависимости от `user.is_authenticated`.

**Безопасность 2.S1.** Не логировать пароли и токены активации.  
**Безопасность 2.S2.** Rate limiting на уровне Nginx для `/accounts/login/` и `/accounts/register/` — запланировать в фазе деплоя (минимум — в коде `django-ratelimit` опционально).

---

## Фаза 3. Домен СТО: модели, админка, публичный каталог

### 3.1. Модели `ServiceStation`, `WorkBay`, фото

**Шаг 3.1.1.** `ServiceStation`: все поля из ТЗ + `subscription_plan` с `choices` через константы + индекс по `(is_active, subscription_plan)`.  
**Шаг 3.1.2.** Метод модели `is_visible_in_catalog(today: date) -> bool`:  
- если `not is_active` → False  
- если `subscription_plan == FREE` → True (или уточнить: free тоже требует дату — **зафиксировать**: для MVP `free` всегда видим при `is_active`; `basic` требует `subscription_paid_until >= today`)  
- если `basic` и (`subscription_paid_until` is None или `< today`) → False; иначе True  

**Шаг 3.1.3.** `WorkBay`: FK на станцию, `name`, `Meta.ordering`, `unique_together` или `UniqueConstraint` на `(station, name)` по решению (рекомендация: без жёсткого unique, только логика).  
**Шаг 3.1.4.** `StationPhoto`: FK `station`, `image = ImageField`, `order` small int; валидация **не более5** на станцию — в `clean()` модели или в `ModelForm` админки.  
**Шаг 3.1.5.** Миграции + индекс на `ServiceStation(name)` не обязателен для icontains; для масштаба позже — триграммы; MVP достаточно последовательного скана при <500 строк.

**Тест 3.1.T1.** `is_visible_in_catalog` для комбинаций free/basic и дат.  
**Тест 3.1.T2.** Нельзя сохранить 6-е фото (если валидация включена).

### 3.2. Админка СТО

**Шаг 3.2.1.** `ServiceStationAdmin`: inline для `WorkBay`, inline для `StationPhoto`, list_display: name, owner, plan, paid_until, is_active.  
**Шаг 3.2.2.** `raw_id_fields` или `autocomplete_fields` для `owner` (после настройки `search_fields` в UserAdmin).  
**Шаг 3.2.3.** Создать суперпользователя `createsuperuser` на email.

### 3.3. Менеджер / QuerySet для каталога

**Шаг 3.3.1.** `ServiceStation.objects.visible_in_catalog()` — фильтр по `is_visible_in_catalog` логике на уровне БД:  
- `Q(is_active=True) & (Q(subscription_plan=FREE) | Q(subscription_plan=BASIC, subscription_paid_until__gte=today))`  
Уточнить согласованность с методом модели — **один источник правды**: вынести в функцию `station_is_visible(station, today)` и использовать в менеджере и тестах.

**Тест 3.3.T1.** Queryset возвращает только ожидаемые станции на фиксированную дату (freeze time через `freezegun` опционально или передача `today` параметром в чистую функцию).

### 3.4. Публичные views: список и деталь

**Шаг 3.4.1.** View `StationListView(ListView)`: queryset `visible_in_catalog()`, контекст: форма поиска `q`.  
**Шаг 3.4.2.** Фильтр: если `q` не пусто — `filter(Q(name__icontains=q) | Q(address__icontains=q))`.  
**Шаг 3.4.3.** Аннотация среднего рейтинга: `annotate(avg_rating=Avg("bookings__review__rating"))` — **осторожно**: только завершённые брони с отзывом; корректнее аннотировать из `Review` через связь station:`Review.objects.filter(booking__station=OuterRef("pk"))` или простой подзапрос; для MVP допустимо `annotate` с `Avg` на `reviews` если FK review → booking → station. Разместить логику в `stations/selectors.py` функция `annotate_station_ratings(qs)`.  
**Шаг 3.4.4.** Индикатор «есть места сегодня»: подзапрос или префетч: существует ли `TimeSlot` с `date=today`, доступный для записи (логика слота уточняется в фазе 4) — функция `station_has_slots_today(station_id, today)`.  
**Шаг 3.4.5.** Шаблон списка: карточки Bootstrap, звёзды рейтинга (округление до 0.1), бейдж «Есть места сегодня».  
**Шаг 3.4.6.** `StationDetailView`: slug или pk; **проверка** `get_object` только из visible queryset — иначе 404 (не раскрывать скрытые СТО).  
**Шаг 3.4.7.** На детальной: галерея (carousel Bootstrap), описание, список отзывов (только с `booking__status=COMPLETED` и существующим review).

**Тест 3.4.T1.** Скрытая подпиской станция возвращает 404 на public detail.  
**Тест 3.4.T2.** Поиск `q` фильтрует корректно.  
**Тест 3.4.T3.** Средний рейтинг считается по двум отзывам (данные фикстуры).

### 3.5. Фикстуры данных

**Шаг 3.5.1.** Management command `seed_demo` или `pytest` factory:5–10 станций с владельцами, постами,1–2 фото.  
**Шаг 3.5.2.** Не коммитить бинарные фото большого размера — генерировать маленькие файлы в тестах через Pillow.

---

## Фаза 4. Слоты времени и бронирование (ядро)

### 4.1. Модель `TimeSlot`

**Шаг 4.1.1.** Поля: `bay`, `date`, `start_time`, `end_time`, `is_available` (bool, ручная блокировка владельцем/админом).  
**Шаг 4.1.2.** `clean()`: `start_time < end_time`; дата не в прошлом **при создании нового слота вручную владельцем** (с оговоркой: админ может править — по политике запретить прошлое в форме ЛК).  
**Шаг 4.1.3.** Индекс `(bay, date, start_time)` для выборок.  
**Шаг 4.1.4.** Функция `slot_is_bookable(slot, now)` → bool:  
- если `date < now.date()` (в прошлом) — False  
- если `not is_available` — False  
- если существует `Booking` на этот слот со статусом **не** `canceled` — False (включая `pending`, `confirmed`, `completed`)  
- иначе True  

После отмены (`canceled`) слот снова становится доступным для новой брони. Для `completed` слот остаётся «использованным» (повторная запись на то же окно не нужна); новые визиты — новые `TimeSlot`.

**Тест 4.1.T1.** `slot_is_bookable` на всех комбинациях.

### 4.2. Модель `Booking`

**Шаг 4.2.1.** Поля из ТЗ + `TextChoices` для статуса.  
**Шаг 4.2.2.** Индексы: `client`, `station`, `status`, `created_at`.  
**Шаг 4.2.3.** Связь со слотом: **`ForeignKey(TimeSlot)`**, не `OneToOne`, и в миграции добавить **частичный уникальный индекс** PostgreSQL: не более одной брони в статусах `pending` и `confirmed` на один слот (`UniqueConstraint` с `condition=Q(status__in=[PENDING, CONFIRMED])`). Так слот после `canceled`/`completed` может принять новую бронь при новом окне (для `completed` слот обычно не переиспользуется — по продукту: создавать новые слоты на будущие даты; при отмене слот снова в пуле).  
**Шаг 4.2.4.** Метод `can_transition_to(new_status, actor)` — заготовка для проверки прав (клиент vs владелец) — реализовать в сервисном слое.

### 4.3. Транзакция создания брони

**Шаг 4.3.1.** Файл `apps/bookings/services.py` функция `create_booking_request(*, client, slot_id, car_info, contact_phone, description, now)`:

1. `select_for_update()` на `TimeSlot` внутри `transaction.atomic()`.  
2. Повторная проверка `slot_is_bookable`.  
3. Создать `Booking` со статусом `pending`, поле `sto_confirm_deadline = now + timedelta(hours=1)`.  
4. Слот не дублировать флагами: занятость определяется связанной бронью (см. `slot_is_bookable`). При желании можно выставить `is_available=False` для ясности в админке — но тогда при `canceled` сбрасывать обратно; **рекомендация MVP:** не трогать `is_available` при брони, только проверять брони.  
5. Вернуть booking.

**Шаг 4.3.2.** Обработать `IntegrityError` / race — ответ пользователю «окно занято».

**Тест 4.3.T1.** Два параллельных `create_booking_request` — только один успех (тест с `Thread` или последовательный вызов с блокировкой симуляцией).  
**Тест 4.3.T2.** После успеха слот не появляется в списке свободных.

### 4.4. Автоотмена `pending` (дедлайн для СТО)

**Шаг 4.4.1.** Поле `Booking.sto_confirm_deadline` (DateTime): при создании брони = `created_at + 60 минут` (как в пользовательском тексте ТЗ: СТО подтверждает в течение часа). Слот считается занятым, пока бронь в `pending` или `confirmed` (см. частичный уникальный индекс в шаге 4.2.3).

**Шаг 4.4.2.** Management command `expire_unconfirmed_bookings`: выбрать брони `status=pending` и `sto_confirm_deadline < now`, перевести в `canceled`. Запись брони **сохраняется** (история); слот снова доступен для новой брони, т.к. активных `pending`/`confirmed` на этот слот больше нет.

**Шаг 4.4.3.** Cron каждые **5 минут**: `*/5 * * * * ... manage.py expire_unconfirmed_bookings`.

**Шаг 4.4.4.** (Опционально) В UI на странице успеха можно текстом упомянуть «окно удерживается до подтверждения СТО, не более часа» — без отдельного таймера 30 мин, чтобы не дублировать две конкурирующие логики.

**Тест 4.4.T1.** Команда переводит просроченные `pending` в `canceled`; слот снова в списке `slot_is_bookable`.

### 4.5. Форма записи (модальное окно)

**Шаг 4.5.1.** HTMX: клик по слоту подгружает фрагмент формы `GET /stations/<pk>/book/<slot_id>/form/` (login_required).  
**Шаг 4.5.2.** POST создаёт бронь; ответ — редирект полной страницы HX-Redirect на «спасибо».  
**Шаг 4.5.3.** Валидация: телефон простым regex RU; длины полей.

**Тест 4.5.T1.** Неавторизованный редирект на login.  
**Тест 4.5.T2.** POST с чужим `slot_id` другой станции — 404.

### 4.6. Email владельцу СТО

**Шаг 4.6.1.** После успешного `create_booking_request` вызвать `mail_sto_new_booking(booking)` синхронно.  
**Шаг 4.6.2.** Шаблон письма: id брони, станция, время, ссылка на ЛК СТО (absolute_uri из `request.build_absolute_uri` в view или `settings.FRONT_BASE_URL`).  
**Шаг 4.6.3.** Обработка ошибки SMTP: логирование; пользователю всё равно показать успех (или предупреждение — по продуктовому решению; **рекомендация**: успех + лог ошибки).

**Тест 4.6.T1.** Mock `send_mail`, assert вызван с корректным `to` = owner.email.

### 4.7. Сетка 7 дней на карточке СТО

**Шаг 4.7.1.** View partial или контекст: список дат `today .. today+6`.  
**Шаг 4.7.2.** HTMX: выбор даты подгружает список свободных слотов за день (`GET .../slots/?date=YYYY-MM-DD`).  
**Шаг 4.7.3.** Queryset слотов: фильтр по станции, дате, `slot_is_bookable`.

**Тест 4.7.T1.** На дату без слотов — пустой список.

---

## Фаза 5. Личный кабинет владельца СТО

**Шаг 5.1.1.** URL namespace `sto/` с декоратором `user_passes_test(lambda u: u.is_sto_owner)`.  
**Шаг 5.1.2.** Middleware **опционально**: проверка подписки не блокирует вход — редирект на страницу-заглушку `sto/billing-required/`.  
**Шаг 5.1.3.** Дашборд: две таблицы — брони на сегодня и на завтра: фильтр по `station.owner=request.user` и датам слота.  
**Шаг 5.1.4.** Визуальное выделение `pending`: класс CSS `table-warning` + анимация (Bootstrap `spinner-border` или CSS `animation`).  
**Шаг 5.1.5.** Кнопки POST с CSRF: Подтвердить (`pending`→`confirmed`), Отклонить (`canceled` + освободить слот), Завершить (`confirmed`→`completed`).  
**Шаг 5.1.6.** Каждое действие — отдельный POST endpoint с проверкой `booking.station.owner == request.user`.  
**Шаг 5.1.7.** Форма добавления слота: `ModelForm` для `TimeSlot` с фильтром `bay` только своей станции (queryset в `__init__`).

**Тест 5.1.T1.** Владелец чужой станции получает 404 при POST на чужой booking id.  
**Тест 5.1.T2.** Переход `confirmed`→`completed` разрешён; из `pending` в `completed` запрещён.  
**Тест 5.1.T3.** Статистика за месяц — число совпадает с количеством созданных броней (или только не canceled — зафиксировать в тесте согласно продукту).

**Шаг 5.1.8.** Заглушка оплаты: если `not station.is_visible...` или просрочка basic — рендерить шаблон без дашборда.

---

## Фаза 6. Личный кабинет клиента

**Шаг 6.1.1.** URL `cabinet/` — список броней пользователя, order by `-created_at`.  
**Шаг 6.1.2.** Отображение статусов человекочитаемо.  
**Шаг 6.1.3.** Ссылка «Оставить отзыв» если `status=completed` и нет `review` (проверка `hasattr` / `exists()`).

**Тест 6.1.T1.** Клиент видит только свои брони.

---

## Фаза 7. Отзывы

**Шаг 7.1.1.** Модель `Review` OneToOne к `Booking`.  
**Шаг 7.1.2.** Форма: рейтинг + текст; view `CreateReview` только если booking.client == user и completed и нет отзыва.  
**Шаг 7.1.3.** После создания — редирект в кабинет.

**Тест 7.1.T1.** Попытка отзыва на `pending` — 403/404.  
**Тест 7.1.T2.** Второй отзыв — IntegrityError перехвачена → сообщение.  
**Тест 7.1.T3.** Средний рейтинг на карточке обновляется (повтор теста 3.4.T3).

**Шаг 7.1.4.** XSS: экранирование текста отзыва в шаблоне (`{{ text|linebreaks }}` без `safe`).

---

## Фаза 8. Монетизация и контроль доступа к каталогу

**Шаг 8.1.1.** Убедиться, что **все** публичные queryset станций используют `visible_in_catalog()`.  
**Шаг 8.1.2.** Добавить тест регрессии: изменение `subscription_paid_until` вчера скрывает станцию из списка.  
**Шаг 8.1.3.** В админке: фильтр по плану и дате оплаты; help_text у полей.

---

## Фаза 9. Полировка безопасности и UX

**Шаг 9.1.1.** `SecurityMiddleware`, `XFrameOptionsMiddleware` — включены.  
**Шаг 9.1.2.** В `prod.py`: `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `CSRF_TRUSTED_ORIGINS`.  
**Шаг 9.1.3.** Кастомный путь админки в `urls.py` (реализовано: `secure-admin/`); убрать упоминание стандартного пути из документации.  
**Шаг 9.1.4.** Сообщения об ошибках пользователю **без** утечки stack trace.  
**Шаг 9.1.5.** Страница 404/500 шаблоны.  
**Шаг 9.1.6.** `django.contrib.messages` для флеш-сообщений после действий.

**Шаг 9.2.1.** Прогон `python manage.py check --deploy` на prod settings.  
**Шаг 9.2.2.** Прогон `ruff check` / `ruff format` по всему проекту.  
**Шаг 9.2.3.** `pytest --cov=apps` — целевое покрытие для MVP **не формализовано жёстко**, ориентир **≥60%** для `bookings`, `stations`, `users`.

---

## Фаза 10. Деплой на VPS

**Шаг 10.1.1.** Установить PostgreSQL 16, создать БД и пользователя с ограниченными правами.  
**Шаг 10.1.2.** Расширение `postgis` опционально: `CREATE EXTENSION postgis;` — для будущего, без использования в MVP.  
**Шаг 10.1.3.** Создать системного пользователя Linux `promaster`, директория `/srv/promaster`.  
**Шаг 10.1.4.** Клонировать репозиторий, venv, `pip install -r requirements/prod.txt`.  
**Шаг 10.1.5.** `collectstatic`, права на `media`.  
**Шаг 10.1.6.** Unit file `gunicorn.service`: socket или bind127.0.0.1:8000, `EnvironmentFile=/srv/promaster/.env`.  
**Шаг 10.1.7.** Nginx: `proxy_pass` к gunicorn, `client_max_body_size` для загрузки фото (5–10 МБ), статика и media.  
**Шаг 10.1.8.** Certbot Let's Encrypt, редирект HTTP→HTTPS.  
**Шаг 10.1.9.** Cron: бэкап БД `pg_dump` + ротация; команды `release_expired` / `cancel_unconfirmed`.  
**Шаг 10.1.10.** Настроить SMTP провайдера (Unisender/SendPulse/Mail.ru для домена) с SPF/DKIM.

**Тест 10.T1.** Smoke после деплоя: регистрация, активация, создание слота, бронь, письмо дошло (проверка логов).

---

## Матрица тестов (сводка по модулям)

| Модуль | Обязательные тесты |
| :-- | :-- |
| users | создание, уникальность email, активация, логин неактивного |
| stations | видимость в каталоге, фото лимит, public detail 404 для скрытых |
| bookings | транзакция брони, гонка, права владельца, истечение pending, email mock |
| reviews | только completed, один отзыв, XSS шаблон (опционально клиентский тест) |
| интеграция | полный flow в одном `pytest` (медленный тест, пометить `@pytest.mark.slow`) |

---

## Порядок выполнения (строго последовательный для соло)

1. Фазы **0–1** (каркас + приложения).  
2. Фаза **2** (пользователь и auth).  
3. Фаза **3** (СТО + каталог без слотов или со слотами пустыми).  
4. Фаза **4** (слоты + бронь + письма + сетка 7 дней).  
5. Фаза **5** (ЛК СТО).  
6. Фаза **6** (ЛК клиента).  
7. Фаза **7** (отзывы).  
8. Фаза **8** (подписка — можно частично ввести раньше в фазе 3, если тесты каталога требуют).  
9. Фазы **9–10** (хардненинг и деплой).

---

## Чеклист перед каждым коммитом (1 минута)

- [ ] `pytest` зелёный  
- [ ] нет секретов в diff  
- [ ] миграции включены  
- [ ] для новых view с формой — CSRF  
- [ ] для новых queryset с `user` — фильтрация по владельцу

---

*Документ можно дробить на задачи в трекере: каждый «Шаг X.Y.Z» = одна карточка с ссылкой на этот файл.*
