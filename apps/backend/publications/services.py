from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from common.api import BusinessError, check_revision
from common.access import project_access
from common.services import audit, notify
from .models import CompetitionApplication, ApplicationTransition


@transaction.atomic
def publish_material(actor, obj, status, expected=None):
    if not actor.is_superuser:
        raise PermissionDenied("Материалы публикует администратор платформы")
    obj = type(obj).objects.select_for_update().get(pk=obj.pk)
    check_revision(obj, expected)
    if (
        status
        not in {"draft": ["published"], "published": ["archived"], "archived": []}[
            obj.status
        ]
    ):
        raise BusinessError("Недопустимый переход публикации", "invalid_transition")
    obj.published = status == "published"
    obj.archived = status == "archived"
    obj.full_clean()
    obj.save()
    audit(actor, "material." + status, obj)
    return obj


@transaction.atomic
def create_application(actor, values):
    project = values["project"]
    competition = values["competition"]
    project_access(actor, project)
    if (
        not competition.published
        or competition.archived
        or competition.deadline <= timezone.now()
    ):
        raise BusinessError("Приём заявок закрыт", "competition_closed")
    from projects.models import Project

    Project.objects.select_for_update().get(pk=project.pk)
    obj, created = CompetitionApplication.objects.get_or_create(
        competition=competition,
        project=project,
        defaults={"author": actor, "text": values["text"]},
    )
    if not created:
        raise BusinessError("Проект уже имеет заявку", "application_exists")
    audit(actor, "application.created", obj, project.classroom.institution)
    return obj


@transaction.atomic
def edit_application(actor, obj, values, expected=None):
    obj = CompetitionApplication.objects.select_for_update().get(pk=obj.pk)
    project_access(actor, obj.project)
    check_revision(obj, expected)
    if obj.author_id != actor.pk or obj.status not in ("draft", "revision"):
        raise BusinessError(
            "Редактируется только собственный черновик/доработка",
            "immutable_application",
        )
    if set(values) - {"text"}:
        raise ValidationError("Проект и конкурс неизменяемы")
    obj.text = values.get("text", obj.text)
    obj.save()
    return obj


@transaction.atomic
def transition_application(actor, obj, status, feedback="", expected=None):
    obj = CompetitionApplication.objects.select_for_update().get(pk=obj.pk)
    project_access(actor, obj.project)
    check_revision(obj, expected)
    allowed = {
        "draft": ["submitted", "cancelled"],
        "submitted": ["revision", "accepted", "rejected", "cancelled"],
        "revision": ["submitted", "cancelled"],
        "accepted": [],
        "rejected": [],
        "cancelled": [],
    }
    if status not in allowed[obj.status]:
        raise BusinessError("Недопустимый переход заявки", "invalid_transition")
    if status in ("revision", "accepted", "rejected"):
        if not actor.is_superuser:
            raise PermissionDenied("Заявки проверяет платформа")
        if status != "accepted" and not feedback.strip():
            raise ValidationError({"feedback": "Обязательно замечание"})
    elif obj.author_id != actor.pk:
        raise PermissionDenied("Изменить заявку может её автор")
    if status == "submitted" and (
        not obj.competition.published
        or obj.competition.archived
        or obj.competition.deadline <= timezone.now()
    ):
        raise BusinessError("Приём заявок закрыт", "competition_closed")
    ApplicationTransition.objects.create(
        application=obj,
        actor=actor,
        previous=obj.status,
        status=status,
        feedback=feedback,
        snapshot={"text": obj.text, "project_title": obj.project.title},
    )
    obj.status = status
    obj.save()
    audit(
        actor,
        "application.transition",
        obj,
        obj.project.classroom.institution,
        {"status": status},
    )
    notify(
        [obj.author],
        "Статус конкурсной заявки: " + status,
        kind="application.transition",
        target=obj.pk,
        event_key=f"application:{obj.pk}:{obj.updated_at.isoformat()}",
    )
    return obj
