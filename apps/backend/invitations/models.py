from django.db import models
from common.models import Entity


class Prospect(Entity):
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    classroom = models.ForeignKey("institutions.Classroom", on_delete=models.PROTECT)
    user = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["email", "classroom"], name="unique_prospect"
            )
        ]


class Invitation(Entity):
    email = models.EmailField()
    institution = models.ForeignKey(
        "institutions.Institution", on_delete=models.PROTECT
    )
    classroom = models.ForeignKey(
        "institutions.Classroom", null=True, blank=True, on_delete=models.PROTECT
    )
    prospect = models.ForeignKey(
        Prospect, null=True, blank=True, on_delete=models.PROTECT
    )
    role = models.CharField(
        max_length=20,
        choices=[
            ("student", "Учащийся"),
            ("teacher", "Преподаватель"),
            ("curator", "Куратор"),
            ("admin", "Администратор учреждения"),
            ("organizer", "Организатор"),
            ("workshop_teacher", "Преподаватель мастер-класса"),
        ],
    )
    token_hash = models.CharField(max_length=64, unique=True)
    encrypted_token = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Ожидает"),
            ("accepted", "Принято"),
            ("revoked", "Отозвано"),
            ("expired", "Истекло"),
        ],
        default="pending",
    )
    expires_at = models.DateTimeField()
    accepted_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT
    )
    code_hash = models.CharField(max_length=64, blank=True)
    code_expires_at = models.DateTimeField(null=True, blank=True)
    code_sent_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    issued_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        related_name="issued_invitations",
        on_delete=models.PROTECT,
    )


class ImportBatch(Entity):
    classroom = models.ForeignKey("institutions.Classroom", on_delete=models.PROTECT)
    actor = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    rows = models.JSONField()
    errors = models.JSONField(default=list)
    applied_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
