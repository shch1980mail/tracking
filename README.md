# ТПК — Отслеживание (MVP-ядро)
Локально: `python -m venv venv && pip install -r requirements.txt && uvicorn main:app --reload`
Импорт: `python scripts/import_xlsx.py "data/Отгрузки 2026.xlsx"`. Тесты: `pytest`.
Layero: задать DATABASE_URL (Neon/Aiven), ADMIN_LOGIN, ADMIN_PASSWORD; без DATABASE_URL — SQLite.
Админ-API (Basic Auth): POST /admin/import, POST /admin/shipments, DELETE /admin/shipments/{id}?restore=; Swagger: /docs.
Решения: нестатусные тексты в колонке S («прошел», «билет…») → notes; пустой статус → planned; статус «Прогноз*» → in_transit.

## Этап 2: импорт
UI: /admin/import (preview → маппинг → импорт → история/откат). CLI: `python scripts/import_xlsx.py [файл] [--sheet all|имя] [--dry-run] [--mapping m.json]`.
Один батч на лист. Основной лист читается по позиции колонок (маппинг фиксирован), остальные — по заголовкам; маппинг хранится в settings.
Откат не затирает правки, сделанные после импорта; созданные записи, изменённые позже, остаются (kept).
«ПланНеделя» ставит status=planned (кроме delivered). Новые таблицы создаются create_all; на старой SQLite удалите data/tracking.db (Alembic — этап 3).

## Этап 3 (частично): авторизация, аудит, CSV, rate-limit
Вход: /admin/login (JWT-cookie: access 15 мин, refresh 7 дней, POST /admin/refresh) или Basic Auth (env-админ или пользователь из БД). Роли: admin — всё; manager — заказы/импорт/GPS; viewer — только GET.
Пользователи (JSON API, admin): GET/POST /admin/users, PATCH /admin/users/{id}. Аудит: GET /admin/audit?action=&user=&frm=&to=. Массовая смена статуса: POST /admin/shipments/bulk.
CSV: /api/shipments.csv?tab=&q= (разделитель «;», BOM). Rate-limit: 60/мин публичные, 600/мин с авторизацией, RATE_LIMIT_ENABLED=false отключает; задайте SECRET_KEY в env.
Alembic пока нет: схема создаётся create_all (на старой SQLite удалите data/tracking.db).

## Этап 3 (завершение): Alembic и админка
Миграции: `alembic upgrade head` (миграция `init_full`, 11 таблиц; URL берётся из `DATABASE_URL`/SQLite). Приложение при старте проверяет `alembic_version`: если миграций нет — пишет `alembic_not_applied` и делает `create_all` (fallback для SQLite на Layero Free). `layero.json` оставлен с одним `uvicorn` — поддержка `alembic upgrade head && uvicorn …` в startCommand Layero не проверялась; на Free работает fallback, для Postgres выполните `alembic upgrade head` с локальной машины с боевым `DATABASE_URL`.
SQLite: `rm data/tracking.db && alembic upgrade head`. Postgres со старой схемой: добавьте колонки этапа 1 вручную и `alembic stamp head`, либо `alembic upgrade head` на пустой БД.
Админка: /admin, /admin/shipments (inline-правка двойным кликом, массовые действия, создание, soft-delete), /admin/gps-links, /admin/users, /admin/audit, /admin/settings, /admin/import. Страницы Users/Audit отдают HTML при `Accept: text/html`, иначе JSON.
Настройки из UI сохраняются в `settings.app_settings` и применяются на лету (интервал GPS — после перезапуска).
Ограничения: IP для rate-limit берётся из X-Forwarded-For (можно подделать), счётчик не общий между воркерами.
**Проверка в браузере НЕ выполнялась** (в среде разработки нет браузера): страницы покрыты только тестами рендеринга/API. Не проверено вручную: вёрстка на 375px, drag&drop на /admin/import, карта, bottom-sheet фильтров (не реализован), прогон реального «Отгрузки 2026.xlsx».
