# Развёртывание и окружения

Документация проверена 03.10.2026. Реальных сервисов Railway/Vercel не создавали и деплой не выполняли.

Официальные источники: [Railway Django](https://docs.railway.com/guides/django), [config as code](https://docs.railway.com/config-as-code/reference), [pre-deploy](https://docs.railway.com/deployments/pre-deploy-command), [healthchecks](https://docs.railway.com/deployments/healthchecks), [Vercel Vite](https://vercel.com/docs/frameworks/frontend/vite), [Vercel monorepos](https://vercel.com/docs/monorepos).

Git server-only переменные: GITHUB_TOKEN/GITVERSE_TOKEN и GITHUB_WEBHOOK_SECRET/GITVERSE_WEBHOOK_SECRET. Они необязательны для запуска платформы; без token sync явно отключён. Secrets относятся к конкретной среде, никогда не VITE_*. См. integrations.md.

Worker: concurrency=2, recycling и max-memory-per-child=256 MiB; настройте ограничение памяти сервиса. Durable outbox автоматически dispatches через beat, а обычные migration/production seed команды не запускаются worker.

## Матрица

| Переменная | Local Compose | Test | Preview / Production |
|---|---|---|---|
| DJANGO_SETTINGS_MODULE | config.settings.development | config.settings.test | config.settings.production |
| SECRET_KEY | локальный пример | не используется вне тестов | обязательный случайный секрет 50+ символов |
| DATABASE_URL | postgres:5432/platform | временная SQLite; TEST_DATABASE_URL включает отдельную PostgreSQL test DB | private PostgreSQL URL выбранного окружения |
| REDIS_URL | redis:6379/0 | локальный cache; Celery eager | приватный Redis для среды |
| ALLOWED_HOSTS | localhost,127.0.0.1,api | testserver | точные API hostnames и healthcheck.railway.app |
| WEB_URL | http://localhost:5173 | local default | https://app.example.org / https://preview.example.org |
| CORS_ALLOWED_ORIGINS | localhost:5173 | пусто | только точные frontend HTTPS origins этой среды |
| CSRF_TRUSTED_ORIGINS | localhost:5173 | стандартные test checks | те же явные origins |
| S3_BUCKET | documents | InMemoryStorage | отдельный приватный bucket среды |
| S3_ENDPOINT_URL | http://s3:8333 | не используется | внешний HTTPS S3 endpoint |
| S3_ACCESS_KEY / S3_SECRET_KEY | локальные ключи | не используются | secrets, минимум необходимых bucket permissions |
| S3_REGION | us-east-1 | не используется | регион провайдера |
| INVITATION_ENCRYPTION_KEY | уникальный make key | статический synthetic key | отдельный Fernet key для каждой среды |
| EMAIL_HOST / EMAIL_PORT | принудительно mailpit:1025 | in-memory | настроенный SMTP сервис, обычно 587 |
| EMAIL_USERNAME / EMAIL_PASSWORD | игнорируются dev backend | не используются | обязательные secrets |
| EMAIL_USE_TLS | dev игнорирует | не используется | true для SMTP STARTTLS |
| DEFAULT_FROM_EMAIL | platform@localhost | local | подтверждённый адрес SMTP отправителя |
| VITE_API_URL | пусто, Vite proxy | build test public value | публичный HTTPS API URL выбранной среды |
| API_PROXY_TARGET | http://api:8000 | не требуется | не требуется для статического frontend |
| PORT | API 8000 | произвольный | инжектируется Railway, Gunicorn использует его |
| WEB_CONCURRENCY | default 2 | не требуется | настраивается при необходимости в start command |
| GITHUB_TOKEN | необязателен | MockTransport | интеграция пока не включена; не передавать браузеру |
| GITVERSE_TOKEN | опционален, server-only | synthetic MockTransport | server-only токен read PR, если интеграция включена |

VITE_* доступны браузеру. DB, SMTP, Redis, S3 keys, Fernet и provider tokens туда не помещаются. .env игнорируется Git. Compose env_file передаёт значения процессам; manage.py сам dotenv не загружает.

В production settings проверяются обязательные переменные, формат Fernet, PostgreSQL, сильный SECRET_KEY, явные HTTPS origins; отсутствие конфигурации вызывает ImproperlyConfigured с именами недостающих переменных, без вывода значений. DEBUG=False. Разрешённый storage — только S3. SESSION_COOKIE_SECURE, CSRF_COOKIE_SECURE, HttpOnly session, SameSite=Lax, HSTS. Прокси Railway передаёт X-Forwarded-Proto; SECURE_PROXY_SSL_HEADER выбран для этого контракта. Нельзя выставлять этот header из неподконтрольного пользовательского reverse proxy.

## Railway

1. По отдельному разрешению создать/подключить PostgreSQL, Redis и приватный S3; SMTP и DNS подготовить отдельно. Данные preview и production изолировать.
2. Создать API, worker, beat из одного репозитория. Root/build context — корень репозитория. Для сервисов выбрать соответственно `/infra/railway-api.json`, `/infra/railway-worker.json`, `/infra/railway-beat.json` как config file path. Dockerfile во всех — apps/backend/Dockerfile.
3. Передать обязательные environment variables всем backend-процессам. DJANGO_SETTINGS_MODULE=config.settings.production. PostgreSQL/Redis брать private network URLs. ALLOWED_HOSTS включает api.example.org, назначенный API Railway hostname при его использовании и healthcheck.railway.app.
4. Только API имеет preDeployCommand `python manage.py migrate --noinput`. Это выполняется до переключения трафика; worker и каждую реплику не использовать как migrator. Деплоить API/migration сначала, затем совместимый worker. При параллельных независимых API deployments обеспечить единственного migrator средствами pipeline; pre-deploy одного сервиса не является глобальным DB lock для всех проектов.
5. Gunicorn слушает 0.0.0.0:$PORT, exec делает его основным процессом; SIGTERM обрабатывается graceful timeout. Логи stdout/stderr. collectstatic выполняется в Docker build с synthetic test settings без DB credentials; собранная статика включается в образ. WhiteNoise обслуживает Admin.
6. `/health/live/` — процесс жив, `/health/ready/` — DB и Redis доступны. Health endpoints освобождены от HTTPS redirect для внутренней проверки. S3 не проверяется readiness и проверяется отдельной операцией upload/download. Railway healthcheck используется при deploy, не является непрерывным мониторингом: для дальнейшего мониторинга нужен отдельный инструмент.
7. Worker отдельный start command `celery -A config worker --loglevel=INFO`; публичный HTTP domain не нужен. Beat `celery -A config beat --loglevel=INFO --schedule=/tmp/celerybeat-schedule`, строго одна реплика. Здесь периодическая очистка, не пользовательское расписание. Schedule файл beat временный, состояние заданий в DB.
8. Создать superuser явной `python manage.py createsuperuser` в выбранной среде. Не запускать demo_data. Seed — только отдельный утверждённый процесс после dry-run и backup.

## Vercel

- Import repository, Root Directory `apps/web`. Разрешить включение файлов вне Root Directory, потому что workspaces/client/lockfile расположены выше.
- Framework Vite, Node 24.x. Конфигурация приложения: install `cd ../.. && npm ci`; build `cd ../.. && npm run build`; Output Directory `dist` относительно apps/web.
- Root build сначала проверяет общий packages/api-client, затем TypeScript и Vite. Сгенерированный schema.ts хранится в Git, build не зависит от доступности backend.
- vercel.json rewrites даёт SPA fallback: вложенный /projects/:id, /schedule и /invite открываются напрямую. API размещён на отдельном hostname и не попадает под этот fallback. Ошибки API не маскируются index.html.
- Production VITE_API_URL — production API; Preview — отдельный preview API. Изменение VITE_* требует rebuild.
- Для надёжной session auth прикрепить app.example.org к production Vercel и api.example.org к Railway. Для preview: preview.example.org + api-preview.example.org, либо отдельная фиксированная ветка/domain на том же site. Динамические *.vercel.app не добавлять wildcard в production CORS/CSRF.

## Auth между доменами

Это cross-origin, но same-site модель. Host-only session cookie принадлежит API; frontend использует credentials=include. GET /api/session/ устанавливает CSRF cookie API и возвращает masked CSRF token в JSON. POST/PATCH заголовок X-CSRFToken; точный frontend Origin доверен CSRF и разрешён CORS. Login защищён CSRF даже до появления session; Logout — только POST. Куки не нужно расширять на .example.org.

Railway/Vercel служебные домены относятся к разным site; SameSite=Lax не гарантирует cross-site fetch sessions. Мы не предлагаем сменить на SameSite=None и полагаться на доступность third-party cookies. Для данного starter собственные same-site домены — требование production auth. Preview аккаунты/интеграции/SMTP не должны использовать production ресурсы. Проверка DNS, TLS и фактических proxy headers остаётся задачей реального deploy и не была выполнена здесь.
