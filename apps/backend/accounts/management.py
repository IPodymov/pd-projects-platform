"""Administration of accounts and educational assignments with institution scope."""

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from common.access import institution_ids, require_institution
from common.api import check_revision
from common.services import audit
from institutions.models import StudentMembership
from .models import User


def users_for(actor):
    if not actor.is_authenticated or not actor.is_active:
        return User.objects.none()
    if actor.is_superuser:
        return User.objects.all()
    institutions = institution_ids(actor, ["admin"])
    return (
        User.objects.filter(
            Q(studentmembership__classroom__institution_id__in=institutions)
            | Q(staffassignment__institution_id__in=institutions)
        )
        .exclude(is_superuser=True)
        .distinct()
    )


def require_managed_user(actor, user):
    if not users_for(actor).filter(pk=user.pk).exists():
        raise PermissionDenied("Нет доступа к этой учётной записи")


def locked_user(actor, user, expected):
    user = User.objects.select_for_update().get(pk=user.pk)
    require_managed_user(actor, user)
    check_revision(user, expected, required=True)
    return user


def require_active(user):
    if not user.is_active:
        raise ValidationError("Учётная запись отключена")


def touch(user):
    user.save(update_fields=["updated_at"])


@transaction.atomic
def change_class(actor, user, classroom, membership=None, expected=None):
    from institutions.services import transfer_student
    from courses.models import Enrollment

    user = locked_user(actor, user, expected)
    require_active(user)
    require_institution(actor, classroom.institution, ["admin"])
    if membership:
        membership = StudentMembership.objects.select_for_update().get(pk=membership.pk)
        if membership.user_id != user.pk:
            raise ValidationError({"membership": "Членство другого пользователя"})
        if membership.classroom_id == classroom.pk and not membership.ended_at:
            return user
        target = transfer_student(actor, membership, classroom)
        # Continue active courses under the new classroom; completed history stays intact.
        Enrollment.objects.filter(
            user=user, classroom=membership.classroom, status="active"
        ).update(
            classroom=target.classroom,
            updated_at=timezone.now(),
        )
    else:
        current = StudentMembership.objects.filter(
            user=user,
            ended_at__isnull=True,
            classroom__institution=classroom.institution,
        )
        if current.exclude(classroom=classroom).exists():
            raise ValidationError({"membership": "Выберите текущий класс для перевода"})
        existing = StudentMembership.objects.filter(
            user=user, classroom=classroom
        ).first()
        if existing and existing.ended_at:
            raise ValidationError(
                "Этот класс уже есть в истории. Создайте класс нового учебного года."
            )
        if not existing:
            membership = StudentMembership.objects.create(
                user=user, classroom=classroom, started_at=timezone.localdate()
            )
            audit(actor, "account.class_assigned", membership, classroom.institution)
    touch(user)
    return user


@transaction.atomic
def add_registered_student(actor, email, classroom):
    require_institution(actor, classroom.institution, ["admin"])
    user = User.objects.select_for_update().filter(email__iexact=email.strip()).first()
    if not user:
        raise ValidationError({"email": "Пользователь ещё не зарегистрирован"})
    require_active(user)
    in_scope = users_for(actor).filter(pk=user.pk).exists()
    unassigned = (
        not user.studentmembership_set.exists()
        and not user.staffassignment_set.exists()
        and not user.is_superuser
    )
    if not in_scope and not (unassigned and user.email_verified_at):
        raise PermissionDenied(
            "Пользователь недоступен для назначения в ваше учреждение"
        )
    current = StudentMembership.objects.filter(
        user=user, classroom__institution=classroom.institution, ended_at__isnull=True
    )
    if current.exclude(classroom=classroom).exists():
        raise ValidationError(
            "Пользователь уже учится в другом классе. Откройте его карточку для перевода."
        )
    membership, created = StudentMembership.objects.get_or_create(
        user=user, classroom=classroom, defaults={"started_at": timezone.localdate()}
    )
    if membership.ended_at:
        raise ValidationError("Членство этого класса уже завершено")
    if created:
        audit(actor, "account.class_assigned", membership, classroom.institution)
        touch(user)
    return user


@transaction.atomic
def add_course(actor, user, course, classroom, expected=None):
    from courses.services import enroll

    user = locked_user(actor, user, expected)
    require_active(user)
    require_institution(actor, course.institution, ["admin"])
    enroll(actor, course, user, classroom)
    touch(user)
    return user


def attach_project(actor, user, project, role):
    from projects.models import ProjectMember

    require_institution(actor, project.classroom.institution, ["admin"])
    if project.status in {"accepted", "archived"}:
        raise ValidationError("Нельзя добавлять участников в закрытый проект")
    if not StudentMembership.objects.filter(
        user=user, classroom=project.classroom, ended_at__isnull=True
    ).exists():
        raise ValidationError(
            {"project": "Пользователь должен учиться в классе проекта"}
        )
    member, created = ProjectMember.objects.get_or_create(
        user=user, project=project, defaults={"role": role}
    )
    if created:
        audit(
            actor,
            "project.member_added",
            member,
            project.classroom.institution,
            {"user": str(user.pk), "role": role},
        )


@transaction.atomic
def add_project(actor, user, project, role="member", expected=None):
    from projects.models import Project

    user = locked_user(actor, user, expected)
    require_active(user)
    project = Project.objects.select_for_update().get(pk=project.pk)
    attach_project(actor, user, project, role)
    touch(user)
    return user


@transaction.atomic
def create_project(actor, user, values, expected=None):
    from projects.models import Project

    user = locked_user(actor, user, expected)
    require_active(user)
    require_institution(actor, values["classroom"].institution, ["admin"])
    project = Project.objects.create(**values)
    attach_project(actor, user, project, "member")
    audit(actor, "project.created", project, project.classroom.institution)
    touch(user)
    return user
