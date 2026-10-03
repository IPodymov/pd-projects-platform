"""Durable committed jobs; broker delivery is only a best-effort acceleration."""

import logging
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from .models import Outbox


def enqueue(task, payload, key):
    job, _ = Outbox.objects.get_or_create(
        key=key,
        defaults={"task": task, "payload": payload, "available_at": timezone.now()},
    )

    def wake():
        from .tasks import process_outbox

        try:
            process_outbox.delay(str(job.pk))
        except Exception:
            # Do not lose the durable job or report a failed operation after commit.
            logging.getLogger(__name__).warning(
                "Outbox dispatch deferred; periodic dispatcher will retry"
            )

    connection = transaction.get_connection()
    # One broker wake per outer transaction. Beat dispatches all other durable jobs.
    # Avoid N blocking broker connects after a batch import commits.
    if not any(
        getattr(callback, "_outbox_wake", False)
        for _, callback, _ in connection.run_on_commit
    ):
        wake._outbox_wake = True
        transaction.on_commit(wake)
    return job


def execute(pk):
    from .tasks import deliver_notification
    from invitations.tasks import send_invitation
    from documents.tasks import extract_text, run_comparison
    from accounts.tasks import deliver_email_change
    from integrations.tasks import synchronize

    handlers = {
        "git_sync": synchronize,
        "notification": deliver_notification,
        "invitation": send_invitation,
        "extract": extract_text,
        "compare": run_comparison,
        "email_change": deliver_email_change,
    }
    now = timezone.now()
    with transaction.atomic():
        job = Outbox.objects.select_for_update().get(pk=pk)
        if (
            job.status in ("done", "failed")
            or job.available_at > now
            or (
                job.status == "processing"
                and job.locked_until
                and job.locked_until > now
            )
        ):
            return
        job.status = "processing"
        job.attempts += 1
        job.locked_until = now + timedelta(minutes=5)
        job.save()
        task, payload = job.task, job.payload
    try:
        handlers[task](**payload)
    except Exception as exc:
        with transaction.atomic():
            job = Outbox.objects.select_for_update().get(pk=pk)
            job.status = "failed" if job.attempts >= 8 else "pending"
            job.available_at = timezone.now() + timedelta(
                seconds=min(3600, 2**job.attempts * 5)
            )
            job.locked_until = None
            # Exception type only: payloads and provider responses may contain secrets.
            job.last_error = type(exc).__name__
            if job.status == "failed":
                if job.task == "notification":
                    from .models import Notification

                    Notification.objects.filter(
                        pk=job.payload.get("pk"), delivery_status="pending"
                    ).update(delivery_status="failed")
                job.payload = {}
            job.save()
        return
    Outbox.objects.filter(pk=pk).update(
        status="done", payload={}, locked_until=None, last_error=""
    )
