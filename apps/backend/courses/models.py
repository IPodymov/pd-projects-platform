from django.db import models
from django.conf import settings
from common.models import Entity


class Course(Entity):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    institution = models.ForeignKey(
        "institutions.Institution", on_delete=models.PROTECT
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ("draft", "Черновик"),
            ("published", "Опубликован"),
            ("archived", "Архив"),
        ],
        default="draft",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["draft", "published", "archived"]),
                name="course_status_valid",
            )
        ]


class Enrollment(Entity):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    course = models.ForeignKey(Course, on_delete=models.PROTECT)
    classroom = models.ForeignKey(
        "institutions.Classroom", null=True, blank=True, on_delete=models.PROTECT
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ("active", "Обучается"),
            ("completed", "Завершено"),
            ("cancelled", "Отменено"),
        ],
        default="active",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "course"], name="unique_enrollment")
        ]


class Assignment(Entity):
    course = models.ForeignKey(
        Course, related_name="assignments", on_delete=models.PROTECT
    )
    title = models.CharField(max_length=200)
    instructions = models.TextField()
    criteria = models.TextField()
    due_at = models.DateTimeField()
    position = models.PositiveIntegerField(default=0)
    required = models.BooleanField(default=True)


class CourseSubmission(Entity):
    assignment = models.ForeignKey(
        Assignment, related_name="submissions", on_delete=models.PROTECT
    )
    enrollment = models.ForeignKey(
        Enrollment, related_name="submissions", on_delete=models.PROTECT
    )
    text = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=[
            ("draft", "Черновик"),
            ("submitted", "Отправлено"),
            ("revision", "Доработка"),
            ("accepted", "Принято"),
        ],
        default="draft",
    )
    previous = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="course_reviews",
        on_delete=models.PROTECT,
    )
    feedback = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    status__in=["draft", "submitted", "revision", "accepted"]
                ),
                name="course_submission_status_valid",
            ),
            models.UniqueConstraint(
                fields=["previous"],
                condition=models.Q(previous__isnull=False),
                name="unique_course_submission_successor",
            ),
        ]


class CourseReview(Entity):
    submission = models.OneToOneField(
        CourseSubmission, related_name="review", on_delete=models.PROTECT
    )
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    result = models.CharField(
        max_length=20, choices=[("revision", "Доработка"), ("accepted", "Принято")]
    )
    feedback = models.TextField(blank=True)


class CourseMaterial(Entity):
    course = models.ForeignKey(
        Course, related_name="materials", on_delete=models.PROTECT
    )
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to="course-materials/%Y/%m")
    filename = models.CharField(max_length=200)
    size = models.PositiveIntegerField()
    teaching_resource = models.BooleanField(default=False)


class CourseLesson(Entity):
    course = models.ForeignKey(Course, related_name="lessons", on_delete=models.PROTECT)
    title = models.CharField(max_length=200)
    body = models.TextField()
    position = models.PositiveIntegerField(default=0)


class LessonCompletion(Entity):
    lesson = models.ForeignKey(CourseLesson, on_delete=models.PROTECT)
    enrollment = models.ForeignKey(Enrollment, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["lesson", "enrollment"], name="unique_lesson_completion"
            )
        ]
