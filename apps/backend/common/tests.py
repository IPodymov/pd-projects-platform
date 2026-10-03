# Create your tests here.

from unittest.mock import patch
from django.db import transaction
from django.utils import timezone
from common.testing import PlatformCase
from .models import Outbox, Notification
from .outbox import enqueue, execute
from .services import notify


class OutboxTests(PlatformCase):
    def test_rollback_does_not_leave_notifications_or_jobs(self):
        with self.assertRaises(ValueError):
            with transaction.atomic():
                notify([self.student], "Не должно отправиться", event_key="rollback")
                raise ValueError("abort")
        self.assertEqual(Notification.objects.count(), 0)
        self.assertEqual(Outbox.objects.count(), 0)

    def test_notification_idempotence_and_delivery_retry(self):
        notify([self.student, self.student], "Проверка", event_key="same-event")
        notify([self.student], "Проверка", event_key="same-event")
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(Outbox.objects.count(), 1)
        job = Outbox.objects.get()
        with patch(
            "common.tasks.deliver_notification",
            side_effect=RuntimeError("secret must not be persisted"),
        ):
            execute(job.pk)
        job.refresh_from_db()
        self.assertEqual(job.status, "pending")
        self.assertEqual(job.last_error, "RuntimeError")
        job.available_at = timezone.now()
        job.save()
        with patch("common.tasks.deliver_notification") as handler:
            execute(job.pk)
            execute(job.pk)
            self.assertEqual(handler.call_count, 1)
        job.refresh_from_db()
        self.assertEqual(job.status, "done")
        self.assertEqual(job.payload, {})

    def test_broker_failure_preserves_committed_job(self):
        with patch(
            "common.tasks.process_outbox.delay",
            side_effect=RuntimeError("broker unavailable"),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                job = enqueue("notification", {"pk": "synthetic"}, "durable")
        self.assertEqual(Outbox.objects.get(pk=job.pk).status, "pending")

    def test_batch_notifications_use_one_broker_wake(self):
        with patch("common.tasks.process_outbox.delay") as wake:
            with self.captureOnCommitCallbacks(execute=True):
                with transaction.atomic():
                    notify(
                        [self.student, self.teacher], "Общее событие", event_key="batch"
                    )
            self.assertEqual(wake.call_count, 1)
        self.assertEqual(Outbox.objects.count(), 2)
