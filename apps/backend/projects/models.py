from django.db import models
from django.conf import settings
from common.models import Entity


class Project(Entity):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    classroom = models.ForeignKey("institutions.Classroom", on_delete=models.PROTECT)
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, through="ProjectMember")
    status = models.CharField(
        max_length=20,
        choices=[
            ("draft", "Черновик"),
            ("active", "В работе"),
            ("submitted", "На проверке"),
            ("revision", "Доработка"),
            ("accepted", "Принят"),
            ("archived", "Архив"),
        ],
        default="active",
    )
    due_at = models.DateTimeField(null=True, blank=True)


class ProjectMember(Entity):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    role = models.CharField(
        max_length=20,
        choices=[("member", "Участник"), ("leader", "Лидер")],
        default="member",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "user"], name="unique_project_member"
            )
        ]


class Task(Entity):
    project = models.ForeignKey(Project, related_name="tasks", on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    stage = models.CharField(max_length=80, default="Основной")
    due_at = models.DateTimeField()
    milestone = models.ForeignKey(
        "Milestone",
        null=True,
        blank=True,
        related_name="tasks",
        on_delete=models.PROTECT,
    )
    criteria = models.TextField(blank=True)


class Submission(Entity):
    task = models.ForeignKey(Task, related_name="submissions", on_delete=models.CASCADE)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    text = models.TextField()
    result = models.CharField(
        max_length=20,
        choices=[
            ("draft", "Черновик"),
            ("submitted", "Отправлено"),
            ("accepted", "Принято"),
            ("revision", "На доработку"),
        ],
        default="submitted",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="reviews",
        on_delete=models.PROTECT,
    )
    feedback = models.TextField(blank=True)
    previous = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="revisions",
        on_delete=models.PROTECT,
    )
    document_version = models.ForeignKey(
        "documents.DocumentVersion", null=True, blank=True, on_delete=models.PROTECT
    )
    submitted_at = models.DateTimeField(null=True, blank=True)


class Milestone(Entity):
    project = models.ForeignKey(
        Project, related_name="milestones", on_delete=models.PROTECT
    )
    title = models.CharField(max_length=200)
    criteria = models.TextField()
    due_at = models.DateTimeField()
    position = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=[
            ("planned", "Запланирован"),
            ("active", "В работе"),
            ("submitted", "На проверке"),
            ("revision", "Доработка"),
            ("accepted", "Принят"),
        ],
        default="planned",
    )


class ReviewEvent(Entity):
    submission = models.OneToOneField(
        Submission, related_name="review_event", on_delete=models.PROTECT
    )
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    result = models.CharField(
        max_length=20, choices=[("revision", "Доработка"), ("accepted", "Принято")]
    )
    feedback = models.TextField(blank=True)


class ProjectTransition(Entity):
    project = models.ForeignKey(
        Project, related_name="transitions", on_delete=models.PROTECT
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    previous = models.CharField(max_length=20)
    status = models.CharField(max_length=20)
    feedback = models.TextField(blank=True)
