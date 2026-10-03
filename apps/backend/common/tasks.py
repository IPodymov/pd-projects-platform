from celery import shared_task
from django.core.mail import EmailMessage
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.db.models import Q
from .models import Notification, Outbox


@shared_task
def deliver_notification(pk):
    with transaction.atomic():
        n = (
            Notification.objects.select_for_update()
            .select_related("recipient")
            .get(pk=pk)
        )
        if n.delivery_status in ("sent", "disabled"):
            return
        if not n.recipient.is_active:
            n.delivery_status = "disabled"
            n.save(update_fields=["delivery_status", "updated_at"])
            return
        EmailMessage(
            n.title,
            n.title + "\n" + settings.WEB_URL,
            settings.DEFAULT_FROM_EMAIL,
            [n.recipient.email],
            headers={"Message-ID": f"<notification-{n.pk}@platform.local>"},
        ).send()
        n.delivery_status = "sent"
        n.save(update_fields=["delivery_status", "updated_at"])


@shared_task(time_limit=90, soft_time_limit=70)
def process_outbox(pk):
    from .outbox import execute

    execute(pk)


@shared_task
def dispatch_outbox():
    now = timezone.now()
    ids = (
        Outbox.objects.filter(available_at__lte=now)
        .filter(Q(status="pending") | Q(status="processing", locked_until__lte=now))
        .order_by("available_at")
        .values_list("pk", flat=True)[:200]
    )
    for pk in ids:
        process_outbox.delay(str(pk))
