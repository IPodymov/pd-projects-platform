from django.db.models import Q
from rest_framework.exceptions import PermissionDenied
from institutions.models import (
    Institution,
    Classroom,
    StaffAssignment,
    TeachingAssignment,
    StudentMembership,
)


def classroom_teachers(classroom):
    """Current teaching assignments, shared by access checks and notifications."""
    return TeachingAssignment.objects.filter(
        classroom=classroom,
        active=True,
        staff__active=True,
        staff__role="teacher",
    )


def teacher_recipients(classroom):
    return [
        assignment.staff.user
        for assignment in classroom_teachers(classroom).select_related("staff__user")
    ]


def institution_ids(user, roles=None):
    if not user.is_authenticated or not user.is_active:
        return Institution.objects.none().values_list("id", flat=True)
    if user.is_superuser:
        return Institution.objects.values_list("id", flat=True)
    q = StaffAssignment.objects.filter(user=user, active=True)
    if roles:
        q = q.filter(role__in=roles)
    return q.values_list("institution_id", flat=True)


def classrooms(user, staff_only=False):
    if not user.is_authenticated or not user.is_active:
        return Classroom.objects.none()
    if user.is_superuser:
        return Classroom.objects.all()
    q = Q(institution_id__in=institution_ids(user, ["admin", "curator"])) | Q(
        id__in=TeachingAssignment.objects.filter(
            staff__user=user, staff__active=True, staff__role="teacher", active=True
        ).values("classroom_id")
    )
    if not staff_only:
        q |= Q(
            id__in=StudentMembership.objects.filter(
                user=user, ended_at__isnull=True
            ).values("classroom_id")
        )
    return Classroom.objects.filter(q).distinct()


def require_class(user, classroom, staff=False):
    if not classrooms(user, staff).filter(pk=classroom.pk).exists():
        raise PermissionDenied("Нет доступа к этому классу")


def require_institution(user, institution, roles=("admin", "curator")):
    if institution.pk not in institution_ids(user, roles):
        raise PermissionDenied("Нет полномочий в этом учреждении")


def project_access(user, project, staff=False):
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied("Аккаунт недоступен")
    if staff:
        require_class(user, project.classroom, True)
    elif (
        not classrooms(user, True).filter(pk=project.classroom_id).exists()
        and not project.members.filter(pk=user.pk).exists()
    ):
        raise PermissionDenied("Нет доступа к проекту")
