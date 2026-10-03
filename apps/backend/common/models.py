import uuid
from django.db import models
from django.conf import settings


class Entity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AuditEvent(Entity):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    action = models.CharField(max_length=80)
    target = models.CharField(max_length=100)
    institution = models.ForeignKey(
        "institutions.Institution", null=True, on_delete=models.SET_NULL
    )
    # Only explicitly selected non-secret metadata; never request payloads.
    details = models.JSONField(default=dict)


class Notification(Entity):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    read_at = models.DateTimeField(null=True, blank=True)
    kind = models.CharField(max_length=80, default="general")
    event_key = models.CharField(max_length=200, null=True, blank=True)
    target = models.CharField(max_length=100, blank=True)
    delivery_status = models.CharField(max_length=20, default="pending")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["event_key", "recipient"], name="unique_notification_event"
            )
        ]


class Outbox(Entity):
    key = models.CharField(max_length=200, unique=True)
    task = models.CharField(max_length=100)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=20, default="pending")
    attempts = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField()
    locked_until = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=100, blank=True)


class SeedReceipt(models.Model):
    key = models.CharField(max_length=200, primary_key=True)
    fingerprint = models.CharField(max_length=64)
