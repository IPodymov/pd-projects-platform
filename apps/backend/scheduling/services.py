from datetime import timedelta, timezone as utc_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from urllib.parse import urlparse
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import ValidationError
from institutions.models import Institution
from accounts.models import User
from common.access import require_institution, classroom_teachers
from common.services import audit, notify
from .models import Lesson, Series


def validate_lesson(lesson, ignore_ids=()):
    if (
        lesson.course_id
        and lesson.course.institution_id != lesson.classroom.institution_id
    ):
        raise ValidationError({"course": "Курс должен принадлежать учреждению класса"})
    try:
        ZoneInfo(lesson.timezone)
    except ZoneInfoNotFoundError:
        raise ValidationError("Неизвестный часовой пояс")
    if not lesson.starts_at or not lesson.ends_at or lesson.starts_at >= lesson.ends_at:
        raise ValidationError("Начало должно предшествовать окончанию")
    if lesson.starts_at.tzinfo is None or lesson.ends_at.tzinfo is None:
        raise ValidationError("Время должно содержать часовой пояс")
    if lesson.format == "online":
        parsed = urlparse(lesson.online_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise ValidationError("Для онлайн-занятия требуется HTTPS ссылка")
        lesson.location = ""
        lesson.room = ""
    elif lesson.format == "onsite":
        if not lesson.location or not lesson.room:
            raise ValidationError("Для очного занятия обязательны место и аудитория")
        lesson.online_url = ""
    else:
        raise ValidationError("Недопустимый формат")
    if (
        not classroom_teachers(lesson.classroom)
        .filter(staff__user=lesson.teacher)
        .exists()
    ):
        raise ValidationError("Преподаватель не назначен этому классу")
    if (
        lesson.curator_id
        and not lesson.curator.staffassignment_set.filter(
            institution=lesson.classroom.institution, active=True, role="curator"
        ).exists()
    ):
        raise ValidationError("Куратор не назначен учреждению")
    if lesson.status == "cancelled":
        return
    conflict = (
        Lesson.objects.exclude(pk=lesson.pk)
        .exclude(pk__in=ignore_ids)
        .exclude(status="cancelled")
        .filter(starts_at__lt=lesson.ends_at, ends_at__gt=lesson.starts_at)
    )
    scope = Q(teacher=lesson.teacher) | Q(classroom=lesson.classroom)
    if lesson.format == "onsite":
        scope |= Q(
            classroom__institution=lesson.classroom.institution,
            format="onsite",
            location=lesson.location,
            room=lesson.room,
        )
    if conflict.filter(scope).exists():
        raise ValidationError("Пересечение преподавателя, класса или аудитории")


def lock_lesson(lesson):
    User.objects.select_for_update().get(pk=lesson.teacher_id)
    Institution.objects.select_for_update().get(pk=lesson.classroom.institution_id)


def lesson_users(lesson):
    members = [
        m.user
        for m in lesson.classroom.studentmembership_set.filter(
            ended_at__isnull=True
        ).select_related("user")
    ]
    if lesson.course_id:
        ids = set(
            lesson.course.enrollment_set.filter(
                status__in=["active", "completed"]
            ).values_list("user_id", flat=True)
        )
        members = [user for user in members if user.pk in ids]
    return members + [lesson.teacher] + ([lesson.curator] if lesson.curator_id else [])


@transaction.atomic
def create_lesson(actor, values, weeks=1):
    if not 1 <= weeks <= 52:
        raise ValidationError("Повторение: от 1 до 52 недель")
    lesson = Lesson(**values)
    if lesson.course_id and lesson.course.status != "published":
        raise ValidationError({"course": "Курс должен быть опубликован"})
    if lesson.status != "scheduled":
        raise ValidationError(
            {"status": "Новое занятие создаётся в состоянии запланировано"}
        )
    require_institution(actor, lesson.classroom.institution)
    lock_lesson(lesson)
    validate_lesson(lesson)
    zone = ZoneInfo(lesson.timezone)
    start = lesson.starts_at.astimezone(zone)
    end = lesson.ends_at.astimezone(zone)
    series = (
        Series.objects.create(timezone=lesson.timezone, local_start=start, weeks=weeks)
        if weeks > 1
        else None
    )
    result = []
    for n in range(weeks):
        # Add calendar weeks in the series timezone, then persist UTC.
        begins = start + timedelta(weeks=n)
        finishes = end + timedelta(weeks=n)
        if begins.astimezone(utc_timezone.utc).astimezone(zone).replace(
            tzinfo=None
        ) != begins.replace(tzinfo=None):
            raise ValidationError("Несуществующее локальное время при переходе DST")
        obj = Lesson(
            **{**values, "starts_at": begins, "ends_at": finishes},
            series=series,
            occurrence=n,
        )
        validate_lesson(obj)
        obj.full_clean()
        obj.save()
        result.append(obj)
        audit(actor, "lesson.created", obj, obj.classroom.institution)
        notify(lesson_users(obj), "Новое занятие: " + obj.title)
    return result


@transaction.atomic
def change_lesson(actor, lesson, values, whole_series=False, expected=None):
    lock_lesson(lesson)
    lesson = (
        Lesson.objects.select_for_update()
        .select_related("classroom__institution")
        .get(pk=lesson.pk)
    )
    require_institution(actor, lesson.classroom.institution)
    from common.api import check_revision, BusinessError

    check_revision(lesson, expected)
    lock_lesson(lesson)
    allowed = {
        "title",
        "description",
        "starts_at",
        "ends_at",
        "timezone",
        "format",
        "status",
        "online_url",
        "location",
        "room",
    }
    if set(values) - allowed:
        raise ValidationError("Поля расписания запрещены")
    targets = (
        list(
            Lesson.objects.select_for_update()
            .filter(series=lesson.series)
            .order_by("starts_at")
        )
        if whole_series and lesson.series_id
        else [lesson]
    )
    editable = [obj for obj in targets if not (whole_series and obj.is_exception)]
    zone = ZoneInfo(
        lesson.series.timezone if whole_series and lesson.series_id else lesson.timezone
    )
    original_start = lesson.starts_at.astimezone(zone).replace(tzinfo=None)
    original_end = lesson.ends_at.astimezone(zone).replace(tzinfo=None)
    start_shift = (
        values.get("starts_at", lesson.starts_at).astimezone(zone).replace(tzinfo=None)
        - original_start
    )
    end_shift = (
        values.get("ends_at", lesson.ends_at).astimezone(zone).replace(tzinfo=None)
        - original_end
        if "ends_at" in values
        else start_shift
    )
    for obj in editable:
        next_status = values.get("status", obj.status)
        if (
            next_status != obj.status
            and next_status
            not in {
                "scheduled": ["rescheduled", "cancelled", "completed"],
                "rescheduled": ["cancelled", "completed"],
                "cancelled": [],
                "completed": [],
            }[obj.status]
        ):
            raise BusinessError("Недопустимый переход занятия", "invalid_transition")
        if obj.status in ("cancelled", "completed") and any(
            k != "status" for k in values
        ):
            raise BusinessError(
                "Завершённое/отменённое занятие неизменяемо", "lesson_closed"
            )
        old_start, old_end = obj.starts_at, obj.ends_at
        for k, v in values.items():
            setattr(obj, k, v)
        if whole_series and lesson.series_id:
            obj.starts_at = (
                old_start.astimezone(zone).replace(tzinfo=None) + start_shift
            ).replace(tzinfo=zone)
            obj.ends_at = (
                old_end.astimezone(zone).replace(tzinfo=None) + end_shift
            ).replace(tzinfo=zone)
        for dt in (obj.starts_at, obj.ends_at):
            z = ZoneInfo(obj.timezone)
            if dt.astimezone(utc_timezone.utc).astimezone(z).replace(
                tzinfo=None
            ) != dt.astimezone(z).replace(tzinfo=None):
                raise ValidationError("Несуществующее локальное время DST")
        obj.is_exception = bool(obj.series_id and not whole_series)
    ids = [obj.pk for obj in editable]
    for obj in editable:
        validate_lesson(obj, ids)
        for other in editable:
            if (
                obj.pk != other.pk
                and obj.status != "cancelled"
                and other.status != "cancelled"
                and obj.starts_at < other.ends_at
                and obj.ends_at > other.starts_at
            ):
                raise ValidationError("Пересечение внутри изменённой серии")
        obj.full_clean()
        obj.save()
        audit(
            actor,
            "lesson.changed",
            obj,
            obj.classroom.institution,
            {"fields": list(values)},
        )
        notify(
            lesson_users(obj),
            "Обновлено занятие: " + obj.title,
            kind="lesson.changed",
            target=obj.pk,
            event_key=f"lesson:{obj.pk}:{obj.updated_at.isoformat()}",
        )
    if whole_series and lesson.series_id and editable:
        lesson.series.local_start = min(o.starts_at for o in editable)
        lesson.series.timezone = values.get("timezone", lesson.series.timezone)
        lesson.series.save()
    return next((obj for obj in editable if obj.pk == lesson.pk), lesson)


@transaction.atomic
def record_class_attendance(actor, lesson, user, present, obj=None, expected=None):
    from common.access import require_class
    from institutions.models import StudentMembership
    from .models import Attendance
    from common.api import BusinessError, check_revision

    lock_lesson(lesson)
    lesson = Lesson.objects.select_for_update().get(pk=lesson.pk)
    require_class(actor, lesson.classroom, True)
    from django.utils import timezone

    if lesson.starts_at > timezone.now() or lesson.status == "cancelled":
        raise BusinessError(
            "Посещение отмечается после начала действующего занятия",
            "invalid_attendance",
        )
    if (
        not StudentMembership.objects.filter(
            user=user,
            classroom=lesson.classroom,
            started_at__lte=lesson.starts_at.date(),
        )
        .filter(Q(ended_at__isnull=True) | Q(ended_at__gte=lesson.starts_at.date()))
        .exists()
    ):
        raise ValidationError({"user": "Участник не состоял в классе на дату занятия"})
    if (
        lesson.course_id
        and not lesson.course.enrollment_set.filter(
            user=user, status__in=["active", "completed"]
        ).exists()
    ):
        raise ValidationError({"user": "Нет записи на курс занятия"})
    if obj:
        obj = Attendance.objects.select_for_update().get(pk=obj.pk)
        check_revision(obj, expected)
        obj.present = present
        obj.save()
    else:
        obj, _ = Attendance.objects.get_or_create(
            lesson=lesson, user=user, defaults={"present": present}
        )
        if obj.present != present:
            raise BusinessError(
                "Отметка уже существует; обновите её с текущей ревизией",
                "attendance_exists",
            )
    audit(
        actor,
        "attendance.recorded",
        obj,
        lesson.classroom.institution,
        {"present": present},
    )
    return obj
