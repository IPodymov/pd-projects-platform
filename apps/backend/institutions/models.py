from django.db import models
from django.conf import settings
from common.models import Entity


class Institution(Entity):
    name = models.CharField(max_length=200)
    kind = models.CharField(
        max_length=20,
        choices=[("school", "Школа"), ("college", "Колледж"), ("university", "Вуз")],
    )

    def __str__(self):
        return self.name


class Classroom(Entity):
    institution = models.ForeignKey(Institution, on_delete=models.PROTECT)
    name = models.CharField(max_length=80)
    academic_year = models.CharField(max_length=9)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "name", "academic_year"],
                name="unique_class_year",
            )
        ]


class StaffAssignment(Entity):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    institution = models.ForeignKey(Institution, on_delete=models.PROTECT)
    role = models.CharField(
        max_length=20,
        choices=[
            ("admin", "Администратор учреждения"),
            ("curator", "Куратор"),
            ("teacher", "Преподаватель"),
            ("organizer", "Организатор"),
            ("workshop_teacher", "Преподаватель мастер-класса"),
        ],
    )
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "institution", "role"], name="unique_staff_role"
            )
        ]


class TeachingAssignment(Entity):
    staff = models.ForeignKey(StaffAssignment, on_delete=models.PROTECT)
    classroom = models.ForeignKey(Classroom, on_delete=models.PROTECT)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["staff", "classroom"], name="unique_teaching"
            )
        ]


class StudentMembership(Entity):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    classroom = models.ForeignKey(Classroom, on_delete=models.PROTECT)
    started_at = models.DateField()
    ended_at = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "classroom"], name="unique_student_class"
            ),
            models.CheckConstraint(
                condition=models.Q(ended_at__isnull=True)
                | models.Q(ended_at__gte=models.F("started_at")),
                name="membership_date_order",
            ),
        ]
