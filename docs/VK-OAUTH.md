# Вход и регистрация через VK (django-allauth + VK ID)

В проекте уже подключён провайдер **`allauth.socialaccount.providers.vk`**. Достаточно задать переменные окружения и зарегистрировать redirect URI в кабинете VK.

См. также **[ACCOUNT-LINKING.md](ACCOUNT-LINKING.md)** — единый аккаунт по email, обязательный email для водителя, экран дозаполнения email при соцвходе.

## 1. Переменные окружения

В **`.env.prod`** (или `.env` для Docker) добавьте:

```dotenv
VK_CLIENT_ID=<числовой App ID из кабинета VK>
VK_CLIENT_SECRET=<защищённый ключ приложения>
```

Секрет **не** коммитить в репозиторий.

После изменения env перезапустите веб-процесс:

```bash
docker compose --env-file .env.prod up -d --build
# или
docker compose --env-file .env.prod restart web
```

## 2. Redirect URI в кабинете VK

Django-allauth обслуживает VK по префиксу **`/oauth/`** (см. `config/urls.py`).

Укажите в настройках приложения VK **основной** callback:

```text
https://mabibip.ru/oauth/vk/login/callback/
```

Если в кабинете VK ID (Low-code) уже указан путь из их примера:

```text
https://mabibip.ru/accounts/vk/login/callback/
```

— оставьте его: в проекте добавлен **HTTP-редирект** на allauth (`apps.users.views.vk_oauth_callback_alias`), запросы с query-параметрами передаются дальше на `/oauth/vk/login/callback/`.

## 3. Кнопки и виджет в интерфейсе

Если заданы `VK_CLIENT_ID` и `VK_CLIENT_SECRET`, на **«Вход»** и **«Регистрация»** (роль «Водитель») показывается **виджет VK ID One Tap**; отдельная текстовая кнопка allauth для VK при этом скрыта (остаётся Google/Apple и вход по телефону).

Не дублируйте приложение VK в админке **Social applications**, если уже задаёте ключи через **env** и `SOCIALACCOUNT_PROVIDERS` — иначе возможен конфликт дубликатов (см. [документацию allauth](https://docs.allauth.org/en/latest/socialaccount/provider_configuration.html)).

## 4. Виджет VK ID SDK (One Tap / Low-code)

На страницах **«Вход»** и **«Регистрация»** (роль «Водитель») подключается виджет **`@vkid/sdk`** (UMD с `unpkg`), `VKID.OneTap` и `VKID.Auth.exchangeCode`, как в примере VK.

После успешного `exchangeCode` фронт отправляет **`access_token`** на **`POST /accounts/api/vkid/session/`** (JSON: `access_token`, `process`: `login` или `signup`). Бэкенд запрашивает профиль у VK ID (**`POST https://id.vk.ru/oauth2/user_info`**) с `client_id` и `access_token`, создаёт/обновляет `SocialAccount` (провайдер `vk`) и выполняет вход через `TachkiSocialAccountAdapter` (те же правила email и существующего аккаунта для `login`).

**Redirect URI** в `VKID.Config.init` должен **побайтно** совпадать с одним из URI в кабинете VK (схема `https`, хост с `www` или без — как у пользователей на сайте).

По умолчанию в шаблон подставляется **`request.build_absolute_uri('/accounts/vk/login/callback/')`** (если не задан `VK_ID_REDIRECT_URI`): так `redirect_uri` совпадает с тем, с какого хоста открыта страница входа. Если в `.env` указан **`SITE_BASE_URL`**, он используется только как запасной вариант, когда построить URL из запроса нельзя.

Явная настройка при расхождениях прокси или домена: **`VK_ID_REDIRECT_URI`** в окружении — полный URL, **точно** как в кабинете VK, например `https://mabibip.ru/accounts/vk/login/callback/`.

Ошибка **`redirect_uri is missing or invalid`** почти всегда означает: в кабинете VK нет этого же URI, пустой `SITE_BASE_URL` и неверный `Host` у запроса, или в виджет ушёл `http://` вместо `https://` (за прокси включите `SECURE_PROXY_SSL_HEADER` или задайте `VK_ID_REDIRECT_URI` с `https`).

Если виджет не нужен, можно отключить только env-ключи VK; при включённом VK кнопка «Войти по ссылке allauth» скрыта, остаётся One Tap + при необходимости Google/Apple.

### CSP

При `CSP_ENABLED=1` в `prod` добавлены **`frame-src`** для iframe виджета VK и уже настроенные `script-src` / `connect-src` для `unpkg` и хостов VK. Для UMD VK ID SDK по умолчанию добавляется **`'unsafe-eval'`** в `script-src` (иначе консоль: CSP blocks eval). Отключить: **`CSP_SCRIPT_ALLOW_UNSAFE_EVAL=0`**.

## 5. Ограничения входа `process=login`

В `TachkiSocialAccountAdapter.is_open_for_signup` для **`process=login`** требуется **email** в профиле соцсети и существующий пользователь с таким email. Для VK включён scope **`email`** в `SOCIALACCOUNT_PROVIDERS`; пользователь должен разрешить доступ к email при авторизации.

## 6. CSP (опционально)

При `CSP_ENABLED=1` в `config/settings/prod.py` в allowlist добавлены хосты VK для скриптов, `connect-src` и **`frame-src`** (iframe виджета One Tap). См. раздел «CSP» выше про **`unsafe-eval`** и переменную **`CSP_SCRIPT_ALLOW_UNSAFE_EVAL`**.
