# Чат по записи: реальное время (WebSocket)

## Диагностика (корневая причина «нужна перезагрузка»)

### Критический баг сериализации исходящего события

Потребитель `ChatConsumer` рассылает сообщение в группу `chat_room_{room_id}` корректно (`group_send`). Обработчик `chat_message` ранее отдавал клиенту:

```python
await self.send_json({"type": "message", **event})
```

В `event` от канального слоя уже есть ключ `"type": "chat.message"`. При раскрытии словаря он **перезаписывал** ключ `type`, и в браузер уходило `type: "chat.message"`.

Клиент (`static/js/pages/booking-chat-ws.js`) принимает только `type === "message"`. В результате **входящие сообщения собеседника отбрасывались**, своё сообщение было видно из‑за оптимистичной отрисовки при отправке.

**Исправление:** явно формировать ответ с `type: "message"` и полями `id`, `sender_id`, `text`, `created_at` без `**event`.

### Прочие проверенные узлы

| Узел | Статус |
|------|--------|
| Маршрут `ws/chat/<booking_id>/` | Совпадает с `chat_ws_path` в шаблонах |
| Группа комнаты | `chat_room_{room.pk}` на connect и в `group_send` |
| `CHANNEL_LAYERS` | Redis (`channels_redis`) в `base.py`; для изолированных тестов — `InMemoryChannelLayer` |
| ACL | `connect` / `_can_post` проверяют клиента и владельца станции |
| Прямые чаты (station-direct, ad-direct) | Отдельные consumers; исходящий тип уже нормализуется в `type: "message"` |

### Косвенные риски

- **Два порта HTTP/WS в Docker** (`8000` / `8001`): см. `static/js/app/ws-base.js`.
- **Обрыв сокета**: добавлены переподключение и ping/pong (см. ниже).

## Поведение после исправлений

1. Оба участника подключаются к одной группе; сообщение сохраняется в БД и рассылается всем подключённым к комнате.
2. Клиент показывает статус: «Подключение…» / «Чат онлайн…» / «Переподключаемся…».
3. Каждые ~25 с отправляется `{"type":"ping"}`; сервер отвечает `{"type":"pong"}` (не учитывается в rate limit).
4. Повторная доставка одного и того же `id` не дублирует пузырь в DOM.

## Автотесты

Файл `apps/chat/tests/test_booking_chat_realtime_broadcast.py`:

- два `WebsocketCommunicator` (клиент и владелец) получают одно и то же сообщение с `type: "message"`;
- проверка ping/pong.

Запуск в Docker (с монтированием кода):

```bash
docker compose run --rm --entrypoint="" -v "$(pwd):/app" -w /app test \
  python -m pytest apps/chat/tests/test_booking_chat_realtime_broadcast.py -q
```

Локально нужен PostGIS/GDAL или `TEST_DATABASE_URL` как в CI.

## Ручная проверка «два клиента»

1. Поднять стек: `docker compose up` (веб + **asgi** на `8001`, см. compose).
2. Открыть чат по одной записи в двух профилях (клиент и СТО) — два браузера или окно инкогнито.
3. В DevTools → Network → WS убедиться, что кадры с текстом имеют `"type":"message"`.
4. Отправить сообщение с одной стороны — оно должно появиться у второй **без** F5.

## Продакшен (рекомендуется)

Один домен, Nginx: **`/ws/` → Uvicorn (ASGI)**. Пошагово: **[DEPLOY-NGINX-PRODUCTION.md](./DEPLOY-NGINX-PRODUCTION.md)**.

## ngrok / один публичный порт (WS падает, бейдж «залипает»)

Типичная схема: туннель ведёт на **Gunicorn (WSGI)**, который **не обрабатывает** WebSocket — в консоли `WebSocket connection to 'wss://…/ws/user-inbox/' failed`.

**Варианты:**

1. **Прокси на одном домене:** nginx/Caddy перед приложением: `location /ws/` → upstream **ASGI** (uvicorn/daphne), остальное → WSGI.
2. **Второй ngrok** на порт ASGI (в compose — `8001`), в `.env`:  
   `CHANNELS_WS_CLIENT_BASE_URL=wss://<второй-субдомен>.ngrok-free.dev`  
   (без пути в конце). Страница открывается с первого туннеля, сокеты — ко второму.
3. **Без рабочего WS:** фронт **опрашивает** `/api/inbox/summary/` (бейдж) и `/api/chats/<room_id>/messages/?after_id=` + POST `.../messages/send/` (чат по записи). Счётчики и переписка остаются корректными.

## Переменные окружения

- **`CHANNELS_WS_CLIENT_BASE_URL`** — опционально, полный базовый URL для WebSocket (`wss://host:port`), без пути.
- `CHANNEL_REDIS_URL` / `REDIS_URL` — для `CHANNEL_LAYERS`;
- в Docker: `WEB_PORT` / `ASGI_PORT` для раздельного WSGI/ASGI.
