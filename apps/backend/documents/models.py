from django.db import models
from django.conf import settings
from common.models import Entity


class Document(Entity):
    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT)
    title = models.CharField(max_length=200)


class DocumentVersion(Entity):
    document = models.ForeignKey(
        Document, related_name="versions", on_delete=models.PROTECT
    )
    file = models.FileField(upload_to="documents/%Y/%m")
    filename = models.CharField(max_length=200)
    checksum = models.CharField(max_length=64)
    size = models.PositiveIntegerField()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    previous = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT
    )
    restored_from = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="restorations",
        on_delete=models.PROTECT,
    )
    text_content = models.TextField(blank=True)
    extraction_status = models.CharField(max_length=20, default="pending")
    structure = models.JSONField(default=list)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["previous"],
                condition=models.Q(previous__isnull=False),
                name="unique_document_successor",
            ),
            models.UniqueConstraint(
                fields=["document"],
                condition=models.Q(previous__isnull=True),
                name="unique_document_root",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Document versions are immutable; create a new version")
        return super().save(*args, **kwargs)


class Comparison(Entity):
    old = models.ForeignKey(
        DocumentVersion, related_name="comparisons_from", on_delete=models.PROTECT
    )
    new = models.ForeignKey(
        DocumentVersion, related_name="comparisons_to", on_delete=models.PROTECT
    )
    initiator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    status = models.CharField(
        max_length=20,
        choices=[
            ("queued", "Ожидает"),
            ("processing", "Обрабатывается"),
            ("succeeded", "Готово"),
            ("failed", "Ошибка"),
        ],
        default="queued",
    )
    result = models.JSONField(default=dict)
    error_code = models.CharField(max_length=80, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["old", "new"], name="unique_comparison_versions"
            )
        ]
