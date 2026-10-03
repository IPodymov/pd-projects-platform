from datetime import timedelta
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from common.testing import PlatformCase
from common.models import Notification
from institutions.models import Institution
from .models import Workshop, Partnership, Subscription, Registration
from .services import register, cancel, visible, announce


class WorkshopTests(PlatformCase):
    def setUp(self):
        super().setUp()
        self.university = Institution.objects.create(name="Вуз", kind="university")
        self.workshop = Workshop.objects.create(
            university=self.university,
            organizer=self.admin,
            title="Робототехника",
            description="Практика",
            topic="Роботы",
            starts_at=timezone.now() + timedelta(days=3),
            ends_at=timezone.now() + timedelta(days=3, hours=1),
            format="onsite",
            location="Лаборатория 1",
            capacity=1,
            registration_opens_at=timezone.now() - timedelta(days=1),
            registration_closes_at=timezone.now() + timedelta(days=1),
            audience="partners",
            published=True,
        )
        Partnership.objects.create(
            university=self.university,
            school=self.school,
            status="active",
            starts_on=timezone.localdate(),
            ends_on=timezone.localdate() + timedelta(days=30),
        )

    def test_visibility_partners_and_selected(self):
        self.assertTrue(visible(self.teacher).filter(pk=self.workshop.pk).exists())
        self.assertFalse(visible(self.stranger).filter(pk=self.workshop.pk).exists())
        self.workshop.audience = "selected"
        self.workshop.save()
        self.workshop.schools.add(self.other)
        self.assertFalse(visible(self.teacher).filter(pk=self.workshop.pk).exists())
        self.workshop.schools.add(self.school)
        self.assertTrue(visible(self.teacher).filter(pk=self.workshop.pk).exists())

    def test_capacity_waitlist_and_no_double_count(self):
        first = register(self.student, self.workshop)[0]
        second = register(self.teacher, self.workshop)[0]
        self.assertEqual(first.status, "confirmed")
        self.assertEqual(second.status, "waiting")
        with self.assertRaises(ValidationError):
            register(self.teacher, self.workshop, [self.student], self.school)
        self.assertEqual(Registration.objects.filter(workshop=self.workshop).count(), 2)
        cancel(self.student, first)
        second.refresh_from_db()
        self.assertEqual(second.status, "confirmed")

    def test_group_request_requires_class_scope(self):
        with self.assertRaises(PermissionDenied):
            register(self.stranger, self.workshop, [self.student], self.school)
        self.assertEqual(
            register(self.teacher, self.workshop, [self.student], self.school)[
                0
            ].group.responsible,
            self.teacher,
        )

    def test_subscriber_notifications_never_broadcast_to_students(self):
        Subscription.objects.create(
            user=self.teacher, school=self.school, email_enabled=False
        )
        announce(self.admin, self.workshop)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.teacher, title__startswith="Доступен"
            ).exists()
        )
        self.assertFalse(
            Notification.objects.filter(
                recipient=self.student, title__startswith="Доступен"
            ).exists()
        )

    def test_workshop_change_scope_and_registered_notification(self):
        from .services import update_workshop

        register(self.student, self.workshop)
        with self.assertRaises(PermissionDenied):
            update_workshop(self.teacher, self.workshop, {"location": "Другое место"})
        update_workshop(self.admin, self.workshop, {"location": "Аудитория 2"})
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.student, title__startswith="Изменён"
            ).exists()
        )

    def test_age_privacy_group_cancel_and_notification_dedup(self):
        from datetime import date
        from .services import cancel_group

        self.workshop.min_age = 13
        self.workshop.max_age = 18
        self.workshop.online_url = "https://example.test/private"
        self.workshop.save()
        with self.assertRaises(ValidationError):
            register(self.student, self.workshop)
        self.student.date_of_birth = date(2011, 1, 1)
        self.student.save()
        registration = register(
            self.teacher, self.workshop, [self.student], self.school
        )[0]
        cancel_group(self.teacher, registration.group)
        registration.refresh_from_db()
        self.assertEqual(registration.status, "cancelled")
        self.client.force_authenticate(self.teacher)
        self.assertEqual(
            self.client.get(f"/api/v1/workshops/{self.workshop.pk}/").data[
                "online_url"
            ],
            "",
        )
        Subscription.objects.create(
            user=self.teacher, school=self.school, email_enabled=False
        )
        announce(self.admin, self.workshop)
        announce(self.admin, self.workshop)
        self.assertEqual(
            Notification.objects.filter(
                kind="workshop.published", recipient=self.teacher
            ).count(),
            1,
        )
