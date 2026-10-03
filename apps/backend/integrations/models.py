from django.db import models
from common.models import Entity


class Repository(Entity):
    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT)
    provider = models.CharField(
        max_length=20, choices=[("github", "GitHub"), ("gitverse", "GitVerse")]
    )
    owner = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    enabled = models.BooleanField(default=False)


class PullRequest(Entity):
    repository = models.ForeignKey(Repository, on_delete=models.PROTECT)
    external_number = models.PositiveIntegerField()
    status = models.CharField(max_length=20)
    url = models.URLField()
    title = models.CharField(max_length=200, blank=True)
    head_sha = models.CharField(max_length=64, blank=True)
    source_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["repository", "external_number"], name="unique_pr"
            )
        ]


class LearningReview(Entity):
    pull_request = models.ForeignKey(PullRequest, on_delete=models.PROTECT)
    reviewer = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    result = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Ожидает"),
            ("accepted", "Принято"),
            ("revision", "Доработка"),
        ],
    )
    remarks = models.TextField(blank=True)
    revision = models.CharField(max_length=64, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)


class WebhookEvent(Entity):
    repository = models.ForeignKey(Repository, on_delete=models.PROTECT)
    delivery = models.CharField(max_length=100)
    digest = models.CharField(max_length=64)
    status = models.CharField(max_length=20, default="queued")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["repository", "delivery"], name="unique_webhook_delivery"
            )
        ]


class SyncJob(Entity):
    repository = models.ForeignKey(Repository, on_delete=models.PROTECT)
    requested_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT
    )
    webhook = models.OneToOneField(
        WebhookEvent, null=True, blank=True, on_delete=models.PROTECT
    )
    status = models.CharField(max_length=20, default="queued")
    error_code = models.CharField(max_length=80, blank=True)
