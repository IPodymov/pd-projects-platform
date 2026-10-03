from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from common.api import BusinessError, check_revision
from common.access import project_access
from common.services import audit, notify
from common.reviews import validate_work_review
from common.access import teacher_recipients
from crm.models import LearningActivity
from .models import Project, Submission, ReviewEvent, Milestone, ProjectTransition


def activity(actor, project, kind, obj):
    LearningActivity.objects.create(
        actor=actor, classroom=project.classroom, kind=kind, target=str(obj.pk)
    )


@transaction.atomic
def create_submission(actor, values, draft=False):
    task = values["task"]
    project = Project.objects.select_for_update().get(pk=task.project_id)
    project_access(actor, project)
    if project.status in ("accepted", "archived"):
        raise BusinessError("Проект закрыт для отправок", "project_closed")
    previous = values.get("previous")
    if previous and (
        previous.task_id != task.pk
        or previous.author_id != actor.pk
        or previous.result != "revision"
    ):
        raise ValidationError(
            {
                "previous": "Предыдущая отправка должна быть вашей работой на доработке по этому заданию"
            }
        )
    attachment = values.get("document_version")
    if attachment and attachment.document.project_id != project.pk:
        raise ValidationError({"document_version": "Версия из другого проекта"})
    last = (
        Submission.objects.filter(task=task, author=actor)
        .order_by("-created_at")
        .first()
    )
    if last and last.result in ("draft", "submitted", "accepted"):
        raise BusinessError(
            "Завершите текущую отправку перед созданием новой", "submission_exists"
        )
    if last and previous != last:
        raise ValidationError({"previous": "Укажите последнюю работу на доработке"})
    obj = Submission.objects.create(
        **values,
        author=actor,
        result="draft" if draft else "submitted",
        submitted_at=None if draft else timezone.now(),
    )
    if not draft:
        activity(actor, project, "task.submitted", obj)
        notify(
            teacher_recipients(project.classroom),
            "Работа на проверке: " + task.title,
            kind="submission.created",
            target=obj.pk,
            event_key=f"submission:{obj.pk}",
        )
    audit(actor, "submission.created", obj, project.classroom.institution)
    return obj


@transaction.atomic
def edit_draft(actor, obj, text, expected=None):
    Project.objects.select_for_update().get(pk=obj.task.project_id)
    obj = Submission.objects.select_for_update().get(pk=obj.pk)
    project_access(actor, obj.task.project)
    check_revision(obj, expected)
    if obj.author_id != actor.pk or obj.result != "draft":
        raise BusinessError(
            "Редактируется только собственный черновик", "immutable_submission"
        )
    obj.text = text
    obj.save()
    return obj


@transaction.atomic
def send_draft(actor, obj, expected=None):
    Project.objects.select_for_update().get(pk=obj.task.project_id)
    obj = Submission.objects.select_for_update().get(pk=obj.pk)
    project_access(actor, obj.task.project)
    check_revision(obj, expected)
    if obj.author_id != actor.pk or obj.result != "draft" or not obj.text.strip():
        raise BusinessError(
            "Можно отправить только заполненный собственный черновик",
            "invalid_transition",
        )
    if obj.task.project.status in ("accepted", "archived"):
        raise BusinessError("Проект закрыт", "project_closed")
    obj.result, obj.submitted_at = "submitted", timezone.now()
    obj.save()
    activity(actor, obj.task.project, "task.submitted", obj)
    audit(actor, "submission.sent", obj, obj.task.project.classroom.institution)
    return obj


@transaction.atomic
def review_submission(actor, obj, result, feedback, expected=None):
    Project.objects.select_for_update().get(pk=obj.task.project_id)
    obj = Submission.objects.select_for_update().get(pk=obj.pk)
    project_access(actor, obj.task.project, True)
    check_revision(obj, expected)
    if obj.result != "submitted":
        raise BusinessError(
            "Эта отправка уже проверена или не отправлена", "already_reviewed"
        )
    validate_work_review(result, feedback)
    ReviewEvent.objects.create(
        submission=obj, reviewer=actor, result=result, feedback=feedback
    )
    obj.result, obj.feedback, obj.reviewer = result, feedback, actor
    obj.save()
    audit(
        actor,
        "submission.reviewed",
        obj,
        obj.task.project.classroom.institution,
        {"result": result},
    )
    notify(
        [obj.author],
        "Проверена работа: " + obj.task.title,
        kind="submission.reviewed",
        target=obj.pk,
        event_key=f"review:{obj.pk}",
    )
    return obj


@transaction.atomic
def transition_project(actor, obj, status, feedback="", expected=None):
    obj = Project.objects.select_for_update().get(pk=obj.pk)
    project_access(
        actor, obj, staff=status in ("active", "revision", "accepted", "archived")
    )
    check_revision(obj, expected)
    transitions = {
        "draft": ["active"],
        "active": ["submitted", "archived"],
        "submitted": ["revision", "accepted"],
        "revision": ["submitted", "archived"],
        "accepted": ["archived"],
        "archived": [],
    }
    if status not in transitions[obj.status]:
        raise BusinessError("Недопустимый переход проекта", "invalid_transition")
    if status == "revision" and not feedback.strip():
        raise ValidationError({"feedback": "Нужно замечание"})
    if status == "accepted":
        if (
            not obj.tasks.exists()
            or obj.tasks.exclude(submissions__result="accepted").exists()
            or obj.milestones.exclude(status="accepted").exists()
        ):
            raise BusinessError(
                "Сначала примите все задания и этапы", "incomplete_project"
            )
    ProjectTransition.objects.create(
        project=obj, actor=actor, previous=obj.status, status=status, feedback=feedback
    )
    obj.status = status
    obj.save()
    audit(
        actor, "project.transition", obj, obj.classroom.institution, {"status": status}
    )
    notify(
        list(obj.members.all()),
        "Статус проекта: " + status,
        kind="project.transition",
        target=obj.pk,
        event_key=f"project:{obj.pk}:{obj.updated_at.isoformat()}",
    )
    return obj


@transaction.atomic
def transition_milestone(actor, obj, status, expected=None):
    obj = Milestone.objects.select_for_update().get(pk=obj.pk)
    project_access(actor, obj.project, status in ("active", "revision", "accepted"))
    check_revision(obj, expected)
    allowed = {
        "planned": ["active"],
        "active": ["submitted"],
        "submitted": ["accepted", "revision"],
        "revision": ["submitted"],
        "accepted": [],
    }
    if status not in allowed[obj.status]:
        raise BusinessError("Недопустимый переход этапа", "invalid_transition")
    if status == "accepted" and (
        not obj.tasks.exists()
        or obj.tasks.exclude(submissions__result="accepted").exists()
    ):
        raise BusinessError(
            "Все задания этапа должны быть приняты", "incomplete_milestone"
        )
    obj.status = status
    obj.save()
    audit(
        actor,
        "milestone.transition",
        obj,
        obj.project.classroom.institution,
        {"status": status},
    )
    return obj
