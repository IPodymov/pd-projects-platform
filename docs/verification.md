# Выполненная проверка

Проверено локально 3 октября 2026 года. Удалённые Railway/Vercel и настоящая production БД не использовались.

## Автоматические проверки

- `make test`: 68 тестов, успешны; 5 конкурентных теста явно пропущены на SQLite.
- PostgreSQL: `docker compose exec -T -e DJANGO_SETTINGS_MODULE=config.settings.test -e TEST_DATABASE_URL=postgresql://platform:platform@postgres:5432/platform api python manage.py test --noinput`: все 68 успешны. Django создал и удалил отдельную `test_platform`.
- Самостоятельная запись: ученик видит только собственные членства; чужое членство возвращает 404, подмена класса при записи отвергается, повторная запись возвращает существующую запись.
- Проверяются область нескольких классов преподавателя, изоляция учреждений/классов/проектов; приглашения с кодом на нужную почту, отзыв после исправления адреса, истечение, повторное и одновременное принятие; повторный импорт, конфликты, XLSX-содержимое/права/formula safety; расписание/уведомления/пересечения/DST/исключения; партнёрская видимость и конкурентные последние места; реальные действия CRM и принятый прогресс.
- Seed: неизвестные модели/поля/технические ключи, запрещённые и demo-материалы, закрытые зависимости, checksum, dry-run, повторный импорт, эквивалентные timezone deadline, ручные конфликты и полный rollback при ошибке сохранения.
- `common.test_journey` проходит десять сквозных этапов через канонический /api/v1/ и реальную тестовую БД. Внутри этого теста email-провайдер заменён тестовым capture, а не внешним SMTP. Реальный локальный SMTP проверен отдельно ниже.
- `make check`: Django system checks без ошибок, `makemigrations --check --dry-run` — изменений нет, Compose config корректен, Vue TypeScript проходит.
- `make schema`: drf-spectacular validate/fail-on-warn и генерация openapi-typescript успешны.
- `npm run build`: общий клиент, vue-tsc и production Vite bundle успешны; `npm run lint -w apps/web` успешен. Ранее выполненный `npm audit` сообщил 0 уязвимостей; повторная проверка по сети в этом проходе недоступна.
- Ruff проверки Python успешны. Установка инструмента отдельно: `.venv/bin/pip install -r apps/backend/requirements-dev.lock`, затем `make lint-python`.
- `make production-check`: Django `check --deploy --fail-level WARNING` успешен с синтетической конфигурацией без подключения к указанной synthetic БД.

## Реальные локальные сервисы

Compose действительно собран и запущен, миграции применены. PostgreSQL, Redis, приватный SeaweedFS S3, Mailpit, API, Celery worker/beat и Vue работают локально. `make smoke` требует явно загруженных demo-данных и DEBUG; проверяет загрузку/скачивание из S3, checksum, текстовый diff, восстановление, DOCX/PPTX и фоновый comparison в реальном worker и email через SMTP/Mailpit. Временные документы и приглашение удаляются после проверки. Это не команда для production.

Production Docker image собран с collectstatic: 157 файлов, 453 post-processed. Отдельный временный контейнер запущен с production settings, синтетическими секретами, локальными PostgreSQL/Redis и назначенным PORT=8099. `/health/ready/` вернул ready; `/static/admin/css/base.css` получен через WhiteNoise с HTTPS proxy header. Контейнер завершён SIGTERM. Это локальная проверка Gunicorn/PORT/static, а не успешный hosted deploy.

`seed_validate` проверил текущий catalog.json: 3 записи. CLI dry-run на локальной development БД сообщил skipped для всех трёх тем; применение, идемпотентность и rollback отдельно проверены тестами.

## Браузер

Google Chrome через agent-browser: гостевой экран, вход преподавателя, обзор с фактическими данными, класс/форма импорта, CRM и фильтры, доступный проект с заданиями/версированием, расписание, пустой каталог мастер-классов. Проверены реальные 404 и ошибка с повтором. Loading проверен введённой задержкой fetch 2 секунды, затем оригинальный fetch восстановлен; данные не подменялись.

Кабинет учащегося дополнительно проверен в той же браузерной сессии после реального login API: CRM-навигация отсутствует, свой проект доступен, отправка работы видна, управление заданиями/проверками скрыто. Преподаватель видит расписание без кнопки изменения; месячная сетка начинается с понедельника.

Desktop 1440×960 и mobile 390×844: визуально просмотрены обзор/CRM/расписание/проект. Для CRM и проекта scrollWidth=390, горизонтального переполнения страницы нет. Таблицы прокручиваются внутри контейнера. JavaScript errors и Vite overlay отсутствуют на нормальных сценариях. Это smoke-проверка основных страниц, не полный браузерный E2E всех ролей и всех бизнес-сценариев.

## Расширенные сценарии, проверенные 3 октября 2026

- Course draft → publish → idempotent enrollment → draft → send → revision → corrected send → accepted/completed; история 2 проверок, черновик не создаёт activity. Project submission chain и immutable reviews.
- Outbox rollback, broker failure after commit, retry/backoff, idempotent handler/event; webhook подпись, delivery conflict/dedup; stale SHA отвергает учебную проверку, PR остаётся open; старая source_updated_at не возвращает предыдущий head.
- v1 428 без If-Match, 409 stale_revision, pagination; revoked TeachingAssignment скрывает класс, перевод сохраняет старое членство. Перенос времени серии по DST с исключением и rollback всего переноса при пересечении.
- Office DOCX paragraph/table extraction и фоновый diff; private/archive approved materials не экспортируются в seed; конкурсный lifecycle и snapshots; возрастное ограничение/отмена группы/notification dedup/редактирование посещаемости.
- На PostgreSQL пять concurrency tests: приглашение, последнее место, idempotent enrollment, одна immutable review при двух решениях, линейная цепочка document versions.
- В реальном Chrome пройден весь цикл курса двумя demo-аккаунтами: сохранение черновика, отправка, замечание, исправленная отправка, принятие. Таблица показала completed/100%, CRM — 2 отправки/1 accepted/1 учебно активный. Эти записи остаются только в явной local demo БД.
- В Chrome куратор создал задание и опубликовал новый local demo курс; ученик самостоятельно записался из своего класса и получил форму отправки работы. Публикация пустого курса была отклонена сервером с понятной ошибкой.
- Новые pages Project/Git, Classes/assignments, Workshops/subscriptions и Materials/Competition загрузились без JS errors. Mobile Classes 390×844: screenshot просмотрен, scrollWidth=390. Не заявляется браузерный E2E каждой ветки организатора/администратора.

## Ограничения проверки

Не проверены внешние GitHub/GitVerse токены, hosted SMTP/S3, Railway pre-deploy/health на платформе, Vercel preview routing, DNS/TLS/cookies собственных доменов. HTTP GitHub adapter проверяется mock-транспортом, а не живым API. Реальный worker extraction и comparison проверены для DOCX и PPTX командой smoke_services. Pinterest-изображения недоступны и не изучались. Полный список оставшегося — [status.md](status.md).

## Проверка после рефакторинга 4 октября 2026

Все 68 тестов прошли на PostgreSQL; SQLite — 68, из них 5 concurrency явно skipped. Добавлена проверка, что отзыв назначения преподавателя прекращает уведомления о работах класса даже при действующем назначении другого класса. Vue build/type-check/lint, Ruff, Django checks, отсутствие новых миграций, Compose config и production check прошли.

В Chrome проверен кабинет курса и переход в расписание. Обе ветки API-клиента передают CSRF и If-Match; запрет преподавательской операции ученику возвращает 403. Проверены отказ и подтверждение ухода с несохранённой формой: значение не сохранялось в БД. Ответ window.confirm управлялся автоматизацией для двух веток, затем оригинальная функция восстановлена. API-ответы и данные не подменялись. На странице расписания Vite overlay отсутствует.

## Demo и единый запуск 4 октября 2026

Расширены development fixtures и добавлен `npm run dev` / `make dev`. Проверен синтаксис bash, Compose configuration и сборка образов. Этапы запуска выполнены локально: `docker compose up --build --detach --wait`, migrate, demo_data. Прямой вызов всей npm-обёртки в sandbox не имел доступа к Docker socket; те же Docker-команды выполнены отдельно. Все сервисы подняты; frontend HTTP 200, API readiness ready.

70 тестов успешны на PostgreSQL; SQLite — 70 с 5 concurrency skipped. Проверены отказ demo при DEBUG=False, идемпотентность, сохранение паролей/результатов/приглашений и явный сброс только demo-паролей. Повторный demo_data в работающем окружении завершился без новых паролей. Реальный HTTP login demo-student2 через Vite proxy с session cookies/CSRF успешен; доступны курсы, собственный класс, 2 занятия, 2 мастер-класса и принятая работа. Данные для CRM относятся к демонстрационным пользователям.
