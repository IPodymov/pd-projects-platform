# Инженеры будущего

Стартовый монорепозиторий образовательной платформы: Vue 3 + TypeScript + Vite + Router + Pinia + PrimeVue, Django + DRF, PostgreSQL, Redis/Celery и приватное S3. Модульный монолит, API и worker используют один backend. Это работающая первая итерация, не полная реализация всех расширенных требований; точная граница — [docs/status.md](docs/status.md).

## Запуск для тестирования продукта

С запущенным Docker Desktop выполните из корня:

```sh
npm run dev
# Или эквивалентно:
make dev
```

Требуется Docker Compose v2 и Python 3 для подготовки локального `.env`; установка Python/npm зависимостей на хост для этого запуска не нужна. Команда создаёт `.env` из примера, генерирует ключ шифрования, собирает и поднимает frontend/backend и вспомогательные сервисы, ждёт готовности, применяет миграции и явно загружает demo. Проверяет development settings и локальную Compose БД; внешняя БД для этого запуска запрещена. Сервисы продолжают работать после завершения команды.

- Интерфейс: http://localhost:5173
- API: http://localhost:8000/api/docs/
- Письма приглашений и коды: http://localhost:8025
- Логи: `npm run dev:logs`; остановка с сохранением данных: `npm run dev:stop`.
- Только frontend вне Docker: `npm run dev:web` (установленные npm зависимости и локальный API обязательны).

Demo содержит школу, вуз, два класса одного преподавателя, трёх учеников, проекты/этапы/задания, принятую курсовую работу с реальной историей/активностью, онлайн/очные занятия, приглашённого ученика, конкурс и два мастер-класса, включая партнёрский на два места для проверки очереди.

Пример CSV для импорта: [student-import.csv](apps/backend/development-fixtures/student-import.csv). Его можно загрузить в выбранный demo-класс через предварительный просмотр.

Аккаунты: `platform@example.test` (платформа), `admin@example.test` (школа), `curator@example.test`, `teacher@example.test`, `student@example.test`, `student2@example.test`, `student3@example.test`, `organizer@example.test` (вуз). Новые случайные пароли выводятся при первой загрузке. Если пароль потерян, `make demo-passwords` явно перевыпускает только demo-пароли и выводит новые. Повторный `npm run dev` не сбрасывает пароли, результаты, записи, сроки или решения. Даты отсчитываются от первой загрузки. Ссылки example.test в занятиях демонстрационные, реальные видеоконференции не создаются.

Demo предназначено только для development, не относится к production seed и не запускается обычным `make up` или при deployment. CRM показывает сохранённые demo-действия, это не реальные показатели пользователей.

## Быстрый запуск

Требования: Docker Engine/Compose v2; для команд вне Docker Python 3.14 и Node 24.12+.

```sh
cp .env.example .env
make setup
make key
# Вставьте полученный ключ в INVITATION_ENCRYPTION_KEY в .env.
make up
make migrate
make superuser
```

Откройте http://localhost:5173, Admin http://localhost:8000/admin/, OpenAPI http://localhost:8000/api/docs/, перехватчик писем http://localhost:8025. Локальный S3 — SeaweedFS 4.48 на http://localhost:8333. PostgreSQL доступен с хоста на 15432, Redis на 16379; внутри Docker используются postgres:5432 и redis:6379. Порты выбраны отдельно от обычных локальных сервисов. При необходимости измените публикацию портов и WEB_URL/CSRF origins вместе.

Миграции запускаются отдельно. При первоначальном старте сначала выполните `make migrate`, затем пользуйтесь интерфейсом. Сервисы не загружают demo автоматически. API/web — hot reload; API, worker и beat читают backend из bind mount. После изменения кода фоновых задач перезапустите `docker compose restart worker beat`: Celery worker не поддерживает безопасный autoreload. PostgreSQL, Redis и S3 сохраняются в volumes. `make down` сохраняет данные; `docker compose down -v` удаляет их.

Только по желанию, локальная демонстрация:

```sh
make demo
```

Команда создаёт явно помеченные demo-записи и выводит новые случайные пароли только для development. Повторный запуск не меняет пароли. Demo никогда не запускается в production. Учётные записи: teacher@example.test, curator@example.test, student@example.test, admin@example.test. Администратор учреждения и superuser — разные роли; demo admin не является superuser.

## Основной сценарий

1. Superuser создаёт учреждение и классы через Vue или Admin. Приглашает преподавателя с ролью, учреждением и классом.
2. Получатель открывает ссылку из Mailpit, запрашивает код на указанную почту, задаёт пароль и принимает приглашение. Для существующего аккаунта сначала требуется вход; его пароль не меняется.
3. Преподаватель открывает «Классы и приглашения», скачивает CSV-шаблон, загружает CSV/XLSX, проверяет строки и явно подтверждает импорт. До регистрации можно исправить почту — старая ссылка отзывается. XLSX-экспорт выдаёт действующие ссылки.
4. Учащийся подтверждает почту и получает свои классы, занятия и проекты. Преподаватель создаёт проект, добавляет участников, назначает задания; учащийся отправляет работу, преподаватель принимает или отправляет на доработку.
5. У проекта можно создать документ, загрузить неизменяемые версии, скачать, сравнить текст или восстановить старую версию как новую.
6. Администратор/куратор создаёт расписание, меняет формат. Получатели получают уведомление внутри платформы и email через Celery. Есть неделя, месяц и список.
7. Партнёрство школы с вузом утверждает superuser. Организатор создаёт мастер-класс через API/Admin, публикует через API. Подписавшиеся сотрудники школы получают уведомление. В Vue есть индивидуальная и групповая запись и отмена; последний слот защищён транзакционной блокировкой.
8. CRM считает реальные учебные действия и принятые задания; фильтры ограничены серверной областью ответственности.

## Команды разработки

```sh
make check           # Django, migration drift, Compose, TypeScript
make test            # SQLite, отдельная временная БД; concurrency-тесты пропускаются
make test-postgres   # PostgreSQL, отдельная test_platform; включая конкурентные запросы
make build           # общий API-клиент, типы, production Vite bundle
make schema          # drf-spectacular -> OpenAPI -> openapi-typescript
npm run lint -w apps/web
make production-check # synthetic configuration only
make smoke            # явная проверка реальных локальных S3/Celery/Mailpit, после make demo
# Необязательные инструменты проверки Python:
.venv/bin/pip install -r apps/backend/requirements-dev.lock
make lint-python
```

Генераторы действительно выполнялись: `npm create vue` / официальный `create-vue`, `django-admin startproject config apps/backend`, `manage.py startapp <module>`, `manage.py makemigrations`, `manage.py migrate`. Первый запуск Vue выполнен установленным официальным `create-vue` CLI, эквивалентно `npm create vue@3.24.0 apps/web -- --typescript --router --pinia --eslint --prettier --default` (для вложенного пути генератор может спросить package name). Python-зависимости зафиксированы `pip freeze` в requirements.lock, npm — в package-lock.json. Schema/client не написаны вручную.

Для нативного backend без Compose приложение допускает SQLite в development; задайте Redis, S3 и почту отдельно. `manage.py` не читает .env автоматически: Compose передаёт его как environment. Для реального локального сценария рекомендуется Compose.

## Production seed

Разделён с development demo; файл `apps/backend/production-seeds/catalog.json` содержит только три технические темы. Экспорт не подключается к production.

```sh
# Подготовка и экспорт в локальной среде
make seed-export
# Для явно утверждённых опубликованных материалов, исключая demo:
docker compose exec api python manage.py seed_export /app/production-seeds/catalog.json --include-approved-materials
make seed-validate
# Проверка diff файла в Git и редакторское утверждение.
```

Затем на **явно выбранной целевой БД**, в окружении backend с нужным DATABASE_URL:

```sh
python manage.py seed_validate production-seeds/catalog.json
python manage.py seed_import production-seeds/catalog.json --dry-run
# Сделать и проверить backup целевой БД средствами её провайдера/pg_dump.
python manage.py seed_import production-seeds/catalog.json --apply
```

`seed_import` без флага тоже выполняет dry-run. Создаёт/обновляет по natural keys, повторный запуск не дублирует, отсутствующие записи не удаляет. Отчёт содержит created/updated/skipped; конфликт ручных правок останавливает импорт. Перезапись конфликтов намеренно не предусмотрена. Подробности процесса и разрешённые поля — [docs/production-seed.md](docs/production-seed.md).

## Railway / Vercel

Развёртывание не выполнялось. Подготовлены проверенные локально Dockerfile и конфигурации, удалённые ресурсы не менялись.

Railway: корень build context — репозиторий; три отдельных процесса с файлами `infra/railway-api.json`, `infra/railway-worker.json`, `infra/railway-beat.json`. Указать config path отдельно для каждого сервиса; не менять корень на apps/backend при данном Dockerfile. API использует Gunicorn и назначенный PORT; только API выполняет migrate в pre-deploy. Worker/beat никогда не запускают миграции. Static Admin собирается в образе и раздаётся WhiteNoise. PostgreSQL, Redis и приватный внешний S3 подключаются переменными. Beat — ровно одна реплика. Порядок запуска и переменные — [docs/deployment.md](docs/deployment.md).

Vercel: Root Directory `apps/web`, включить доступ к файлам вне root; Node 24.x; конфигурация `apps/web/vercel.json` устанавливает зависимости из корня, собирает общий клиент и Vue, результат `dist`, SPA fallback. `VITE_API_URL=https://api.example.org` — только публичный адрес. Preview использует отдельный backend и отдельные данные.

Авторизация: session cookie HttpOnly Secure SameSite=Lax, точные CORS/CSRF origins и токен CSRF через session API. Для надёжной работы нужны **собственные домены одного site**: например app.example.org на Vercel и api.example.org на Railway. Связка *.vercel.app + *.up.railway.app без собственного домена этим контрактом не поддерживается. Production API не разрешает wildcard preview origins.

## Документация

- [Бизнес-правила и матрица требований](docs/business-rules.md).
- [Git-провайдеры и webhooks](docs/integrations.md).
- [Архитектура и границы модулей](docs/architecture.md).
- [Сущности и модель данных](docs/data-model.md).
- [Безопасность, приглашения и метрики](docs/security.md).
- [Переменные окружения и hosting](docs/deployment.md).
- [Production seed и миграции](docs/production-seed.md).
- [Реализовано и дальнейшие этапы](docs/status.md).
- [Дизайн](docs/design.md).
- [Результаты проверок](docs/verification.md).

Pinterest-референсы недоступны инструменту просмотра; сходство с ними не заявляется. Для точной адаптации нужны прикреплённые изображения. Предварительный интерфейс использует общие токены, настроенную тему PrimeVue, адаптивную навигацию, карточки, календарь, формы, состояния загрузки/ошибки/пустых данных.

## Расширенная бизнес-логика

Канонический API — `/api/v1/`: pagination `{count,next,previous,results}`, search и разрешённые filters. На PATCH и значимые действия передавайте `If-Match` = `updated_at` последнего прочитанного объекта. 428 требует ревизию; 409 `stale_revision` требует обновления данных и повторной проверки ввода. `/api/` сохранён как временный compatibility API.

Кабинет курса: `/courses/:id`; команда/этапы/документы/Git — `/projects/:id`; редактор материалов/заявки — `/manage/publications` и `/manage/competitions`; назначения/переводы — `/classes`; кабинет организации — `/workshops`. Для Git нужен отдельно настроенный серверный token и утверждённый Repository; без него возвращается явная ошибка конфигурации.

Worker использует тот же backend. Beat dispatches durable outbox и открытия регистрации; нужна одна реплика beat. После изменения Python-кода worker/beat в dev выполните `docker compose restart worker beat` (API перезагружается автоматически).

## Git и откат изменений

Текущая реализация зафиксирована исходной контрольной точкой. Последующие задачи оформляются отдельными коммитами; отмена — через `git revert <commit>` с сохранением истории. Git не включает `.env`, БД и S3. Подробности: [docs/version-control.md](docs/version-control.md).
