# Git integrations

Repository привязан к проекту и провайдеру. Преподаватель связывает доступный проект, платформа утверждает доступ серверного токена (`enabled`). Без токена sync возвращает 503 `integration_unconfigured`; API не подменяет внешний результат демонстрационными PR. Токены поступают только из окружения backend. Доступны POST repositories/{id}/sync/, GET git-sync/, GET pull-requests/, POST pull-requests/{id}/assign/, POST git-reviews/{id}/decide/. Новый head создаёт необходимость новой проверки; завершённая проверка старого head сохраняется и помечается stale. Статус PR не меняется учебной проверкой.

GitHub: read-only API, pagination, version header, Authorization Bearer. Webhook `/api/v1/webhooks/{repository_uuid}/` проверяет HMAC SHA256 над исходным body (`X-Hub-Signature-256`) и `X-GitHub-Delivery`; unique delivery + digest запрещают повтор с другим payload.

GitVerse: отдельный адаптер, Accept `application/vnd.gitverse.object+json;version=1`, `per_page/page`, provider-specific `merged`, `head.sha`, `updated_at`. Переход по next Link разрешён только к фиксированному HTTPS API host/path. Webhook настраивается у провайдера с `authorization_header` = `Bearer <GITVERSE_WEBHOOK_SECRET>`; дедупликация по SHA256 body. GitHub HMAC для GitVerse не предполагается.

Webhook не применяет присланное состояние PR напрямую: сохраняет inbox и outbox-задание на авторитетное чтение провайдера. Монотонный source_updated_at отвергает устаревшие результаты синхронизации. Область доступа инициатора перепроверяется в worker. Настройки webhook и token scope на настоящих аккаунтах не проверены; нужны внешние доступы и отдельное разрешение на изменения удалённых ресурсов.

Официальные источники контракта: [GitHub signature](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries), [GitVerse PR API](https://gitverse.ru/docs/developers/public-api/pull-and-issues_2/pulls/api-get-repos-owner-repo-pulls), [GitVerse webhook authorization_header](https://gitverse.ru/docs/developers/public-api/webhooks/api-post-repos-hooks).
