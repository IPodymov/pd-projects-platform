from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import timedelta
from unittest import skipUnless
from unittest.mock import patch
from django.test import TransactionTestCase
from django.db import connection, close_old_connections
from django.utils import timezone
from common.testing import PlatformCase
from institutions.models import Institution
from workshops.models import Workshop
from workshops.services import register
from invitations.models import Prospect
from invitations import services


@skipUnless(
    connection.vendor == "postgresql",
    "Row-lock concurrency requires PostgreSQL; run make test-postgres",
)
class ConcurrentTests(TransactionTestCase):
    def setUp(self):
        PlatformCase.setUp(self)

    def test_last_place_under_parallel_requests(self):
        uni = Institution.objects.create(name="Вуз", kind="university")
        w = Workshop.objects.create(
            university=uni,
            organizer=self.admin,
            title="Практика",
            description="Практика",
            topic="Роботы",
            starts_at=timezone.now() + timedelta(days=3),
            ends_at=timezone.now() + timedelta(days=3, hours=1),
            format="onsite",
            location="Лаборатория",
            capacity=1,
            registration_opens_at=timezone.now() - timedelta(days=1),
            registration_closes_at=timezone.now() + timedelta(days=1),
            audience="all",
            published=True,
        )
        barrier = Barrier(2)

        def action(u):
            close_old_connections()
            barrier.wait()
            try:
                return register(u, w)[0].status
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(action, [self.student, self.teacher]))
        self.assertEqual(sorted(result), ["confirmed", "waiting"])
        self.assertEqual(w.registrations.filter(status="confirmed").count(), 1)

    def test_parallel_invitation_single_acceptance(self):
        p = Prospect.objects.create(
            full_name="Новый", email="parallel@example.test", classroom=self.classroom
        )
        with patch("invitations.services.queue_mail"):
            inv = services.issue(
                self.teacher, self.school, p.email, "student", self.classroom, p
            )
            token = services.cipher().decrypt(inv.encrypted_token.encode()).decode()
            with patch("invitations.services.queue_mail") as mail:
                services.request_code(token)
                code = (
                    services.cipher().decrypt(mail.call_args.args[1].encode()).decode()
                )
        barrier = Barrier(2)

        def action(_):
            from rest_framework.exceptions import ValidationError

            close_old_connections()
            barrier.wait()
            try:
                services.accept(token, code, "SecurePassword!291")
                return "accepted"
            except ValidationError:
                return "rejected"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(action, [1, 2]))
        self.assertEqual(sorted(result), ["accepted", "rejected"])

    def test_parallel_enrollment_is_idempotent(self):
        from courses.models import Course, Enrollment
        from courses.services import enroll

        course = Course.objects.create(
            title="Курс", institution=self.school, status="published"
        )
        barrier = Barrier(2)

        def action(_):
            close_old_connections()
            barrier.wait()
            try:
                return enroll(self.student, course, self.student, self.classroom).pk
            finally:
                close_old_connections()

        with (
            patch("common.tasks.process_outbox.delay"),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            result = list(pool.map(action, [1, 2]))
        self.assertEqual(result[0], result[1])
        self.assertEqual(
            Enrollment.objects.filter(course=course, user=self.student).count(), 1
        )

    def test_parallel_review_keeps_one_immutable_decision(self):
        from courses.models import (
            Course,
            Enrollment,
            Assignment,
            CourseSubmission,
            CourseReview,
        )
        from courses.services import review_work
        from common.api import BusinessError

        course = Course.objects.create(
            title="Курс", institution=self.school, status="published"
        )
        enrollment = Enrollment.objects.create(
            course=course, user=self.student, classroom=self.classroom
        )
        task = Assignment.objects.create(
            course=course,
            title="Работа",
            instructions="Описание",
            criteria="Критерии",
            due_at=timezone.now(),
        )
        work = CourseSubmission.objects.create(
            assignment=task, enrollment=enrollment, text="Результат", status="submitted"
        )
        barrier = Barrier(2)

        def action(result):
            close_old_connections()
            barrier.wait()
            try:
                review_work(self.teacher, work, result, "Замечание")
                return "reviewed"
            except BusinessError:
                return "conflict"
            finally:
                close_old_connections()

        with (
            patch("common.tasks.process_outbox.delay"),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            result = list(pool.map(action, ["accepted", "revision"]))
        self.assertEqual(sorted(result), ["conflict", "reviewed"])
        self.assertEqual(CourseReview.objects.filter(submission=work).count(), 1)

    def test_parallel_document_versions_form_one_chain(self):
        from projects.models import Project, ProjectMember
        from documents.models import Document, DocumentVersion
        from documents.services import upload_version
        from django.core.files.uploadedfile import SimpleUploadedFile

        project = Project.objects.create(title="Проект", classroom=self.classroom)
        ProjectMember.objects.create(project=project, user=self.student)
        document = Document.objects.create(title="Файл", project=project)
        barrier = Barrier(2)

        def action(value):
            close_old_connections()
            barrier.wait()
            try:
                return upload_version(
                    self.student,
                    document,
                    SimpleUploadedFile("test.txt", value.encode()),
                ).pk
            finally:
                close_old_connections()

        with (
            patch("common.tasks.process_outbox.delay"),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            result = list(pool.map(action, ["one", "two"]))
        versions = list(
            DocumentVersion.objects.filter(pk__in=result).order_by("created_at")
        )
        self.assertIsNone(versions[0].previous_id)
        self.assertEqual(versions[1].previous_id, versions[0].pk)
