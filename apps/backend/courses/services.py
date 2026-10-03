from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from common.api import BusinessError, check_revision
from common.access import require_class, require_institution
from common.services import audit, notify
from common.reviews import validate_work_review
from common.access import teacher_recipients
from institutions.models import StudentMembership
from crm.models import LearningActivity
from .models import Course, Enrollment, CourseSubmission, CourseReview


def progress(enrollment):
    tasks = enrollment.course.assignments.filter(required=True)
    accepted = (
        tasks.filter(submissions__enrollment=enrollment, submissions__status="accepted")
        .distinct()
        .count()
    )
    return round(100 * accepted / tasks.count()) if tasks.exists() else 0


@transaction.atomic
def change_course(actor, course, status, expected=None):
    course = Course.objects.select_for_update().get(pk=course.pk)
    require_institution(actor, course.institution)
    check_revision(course, expected)
    if (
        status
        not in {"draft": ["published"], "published": ["archived"], "archived": []}[
            course.status
        ]
    ):
        raise BusinessError("Недопустимый переход курса", "invalid_transition")
    if status == "published" and not course.assignments.exists():
        raise BusinessError("Добавьте задания перед публикацией", "course_empty")
    course.status = status
    course.save()
    audit(actor, "course.transition", course, course.institution, {"status": status})
    return course


@transaction.atomic
def enroll(actor, course, user, classroom):
    course = Course.objects.select_for_update().get(pk=course.pk)
    require_class(actor, classroom, staff=actor != user)
    if course.status != "published":
        raise BusinessError("Курс не открыт для записи", "course_not_open")
    if (
        classroom.institution_id != course.institution_id
        or not StudentMembership.objects.filter(
            user=user, classroom=classroom, ended_at__isnull=True
        ).exists()
    ):
        raise ValidationError(
            {"classroom": "Участник должен состоять в классе учреждения курса"}
        )
    obj, created = Enrollment.objects.get_or_create(
        user=user, course=course, defaults={"classroom": classroom}
    )
    if obj.classroom_id != classroom.pk:
        raise BusinessError(
            "Существующая запись относится к другому классу",
            "enrollment_class_conflict",
        )
    if obj.status == "cancelled":
        obj.status = "active"
        obj.save()
    if obj.status == "active" and progress(obj) == 100:
        obj.status = "completed"
        obj.save()
    if created:
        audit(actor, "course.enrolled", obj, course.institution)
    return obj


@transaction.atomic
def cancel_enrollment(actor, obj, expected=None):
    Course.objects.select_for_update().get(pk=obj.course_id)
    obj = Enrollment.objects.select_for_update().get(pk=obj.pk)
    require_class(actor, obj.classroom, staff=actor.pk != obj.user_id)
    check_revision(obj, expected)
    if obj.status == "completed":
        raise BusinessError("Завершённую запись нельзя отменить", "invalid_transition")
    obj.status = "cancelled"
    obj.save()
    audit(actor, "enrollment.cancelled", obj, obj.course.institution)
    return obj


@transaction.atomic
def create_work(actor, values):
    assignment = values["assignment"]
    Course.objects.select_for_update().get(pk=assignment.course_id)
    enrollment = Enrollment.objects.select_for_update().get(pk=values["enrollment"].pk)
    if (
        enrollment.user_id != actor.pk
        or enrollment.status != "active"
        or enrollment.course.status != "published"
    ):
        raise BusinessError(
            "Нет активной записи на опубликованный курс", "enrollment_inactive"
        )
    require_class(actor, enrollment.classroom)
    if assignment.course_id != enrollment.course_id:
        raise ValidationError({"assignment": "Задание другого курса"})
    previous = values.get("previous")
    latest = (
        CourseSubmission.objects.filter(assignment=assignment, enrollment=enrollment)
        .order_by("-created_at")
        .first()
    )
    if latest and (latest.status != "revision" or previous != latest):
        raise BusinessError(
            "Продолжите текущую работу или укажите последнюю доработку",
            "submission_exists",
        )
    if previous and (
        previous.assignment_id != assignment.pk
        or previous.enrollment_id != enrollment.pk
        or previous.status != "revision"
    ):
        raise ValidationError({"previous": "Неверная предыдущая отправка"})
    return CourseSubmission.objects.create(**values)


@transaction.atomic
def edit_work(actor, obj, text, expected=None):
    Course.objects.select_for_update().get(pk=obj.assignment.course_id)
    Enrollment.objects.select_for_update().get(pk=obj.enrollment_id)
    obj = CourseSubmission.objects.select_for_update().get(pk=obj.pk)
    check_revision(obj, expected)
    if obj.enrollment.user_id != actor.pk or obj.status != "draft":
        raise BusinessError(
            "Редактируется только собственный черновик", "immutable_submission"
        )
    require_class(actor, obj.enrollment.classroom)
    obj.text = text
    obj.save()
    return obj


@transaction.atomic
def send_work(actor, obj, expected=None):
    Course.objects.select_for_update().get(pk=obj.assignment.course_id)
    Enrollment.objects.select_for_update().get(pk=obj.enrollment_id)
    obj = CourseSubmission.objects.select_for_update().get(pk=obj.pk)
    check_revision(obj, expected)
    if (
        obj.enrollment.user_id != actor.pk
        or obj.status != "draft"
        or obj.enrollment.status != "active"
        or obj.enrollment.course.status != "published"
    ):
        raise BusinessError("Нет права отправить эту работу", "invalid_transition")
    require_class(actor, obj.enrollment.classroom)
    if not obj.text.strip():
        raise ValidationError({"text": "Заполните результат"})
    obj.status = "submitted"
    obj.submitted_at = timezone.now()
    obj.save()
    LearningActivity.objects.create(
        actor=actor,
        classroom=obj.enrollment.classroom,
        kind="course.submitted",
        target=str(obj.pk),
    )
    audit(actor, "course_submission.sent", obj, obj.enrollment.course.institution)
    notify(
        teacher_recipients(obj.enrollment.classroom),
        "Работа курса на проверке: " + obj.assignment.title,
        kind="course.submitted",
        target=obj.pk,
        event_key=f"course-work:{obj.pk}",
    )
    return obj


@transaction.atomic
def review_work(actor, obj, result, feedback, expected=None):
    Course.objects.select_for_update().get(pk=obj.assignment.course_id)
    enrollment = Enrollment.objects.select_for_update().get(pk=obj.enrollment_id)
    obj = CourseSubmission.objects.select_for_update().get(pk=obj.pk)
    require_class(actor, enrollment.classroom, True)
    check_revision(obj, expected)
    if obj.status != "submitted":
        raise BusinessError(
            "Работа уже проверена или не отправлена", "already_reviewed"
        )
    validate_work_review(result, feedback)
    CourseReview.objects.create(
        submission=obj, reviewer=actor, result=result, feedback=feedback
    )
    obj.status, obj.reviewer, obj.feedback = result, actor, feedback
    obj.save()
    if enrollment.status == "active" and progress(enrollment) == 100:
        enrollment.status = "completed"
        enrollment.save()
    audit(
        actor,
        "course_submission.reviewed",
        obj,
        enrollment.course.institution,
        {"result": result},
    )
    notify(
        [enrollment.user],
        "Проверена работа курса: " + obj.assignment.title,
        kind="course.reviewed",
        target=obj.pk,
        event_key=f"course-review:{obj.pk}",
    )
    return obj
