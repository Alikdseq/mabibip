# Runbook: словарь поисковых фраз (фаза D1)

Цель: на проде и стендах актуальны записи `ServiceSearchPhrase`, согласованные с `списокзапросов.txt` в корне репозитория.

## Команды

| Команда | Назначение |
|--------|------------|
| `python manage.py import_search_dictionary` | Полный импорт из файла по умолчанию (`BASE_DIR/списокзапросов.txt`). Обновляет вес и текст существующих связей; создаёт категории по имени услуги, если их ещё нет. |
| `python manage.py import_search_dictionary --file /path/to/file.txt` | Импорт из другого файла (UTF-8, строки вида `фраза → услуга1 / услуга2`). |
| `python manage.py import_search_dictionary --dry-run` | Разбор и счётчики без записи в БД. |
| `python manage.py import_search_dictionary --truncate` | Удалить все `ServiceSearchPhrase`, затем импорт (осторожно на проде: обсудить окно простоя). |
| `python manage.py ensure_search_phrases` | Если таблица фраз **пуста**, один раз вызывает `import_search_dictionary` (удобно для Docker/нового стенда). |

## Docker

```text
docker compose run --rm --entrypoint "" web python manage.py import_search_dictionary --dry-run
docker compose run --rm --entrypoint "" web python manage.py import_search_dictionary
```

## CI / прод

- После изменения `списокзапросов.txt` в релизе: выполнить `import_search_dictionary` на целевом окружении (или зафиксировать в pipeline шаг «миграция данных» после деплоя).
- Полная перезаливка (`--truncate`) — только по согласованной процедуре, чтобы не потерять ручные правки в БД, если такие ведутся.

## Проверка

- В админке или через ORM: выборочно сравнить несколько фраз из файла с записями в `ServiceSearchPhrase`.
- Смок-тест UI: подсказки поиска по симптомам из словаря ведут на ожидаемые услуги/каталог.
