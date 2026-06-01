# Индексация Google и другие поисковики

Chrome, Safari и Firefox **не индексируют** сайты — только Google, Яндекс, Bing.

## Код на сервере

1. `SITE_BASE_URL=https://ваш-домен` (HTTPS, без слэша в конце).
2. `GOOGLE_SITE_VERIFICATION` — код из Google Search Console → meta-тег в `base.html`.
3. Проверить https://ваш-домен/robots.txt — `Allow: /`, строка `Sitemap:`.
4. Проверить https://ваш-домен/sitemap.xml.

## Google Search Console

1. Добавить ресурс с префиксом URL.
2. Подтвердить владение (meta-тег или DNS).
3. Sitemaps → добавить `https://ваш-домен/sitemap.xml`.
4. URL Inspection → запросить индексацию главной и новых разделов (`/pomoshch/`, `/problemy/`, `/instruktory/`).

## Яндекс.Вебмастер

См. [webmaster-gsc-f1.md](webmaster-gsc-f1.md) — не отключать.
