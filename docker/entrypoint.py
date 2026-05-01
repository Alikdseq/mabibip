"""Точка входа контейнера: миграции, статика, затем exec основной команды (Gunicorn).

Обходит проблему Windows CRLF у shell-скриптов (`exec ... no such file or directory`).
"""

from __future__ import annotations

import os
import sys
from subprocess import run


def main() -> None:
    os.chdir("/app")
    # Default settings for normal container runtime.
    # For test runs (`docker compose run web pytest ...`) we want pytest-django to control
    # the settings module (via pytest.ini) and use the same DB URL as Docker.
    argv = sys.argv[1:]
    is_pytest = bool(argv) and (
        argv[0] == "pytest"
        or (argv[:2] == ["python", "-m"] and len(argv) > 2 and argv[2] == "pytest")
    )
    if is_pytest:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.tests")
        # Force tests settings to pick PostgreSQL in Docker.
        os.environ.setdefault("TEST_DATABASE_URL", os.environ.get("DATABASE_URL", ""))
    else:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.docker")
    exe = sys.executable
    run([exe, "manage.py", "migrate", "--noinput"], check=True)
    # Словарь «живых» запросов → услуги (если БД пустая после миграций).
    run([exe, "manage.py", "ensure_search_phrases"], check=True)
    # F0: юридические документы должны быть доступны для регистрации и кабинета СТО.
    # Команда идемпотентна: update_or_create по (key, version_label).
    run(
        [
            exe,
            "manage.py",
            "seed_legal_documents",
            "--version-label",
            os.environ.get("LEGAL_DOCS_VERSION", "1.0"),
            "--effective-now",
        ],
        check=True,
    )
    run([exe, "manage.py", "collectstatic", "--noinput"], check=True)
    if len(sys.argv) < 2:
        sys.exit("entrypoint: укажите команду после образа (например gunicorn)")
    argv = sys.argv[1:]
    if argv and argv[0] == "gunicorn":
        # F9.1.4: workers = (2*CPU)+1 for sync, overridable via WEB_CONCURRENCY/GUNICORN_WORKERS.
        cpu = os.cpu_count() or 1
        desired = int(
            os.environ.get("GUNICORN_WORKERS")
            or os.environ.get("WEB_CONCURRENCY")
            or ((2 * cpu) + 1)
        )
        if "--workers" in argv:
            i = argv.index("--workers")
            if i + 1 < len(argv):
                argv[i + 1] = str(desired)
        else:
            argv[1:1] = ["--workers", str(desired)]
    try:
        os.execvp(argv[0], argv)
    except FileNotFoundError:
        sys.stderr.write(
            f"entrypoint: команда не найдена: {argv[0]!r}\n"
            "Подсказка: для утилит Python используйте `python -m <module>` "
            "или убедитесь, что зависимость установлена в образе.\n"
        )
        raise


if __name__ == "__main__":
    main()
