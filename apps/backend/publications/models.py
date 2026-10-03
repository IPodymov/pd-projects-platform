from django.db import models
from common.models import Entity


class Topic(models.Model):
    code = models.SlugField(primary_key=True)
    title = models.CharField(max_length=100)


class Publication(Entity):
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    body = models.TextField()
    topic = models.ForeignKey(Topic, on_delete=models.PROTECT)
    published = models.BooleanField(default=False)
    approved_for_production = models.BooleanField(default=False)
    is_demo = models.BooleanField(default=False)
    archived = models.BooleanField(default=False)
    visibility = models.CharField(
        max_length=20,
        choices=[("public", "Все"), ("authenticated", "Участники")],
        default="public",
    )

    @property
    def status(self):
        return (
            "archived" if self.archived else "published" if self.published else "draft"
        )


class Competition(Entity):
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    requirements = models.TextField()
    deadline = models.DateTimeField()
    topic = models.ForeignKey(Topic, on_delete=models.PROTECT)
    published = models.BooleanField(default=False)
    approved_for_production = models.BooleanField(default=False)
    is_demo = models.BooleanField(default=False)
    archived = models.BooleanField(default=False)
    visibility = models.CharField(
        max_length=20,
        choices=[("public", "Все"), ("authenticated", "Участники")],
        default="public",
    )

    @property
    def status(self):
        return (
            "archived" if self.archived else "published" if self.published else "draft"
        )


class CompetitionApplication(Entity):
    competition = models.ForeignKey(Competition, on_delete=models.PROTECT)
    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT)
    author = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    text = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=[
            ("draft", "Черновик"),
            ("submitted", "Отправлена"),
            ("revision", "Доработка"),
            ("accepted", "Принята"),
            ("rejected", "Отклонена"),
            ("cancelled", "Отменена"),
        ],
        default="draft",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["competition", "project"], name="unique_competition_project"
            )
        ]


class ApplicationTransition(Entity):
    application = models.ForeignKey(
        CompetitionApplication, related_name="history", on_delete=models.PROTECT
    )
    actor = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    previous = models.CharField(max_length=20)
    status = models.CharField(max_length=20)
    feedback = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict)
