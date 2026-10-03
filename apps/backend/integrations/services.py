import hashlib, hmac, json
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from common.access import project_access
from common.api import BusinessError, check_revision
from common.outbox import enqueue
from common.services import audit, notify
from .models import PullRequest, LearningReview, WebhookEvent, SyncJob


@transaction.atomic
def request_sync(actor, repository):
    project_access(actor, repository.project, True)
    if not repository.enabled:
        raise BusinessError(
            "Соединение должно быть утверждено платформой", "repository_unapproved"
        )
    token = getattr(
        settings,
        "GITHUB_TOKEN" if repository.provider == "github" else "GITVERSE_TOKEN",
        "",
    )
    if not token:
        raise BusinessError(
            "Токен провайдера не настроен", "integration_unconfigured", 503
        )
    job = SyncJob.objects.create(repository=repository, requested_by=actor)
    enqueue("git_sync", {"pk": str(job.pk)}, f"git-sync:{job.pk}")
    return job


@transaction.atomic
def receive_webhook(repository, body, headers):
    if not repository.enabled:
        raise PermissionDenied("Соединение не утверждено")
    if len(body) > 1024 * 1024:
        raise ValidationError("Событие слишком большое")
    if repository.provider == "github":
        secret = settings.GITHUB_WEBHOOK_SECRET
        expected = (
            "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        )
        if not secret or not hmac.compare_digest(
            expected, headers.get("X-Hub-Signature-256", "")
        ):
            raise PermissionDenied("Некорректная подпись")
        delivery = headers.get("X-GitHub-Delivery", "")
        if not delivery or len(delivery) > 100:
            raise ValidationError("Не указан delivery")
    else:
        secret = settings.GITVERSE_WEBHOOK_SECRET
        if not secret or not hmac.compare_digest(
            "Bearer " + secret, headers.get("Authorization", "")
        ):
            raise PermissionDenied("Некорректный секрет вебхука")
        delivery = hashlib.sha256(body).hexdigest()
    try:
        data = json.loads(body)
    except ValueError:
        raise ValidationError("Ожидается JSON")
    if not isinstance(data, dict) or not isinstance(data.get("repository"), dict):
        raise ValidationError("Ожидается объект события с репозиторием")
    remote = data.get("repository", {})
    if (
        remote.get("full_name", "").casefold()
        != f"{repository.owner}/{repository.name}".casefold()
    ):
        raise PermissionDenied("Событие другого репозитория")
    digest = hashlib.sha256(body).hexdigest()
    event, created = WebhookEvent.objects.get_or_create(
        repository=repository, delivery=delivery, defaults={"digest": digest}
    )
    if not created and event.digest != digest:
        raise BusinessError(
            "Delivery уже использован другим payload", "delivery_conflict"
        )
    if created:
        job = SyncJob.objects.create(repository=repository, webhook=event)
        enqueue("git_sync", {"pk": str(job.pk)}, f"git-sync:{job.pk}")
    return event, created


@transaction.atomic
def assign_review(actor, pull, reviewer):
    pull = PullRequest.objects.select_for_update().get(pk=pull.pk)
    project_access(actor, pull.repository.project, True)
    project_access(reviewer, pull.repository.project, True)
    if not pull.head_sha:
        raise BusinessError("Сначала синхронизируйте ревизию", "revision_unknown")
    obj, created = LearningReview.objects.get_or_create(
        pull_request=pull,
        reviewer=reviewer,
        revision=pull.head_sha,
        defaults={"result": "pending"},
    )
    if created:
        audit(
            actor,
            "pr.reviewer_assigned",
            obj,
            pull.repository.project.classroom.institution,
        )
        notify(
            [reviewer],
            "Назначена проверка PR: " + pull.title,
            kind="pr.assigned",
            target=obj.pk,
            event_key=f"pr-review-assigned:{obj.pk}",
        )
    return obj


@transaction.atomic
def decide_review(actor, obj, result, remarks, expected=None):
    # Lock PR first: sync and review cannot disagree about current revision.
    pull = PullRequest.objects.select_for_update().get(pk=obj.pull_request_id)
    obj = LearningReview.objects.select_for_update().get(pk=obj.pk)
    project_access(actor, pull.repository.project, True)
    check_revision(obj, expected)
    if obj.reviewer_id != actor.pk or obj.result != "pending":
        raise BusinessError(
            "Проверка не назначена вам или уже завершена", "already_reviewed"
        )
    if obj.revision != pull.head_sha:
        raise BusinessError(
            "Новые коммиты требуют новой проверки", "stale_git_revision"
        )
    if result not in ("accepted", "revision") or (
        result == "revision" and not remarks.strip()
    ):
        raise ValidationError({"remarks": "Обязательно замечание для доработки"})
    obj.result, obj.remarks, obj.decided_at = result, remarks, timezone.now()
    obj.save()
    audit(
        actor,
        "pr.reviewed",
        obj,
        pull.repository.project.classroom.institution,
        {"result": result, "revision": obj.revision},
    )
    notify(
        list(pull.repository.project.members.all()),
        "Проверен PR: " + pull.title,
        kind="pr.reviewed",
        target=obj.pk,
        event_key=f"pr-reviewed:{obj.pk}",
    )
    return obj
