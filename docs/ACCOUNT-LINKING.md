# Единый аккаунт: телефон, VK, Google

## Ключ связывания

Автоматическое объединение входов опирается на **один и тот же email** (без учёта регистра). Реализация: `TachkiSocialAccountAdapter` (`save_user`, `pre_social_login`) и путь VK One Tap (`apps/users/vkid.py` → `save_user`).

## Регистрация водителя по форме

Для роли **«Водитель»** поле **email обязательно** (`RoleRegisterForm`): без него соцсети не смогут сопоставить аккаунт с уже существующим пользователем по телефону.

## Соцвход без email от провайдера

Если провайдер не передал email, при включённых `SOCIALACCOUNT_EMAIL_REQUIRED` и `ACCOUNT_SIGNUP_FIELDS = ["email*"]` django-allauth перенаправляет на **`/oauth/signup/`** — шаблон [`templates/socialaccount/signup.html`](../templates/socialaccount/signup.html). Пользователь вводит email; дальше срабатывает та же логика `save_user` (в т.ч. привязка к существующему пользователю при совпадении email).

## Настройки (см. `config/settings/base.py`)

- `ACCOUNT_SIGNUP_FIELDS = ["email*"]` — минимальная форма дозаполнения email для соцрегистрации.
- `SOCIALACCOUNT_EMAIL_REQUIRED = True` — без email от провайдера показывается экран ввода.

## Ограничения

Разные осознанно указанные email в соцсети и на сайте дают **разные** учётные записи; это ожидаемо с точки зрения безопасности.
