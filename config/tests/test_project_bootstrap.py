"""Фаза 1.1: pytest и проверки каркаса проекта."""

import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.conf import settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.django_db
def test_database_accessible():
    from django.db import connection

    connection.ensure_connection()


def test_secret_key_not_empty():
    assert settings.SECRET_KEY


def test_installed_apps_contain_project_apps():
    names = set(settings.INSTALLED_APPS)
    assert "apps.core" in names
    assert "apps.users" in names
    assert "apps.stations" in names
    assert "apps.bookings" in names
    assert "apps.reviews" in names


def test_manage_check_dev():
    env = {**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings.dev"}
    result = subprocess.run(
        [sys.executable, "manage.py", "check", "--settings=config.settings.dev"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_manage_check_prod():
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings.prod",
        "SECRET_KEY": "test-production-secret-key-minimum-fifty-characters-long-ok",
        "ALLOWED_HOSTS": "localhost,example.com",
        "DATABASE_URL": "postgres://user:pass@127.0.0.1:5432/promaster_test",
        "CSRF_TRUSTED_ORIGINS": "https://example.com,https://www.example.com",
    }
    result = subprocess.run(
        [sys.executable, "manage.py", "check", "--settings=config.settings.prod"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_manage_check_deploy_prod():
    """Фаза 9.2.1: `manage.py check --deploy` на prod settings."""
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings.prod",
        "SECRET_KEY": "test-production-secret-key-minimum-fifty-characters-long-ok",
        "ALLOWED_HOSTS": "localhost,example.com",
        "DATABASE_URL": "postgres://user:pass@127.0.0.1:5432/promaster_test",
        "CSRF_TRUSTED_ORIGINS": "https://example.com",
    }
    result = subprocess.run(
        [
            sys.executable,
            "manage.py",
            "check",
            "--deploy",
            "--settings=config.settings.prod",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_prod_settings_secret_key_not_placeholder(monkeypatch):
    monkeypatch.setenv(
        "SECRET_KEY",
        "test-production-secret-key-minimum-fifty-characters-long-ok",
    )
    monkeypatch.setenv("ALLOWED_HOSTS", "example.com")
    monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", "https://example.com")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgres://user:pass@127.0.0.1:5432/promaster_test",
    )
    import config.settings.prod as prod_settings

    importlib.reload(prod_settings)
    assert prod_settings.SECRET_KEY != "change-me"


def test_mvp_modules_coverage_meets_threshold():
    """Фаза 9.2.3: ориентир ≥60% для bookings, stations, users (полный pytest + cov)."""
    # Этот чек нельзя запускать "pytest внутри pytest": это приводит к конфликтам по БД
    # и зависаниям в Docker/CI. Запускайте как отдельный шаг (например, в CI),
    # установив переменную окружения.
    if os.environ.get("PM_RUN_COVERAGE_CHECK", "0") != "1":
        pytest.skip("Coverage threshold check runs as separate CI step (set PM_RUN_COVERAGE_CHECK=1).")
    env = {**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings.tests"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--cov=apps.bookings",
            "--cov=apps.stations",
            "--cov=apps.users",
            "--cov-fail-under=60",
            "--cov-report=term",
            "apps",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
