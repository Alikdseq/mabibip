# WebRTC-звонки (LiveKit + Channels) — МаБибип

## Включение

По умолчанию звонки выключены. Чтобы включить:

- `CALLS_ENABLED=1`
- настроить LiveKit (URL + ключи)

## Переменные окружения

- `CALLS_ENABLED`: `1/0` — включить/выключить фичу.
- `LIVEKIT_URL`: публичный URL LiveKit, например `https://livekit.example.com` (или `http://...` для локального стенда).
- `LIVEKIT_API_KEY`: ключ доступа.
- `LIVEKIT_API_SECRET`: секрет (подпись токенов).
- `CALLS_RING_TIMEOUT_SEC`: таймаут ожидания ответа, по умолчанию `30`.
- `CALLS_TOKEN_TTL_SEC`: TTL токена подключения, по умолчанию `300`.

## Как работает

- **Сигнализация**: WebSocket `/ws/calls/` (Channels, session auth).
- **API**:
  - `POST /api/calls/initiate/` → создаёт `Call`, выдаёт токен звонящему, отправляет `call.incoming` получателю.
  - `POST /api/calls/action/` → `accept/decline/end`.
- **Медиа**: LiveKit (аудио WebRTC). Клиент подключается через LiveKit JS SDK по выданному токену.

## Деплой LiveKit (self-hosted, Docker) — шаблон

Пример (ориентир, финальные порты/конфиг зависят от вашей сети и reverse-proxy):

```yaml
version: '3'
services:
  livekit:
    image: livekit/livekit-server:latest
    ports:
      - 7880:7880
      - 7881:7881/udp
    environment:
      LIVEKIT_KEYS: "devkey: secret"
      LIVEKIT_CONFIG: |
        port: 7880
        rtc:
          udp_port: 7881
          stun_servers: ["stun:stun.l.google.com:19302"]
          use_external_ip: true
```

Минимально нужно:\n
- публичный домен/сертификат (желательно HTTPS)\n
- открытый UDP-порт для WebRTC (или отдельный TCP-only режим — хуже по качеству)\n
- корректный reverse-proxy для `LIVEKIT_URL`\n

## Диагностика

- Если `LIVEKIT_URL/LIVEKIT_API_KEY/LIVEKIT_API_SECRET` не заданы — `POST /api/calls/initiate/` вернёт `503`.
- Если звонки выключены — API вернёт `403`, а UI-кнопки не показываются.

