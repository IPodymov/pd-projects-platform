from django.db import transaction
from .models import AuditEvent, Notification


def audit(actor, action, obj, institution=None, details=None):
    AuditEvent.objects.create(
        actor=actor,
        action=action,
        target=str(obj.pk),
        institution=institution,
        details=details or {},
    )


@transaction.atomic
def notify(users, title, email=True, kind="general", target="", event_key=None):
    import uuid
    from .outbox import enqueue

    event_key = event_key or str(uuid.uuid4())
    for user in {u.pk: u for u in users}.values():
        n, _ = Notification.objects.get_or_create(
            recipient=user,
            event_key=event_key,
            defaults={
                "title": title,
                "kind": kind,
                "target": str(target),
                "delivery_status": "pending" if email else "disabled",
            },
        )
        if email:
            enqueue("notification", {"pk": str(n.pk)}, "notification:" + str(n.pk))
