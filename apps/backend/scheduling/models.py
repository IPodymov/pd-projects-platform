from django.db import models
from common.models import Entity


class Series(Entity):
    timezone = models.CharField(max_length=80)
    local_start = models.DateTimeField()
    weeks = models.PositiveSmallIntegerField()


class Lesson(Entity):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    classroom = models.ForeignKey("institutions.Classroom", on_delete=models.PROTECT)
    course = models.ForeignKey(
        "courses.Course", null=True, blank=True, on_delete=models.PROTECT
    )
    teacher = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="lessons"
    )
    curator = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="curated_lessons",
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    timezone = models.CharField(max_length=80, default="Europe/Moscow")
    format = models.CharField(
        max_length=20, choices=[("online", "Онлайн"), ("onsite", "Очно")]
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ("scheduled", "Запланировано"),
            ("rescheduled", "Перенесено"),
            ("cancelled", "Отменено"),
            ("completed", "Проведено"),
        ],
        default="scheduled",
    )
    online_url = models.URLField(blank=True)
    location = models.CharField(max_length=200, blank=True)
    room = models.CharField(max_length=80, blank=True)
    series = models.ForeignKey(Series, null=True, blank=True, on_delete=models.PROTECT)
    occurrence = models.PositiveSmallIntegerField(default=0)
    is_exception = models.BooleanField(default=False)


class Attendance(Entity):
    lesson = models.ForeignKey(Lesson, on_delete=models.PROTECT)
    user = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    present = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["lesson", "user"], name="unique_attendance")
        ]
