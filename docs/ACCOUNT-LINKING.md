# Единый аккаунт: телефон, VK, Google

## Ключ связывания

Автоматическое объединение входов опирается на **один и тот же email** (без учёта регистра). Реализация: `TachkiSocialAccountAdapter` (`save_user`, `pre_social_login`) и путь VK One Tap (`apps/users/vkid.py` → `save_user`).

## Регистрация водителя по форме

Для роли **«Водитель»** поле **email обязательно** (`RoleRegisterForm`): без него соцсети не смогут сопоставить аккаунт с уже существующим пользователем по телефону.

## Соцвход без email от провайдера

Если провайдер не передал email, при включённых `SOCIALACCOUNT_EMAIL_REQUIRED` и `ACCOUNT_SIGNUP_FIELDS = ["email*"]` django-allauth перенаправляет на **`/oauth/signup/`** — шаблон [`templates/socialaccount/signup.html`](../templates/socialaccount/signup.html). Пользователь вводит email; дальше срабатывает та же логика `save_user` (в т.ч. привязка к существующему пользователю при совпадении email).

### Форма без «тупика» при занятом email

Стандартный `SignupForm` из allauth помечает уже существующий в БД email как ошибку **до** вызова `save_user`. У нас слияние делается в `TachkiSocialAccountAdapter.save_user` через `sociallogin.connect(existing)`. Поэтому подключена кастомная форма [`apps/users/social_signup_form.py`](../apps/users/social_signup_form.py) (`SOCIALACCOUNT_FORMS["signup"]`): если такой `User.email` уже есть (Google, регистрация по телефону и т.д.), поле проходит валидацию и выполняется привязка VK к этому аккаунту.

## Настройки (см. `config/settings/base.py`)

- `ACCOUNT_SIGNUP_FIELDS = ["email*"]` — минимальная форма дозаполнения email для соцрегистрации.
- `SOCIALACCOUNT_EMAIL_REQUIRED = True` — без email от провайдера показывается экран ввода.
- `SOCIALACCOUNT_FORMS["signup"]` → `TachkiSocialSignupForm` — см. выше.

## Ограничения

Разные осознанно указанные email в соцсети и на сайте дают **разные** учётные записи; это ожидаемо с точки зрения безопасности.
