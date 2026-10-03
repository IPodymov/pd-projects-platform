from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from common.api import check_revision, BusinessError
from common.access import require_institution
from common.services import audit, notify
from .models import StaffAssignment, TeachingAssignment, StudentMembership


@transaction.atomic
def set_staff_active(actor, obj, active, expected=None):
    obj = StaffAssignment.objects.select_for_update().get(pk=obj.pk)
    require_institution(actor, obj.institution, ["admin"])
    check_revision(obj, expected)
    if obj.role == "admin" and not actor.is_superuser:
        raise PermissionDenied("Администраторов назначает платформа")
    obj.active = active
    obj.save()
    audit(actor, "staff.assignment_changed", obj, obj.institution, {"active": active})
    notify(
        [obj.user],
        "Изменено назначение: " + obj.institution.name,
        kind="staff.changed",
        target=obj.pk,
        event_key=f"staff:{obj.pk}:{obj.updated_at.isoformat()}",
    )
    return obj


@transaction.atomic
def set_teaching_active(actor, obj, active, expected=None):
    obj = TeachingAssignment.objects.select_for_update().get(pk=obj.pk)
    require_institution(actor, obj.classroom.institution, ["admin"])
    check_revision(obj, expected)
    obj.active = active
    obj.save()
    audit(
        actor,
        "teaching.assignment_changed",
        obj,
        obj.classroom.institution,
        {"active": active},
    )
    return obj


@transaction.atomic
def transfer_student(actor, obj, classroom, expected=None):
    from accounts.models import User

    User.objects.select_for_update().get(pk=obj.user_id)
    obj = StudentMembership.objects.select_for_update().get(pk=obj.pk)
    require_institution(actor, obj.classroom.institution, ["admin"])
    require_institution(actor, classroom.institution, ["admin"])
    check_revision(obj, expected)
    if obj.classroom.institution_id != classroom.institution_id:
        raise ValidationError(
            "Межучрежденческий перенос требует отдельного согласования"
        )
    if obj.ended_at or obj.classroom_id == classroom.pk:
        raise BusinessError(
            "Членство завершено или выбран тот же класс", "invalid_transfer"
        )
    if StudentMembership.objects.filter(user=obj.user, classroom=classroom).exists():
        raise BusinessError(
            "Членство в целевом классе уже существует", "membership_exists"
        )
    obj.ended_at = timezone.localdate()
    obj.save()
    target = StudentMembership.objects.create(
        user=obj.user, classroom=classroom, started_at=timezone.localdate()
    )
    audit(
        actor,
        "student.transferred",
        target,
        classroom.institution,
        {"from": str(obj.classroom_id), "to": str(classroom.pk)},
    )
    notify(
        [obj.user],
        "Вы переведены в класс " + classroom.name,
        kind="student.transferred",
        target=target.pk,
        event_key=f"transfer:{target.pk}",
    )
    return target
