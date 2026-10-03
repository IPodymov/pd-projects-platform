from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied
from common.access import (
    institution_ids,
    require_institution,
    classrooms,
)
from common.services import audit, notify
from institutions.models import StudentMembership
from .models import Workshop, Partnership, Registration, GroupApplication, Subscription
from common.api import BusinessError, check_revision


def visible(user):
    if user.is_superuser:
        return Workshop.objects.all()
    schools = set(institution_ids(user)) | set(
        StudentMembership.objects.filter(user=user, ended_at__isnull=True).values_list(
            "classroom__institution_id", flat=True
        )
    )
    partners = Partnership.objects.filter(
        school_id__in=schools,
        status="active",
        starts_on__lte=timezone.localdate(),
        ends_on__gte=timezone.localdate(),
    )
    q = (
        Q(audience="all")
        | Q(audience="partners", university_id__in=partners.values("university_id"))
        | Q(
            audience="selected",
            schools__id__in=partners.values("school_id"),
            university_id__in=partners.values("university_id"),
        )
    )
    # Selected school's partnership must belong to THIS university, not any university.
    candidates = Workshop.objects.filter(published=True).filter(q).distinct()
    ids = []
    for w in candidates:
        if (
            w.audience != "selected"
            or partners.filter(
                university=w.university, school_id__in=w.schools.values("pk")
            ).exists()
        ):
            ids.append(w.pk)
    return Workshop.objects.filter(Q(pk__in=ids) | Q(organizer=user) | Q(leader=user))


@transaction.atomic
def register(actor, workshop, users=None, school=None):
    workshop = Workshop.objects.select_for_update().get(pk=workshop.pk)
    if not visible(actor).filter(pk=workshop.pk).exists():
        raise PermissionDenied("Мастер-класс недоступен")
    now = timezone.now()
    if (
        workshop.cancelled
        or workshop.completed
        or not workshop.published
        or not workshop.registration_opens_at <= now <= workshop.registration_closes_at
    ):
        raise ValidationError("Регистрация закрыта")
    users = users or [actor]
    if len({u.pk for u in users}) != len(users) or len(users) > 500:
        raise ValidationError("Дубликаты участников или слишком большая группа")
    for participant in users:
        if workshop.min_age > 0 or workshop.max_age < 99:
            birth = participant.date_of_birth
            if not birth:
                raise ValidationError(
                    {
                        "users": "Участник должен указать дату рождения для возрастного ограничения"
                    }
                )
            day = workshop.starts_at.date()
            age = (
                day.year
                - birth.year
                - ((day.month, day.day) < (birth.month, birth.day))
            )
            if not workshop.min_age <= age <= workshop.max_age:
                raise ValidationError(
                    {"users": "Возраст участника не соответствует мероприятию"}
                )
    group = None
    if school:
        require_institution(actor, school, ["admin", "curator", "teacher"])
        for u in users:
            memberships = StudentMembership.objects.filter(
                user=u, classroom__institution=school, ended_at__isnull=True
            )
            if (
                not memberships.exists()
                or not memberships.filter(
                    classroom__in=classrooms(actor, True)
                ).exists()
            ):
                raise PermissionDenied("Участник не входит в доступные классы школы")
        group = GroupApplication.objects.create(
            workshop=workshop, school=school, responsible=actor
        )
    elif len(users) != 1 or users[0] != actor:
        raise PermissionDenied("Можно записать только себя")
    available = (
        workshop.capacity - workshop.registrations.filter(status="confirmed").count()
    )
    results = []
    for user in users:
        old = Registration.objects.filter(workshop=workshop, user=user).first()
        if old and old.status != "cancelled":
            raise ValidationError("Участник уже записан индивидуально или в группе")
        status = "confirmed" if available > 0 else "waiting"
        if status == "confirmed":
            available -= 1
        obj, _ = Registration.objects.update_or_create(
            workshop=workshop,
            user=user,
            defaults={"status": status, "group": group, "attended": False},
        )
        results.append(obj)
        notify(
            [user], "Запись на мастер-класс: " + workshop.title + " (" + status + ")"
        )
    if group:
        group.status = (
            "confirmed" if any(r.status == "confirmed" for r in results) else "waiting"
        )
        group.save()
    audit(actor, "workshop.registered", workshop, school, {"count": len(users)})
    return results


@transaction.atomic
def cancel(actor, registration, expected=None):
    Workshop.objects.select_for_update().get(pk=registration.workshop_id)
    registration = Registration.objects.select_for_update().get(pk=registration.pk)
    check_revision(registration, expected)
    responsible = registration.group and registration.group.responsible_id == actor.pk
    if responsible:
        require_institution(
            actor, registration.group.school, ["admin", "curator", "teacher"]
        )
        if not StudentMembership.objects.filter(
            user=registration.user, classroom__in=classrooms(actor, True)
        ).exists():
            raise PermissionDenied("Нет доступа к участнику группы")
    if (
        not responsible
        and registration.user_id != actor.pk
        and registration.workshop.organizer_id != actor.pk
        and not actor.is_superuser
    ):
        raise PermissionDenied("Нет права отмены")
    if registration.status == "cancelled":
        return registration
    previous = registration.status
    registration.status = "cancelled"
    registration.save()
    if previous == "confirmed":
        waiting = (
            Registration.objects.filter(
                workshop=registration.workshop, status="waiting"
            )
            .order_by("created_at")
            .first()
        )
        if waiting:
            waiting.status = "confirmed"
            waiting.save()
            if waiting.group_id:
                GroupApplication.objects.filter(pk=waiting.group_id).update(
                    status="confirmed"
                )
            notify([waiting.user], "Освободилось место: " + registration.workshop.title)
    if (
        registration.group_id
        and not registration.group.registration_set.exclude(status="cancelled").exists()
    ):
        GroupApplication.objects.filter(pk=registration.group_id).update(
            status="cancelled"
        )
    notify(
        [registration.user],
        "Отменена запись: " + registration.workshop.title,
        kind="registration.cancelled",
        target=registration.pk,
        event_key=f"registration-cancelled:{registration.pk}:{registration.updated_at.isoformat()}",
    )
    audit(actor, "workshop.cancelled", registration)
    return registration


@transaction.atomic
def announce(actor, workshop, expected=None):
    workshop = Workshop.objects.select_for_update().get(pk=workshop.pk)
    check_revision(workshop, expected)
    require_institution(actor, workshop.university, ["admin", "organizer"])
    require_institution(actor, workshop.university, ["admin", "organizer"])
    if not actor.is_superuser and workshop.organizer_id != actor.pk:
        raise PermissionDenied("Только организатор")
    validate_workshop(workshop)
    if workshop.university.kind != "university":
        raise ValidationError("Организатором должен быть вуз")
    if (
        workshop.starts_at >= workshop.ends_at
        or workshop.registration_opens_at >= workshop.registration_closes_at
        or not workshop.capacity
    ):
        raise ValidationError("Некорректное время или вместимость")
    partners = Partnership.objects.filter(
        university=workshop.university,
        status="active",
        starts_on__lte=timezone.localdate(),
        ends_on__gte=timezone.localdate(),
    )
    if (
        workshop.audience == "selected"
        and workshop.schools.exclude(pk__in=partners.values("school_id")).exists()
    ):
        raise ValidationError("Выбрана школа без действующего партнёрства")
    workshop.published = True
    workshop.save()
    subscriptions = Subscription.objects.filter(
        school_id__in=partners.values("school_id")
    ).select_related("user")
    if workshop.audience == "selected":
        subscriptions = subscriptions.filter(school__in=workshop.schools.all())
    for sub in subscriptions:
        if sub.school_id in institution_ids(sub.user):
            notify(
                [sub.user],
                "Доступен мастер-класс: " + workshop.title,
                email=sub.email_enabled,
                kind="workshop.published",
                target=workshop.pk,
                event_key=f"workshop-published:{workshop.pk}",
            )
    audit(actor, "workshop.published", workshop, workshop.university)


@transaction.atomic
def update_workshop(actor, workshop, values, expected=None):
    workshop = Workshop.objects.select_for_update().get(pk=workshop.pk)
    check_revision(workshop, expected)
    require_institution(actor, workshop.university, ["admin", "organizer"])
    if not actor.is_superuser and workshop.organizer_id != actor.pk:
        raise PermissionDenied("Только организатор")
    if values.get("university", workshop.university) != workshop.university:
        raise ValidationError("Вуз мероприятия неизменяем")
    schools = values.pop("schools", None)
    for key, value in values.items():
        setattr(workshop, key, value)
    if workshop.capacity < workshop.registrations.filter(status="confirmed").count():
        raise ValidationError("Вместимость меньше подтверждённых записей")
    if (
        workshop.starts_at >= workshop.ends_at
        or workshop.registration_opens_at >= workshop.registration_closes_at
        or workshop.min_age > workshop.max_age
    ):
        raise ValidationError("Некорректные даты или возрастные ограничения")
    validate_workshop(workshop)
    workshop.full_clean()
    workshop.save()
    if schools is not None:
        workshop.schools.set(schools)
    if workshop.published and workshop.audience == "selected":
        partners = Partnership.objects.filter(
            university=workshop.university,
            status="active",
            starts_on__lte=timezone.localdate(),
            ends_on__gte=timezone.localdate(),
        )
        if workshop.schools.exclude(pk__in=partners.values("school_id")).exists():
            raise ValidationError(
                {"schools": "Выбрана школа без действующего партнёрства"}
            )
    notify(
        [
            r.user
            for r in workshop.registrations.exclude(status="cancelled").select_related(
                "user"
            )
        ],
        "Изменён мастер-класс: " + workshop.title,
    )
    audit(
        actor,
        "workshop.changed",
        workshop,
        workshop.university,
        {"fields": list(values)},
    )
    return workshop


def validate_workshop(workshop):
    from urllib.parse import urlparse

    if workshop.university.kind != "university":
        raise ValidationError({"university": "Требуется вуз"})
    if workshop.status in ("cancelled", "completed"):
        raise BusinessError("Мероприятие закрыто", "workshop_closed")
    if (
        workshop.leader_id
        and not workshop.leader.staffassignment_set.filter(
            institution=workshop.university,
            active=True,
            role__in=["teacher", "organizer", "workshop_teacher"],
        ).exists()
    ):
        raise ValidationError({"leader": "Ведущий должен быть назначен вузу"})
    if workshop.format == "online":
        url = urlparse(workshop.online_url)
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ValidationError({"online_url": "Требуется HTTPS ссылка"})
    elif not workshop.location.strip():
        raise ValidationError({"location": "Укажите место"})
    workshop.full_clean()


@transaction.atomic
def close_workshop(actor, workshop, status, expected=None):
    workshop = Workshop.objects.select_for_update().get(pk=workshop.pk)
    check_revision(workshop, expected)
    require_institution(actor, workshop.university, ["admin", "organizer"])
    if not actor.is_superuser and workshop.organizer_id != actor.pk:
        raise PermissionDenied("Только организатор")
    if status not in ("cancelled", "completed") or workshop.status not in (
        "draft",
        "published",
    ):
        raise BusinessError("Недопустимый переход", "invalid_transition")
    if status == "completed" and workshop.ends_at > timezone.now():
        raise BusinessError("Мероприятие ещё не завершилось", "workshop_not_finished")
    if status == "cancelled":
        people = [
            r.user
            for r in workshop.registrations.exclude(status="cancelled").select_related(
                "user"
            )
        ]
        workshop.cancelled = True
        workshop.registrations.update(status="cancelled", attended=False)
        workshop.groupapplication_set.update(status="cancelled")
        notify(
            people,
            "Отменён мастер-класс: " + workshop.title,
            kind="workshop.cancelled",
            target=workshop.pk,
            event_key=f"workshop-cancelled:{workshop.pk}",
        )
    else:
        workshop.completed = True
    workshop.save()
    audit(actor, "workshop." + status, workshop, workshop.university)
    return workshop


@transaction.atomic
def cancel_group(actor, group, expected=None):
    Workshop.objects.select_for_update().get(pk=group.workshop_id)
    group = GroupApplication.objects.select_for_update().get(pk=group.pk)
    check_revision(group, expected)
    if (
        not actor.is_superuser
        and group.responsible_id != actor.pk
        and group.workshop.organizer_id != actor.pk
    ):
        raise PermissionDenied("Нет права отмены группы")
    for state in ("waiting", "confirmed"):
        for registration in group.registration_set.filter(status=state).order_by(
            "created_at"
        ):
            cancel(actor, registration)
    group.status = "cancelled"
    group.save()
    return group


@transaction.atomic
def record_attendance(actor, obj, attended, expected=None):
    Workshop.objects.select_for_update().get(pk=obj.workshop_id)
    obj = Registration.objects.select_for_update().get(pk=obj.pk)
    check_revision(obj, expected)
    if not actor.is_superuser and actor.pk not in (
        obj.workshop.organizer_id,
        obj.workshop.leader_id,
    ):
        raise PermissionDenied("Только организатор или ведущий")
    if obj.status != "confirmed" or obj.workshop.starts_at > timezone.now():
        raise BusinessError(
            "Посещение отмечается для подтверждённой записи после начала",
            "invalid_attendance",
        )
    obj.attended = attended
    obj.save()
    audit(actor, "workshop.attendance", obj, obj.workshop.university)
    return obj


@transaction.atomic
def transition_partnership(actor, obj, status, expected=None):
    if not actor.is_superuser:
        raise PermissionDenied("Партнёрства утверждает платформа")
    obj = Partnership.objects.select_for_update().get(pk=obj.pk)
    check_revision(obj, expected)
    if (
        status
        not in {"pending": ["active", "ended"], "active": ["ended"], "ended": []}[
            obj.status
        ]
    ):
        raise BusinessError("Недопустимый переход партнёрства", "invalid_transition")
    if obj.starts_on > obj.ends_on:
        raise ValidationError("Неверные сроки")
    obj.status = status
    obj.save()
    audit(actor, "partnership.transition", obj, obj.university, {"status": status})
    from institutions.models import StaffAssignment

    people = [
        s.user
        for s in StaffAssignment.objects.filter(
            institution=obj.school, active=True, role__in=["admin", "curator"]
        ).select_related("user")
    ]
    notify(
        people,
        "Партнёрство с вузом: " + status,
        kind="partnership.changed",
        target=obj.pk,
        event_key=f"partnership:{obj.pk}:{obj.updated_at.isoformat()}",
    )
    return obj
