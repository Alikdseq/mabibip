## Цели и пороги (зафиксировать перед прогоном)

- **Окружение**: (локально docker / staging / prod)
- **Версия**: (git sha / tag)
- **Профиль воркеров**:
  - web (gunicorn workers): …
  - asgi (uvicorn workers): …
- **Нагрузка**:
  - users: …
  - spawn rate: …
  - duration: …

### Пороги успеха (пример)

- **Ошибки**: 5xx < 0.5%, timeouts < 0.1%
- **Latency p95**:
  - `/sto/` <= 600ms
  - `/api/stations/nearby/` <= 700ms
  - booking submit <= 900ms
- **Latency p99**: +50–80% к p95 (зафиксировать)

## Результаты

### Сводка

- **RPS**: …
- **Ошибки**: …
- **CPU/RAM**: …
- **DB**: connections / slow queries …

### Latency (p50/p95/p99)

| Endpoint | p50 | p95 | p99 | errors |
|---|---:|---:|---:|---:|
| `/sto/` | | | | |
| `/api/stations/nearby/` | | | | |
| booking | | | | |
| ws chat | | | | |

## Выводы и действия

- …

