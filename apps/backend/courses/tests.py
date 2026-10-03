from datetime import timedelta
from django.utils import timezone
from common.testing import PlatformCase
from common.api import BusinessError
from crm.models import LearningActivity
from institutions.models import StudentMembership, TeachingAssignment
from common.models import Notification
from .models import Course, Assignment, CourseReview
from .services import (
    change_course,
    enroll,
    create_work,
    edit_work,
    send_work,
    review_work,
    progress,
)


class CourseWorkflowTests(PlatformCase):
    def setUp(self):
        super().setUp()
        self.course = Course.objects.create(
            title="Инженерный курс", institution=self.school
        )
        self.assignment = Assignment.objects.create(
            course=self.course,
            title="Прототип",
            instructions="Создать",
            criteria="Работает",
            due_at=timezone.now() + timedelta(days=1),
        )
        change_course(self.curator, self.course, "published")
        self.course.refresh_from_db()
        self.enrollment = enroll(
            self.student, self.course, self.student, self.classroom
        )

    def test_self_enrollment_exposes_only_own_memberships(self):
        other_membership = StudentMembership.objects.create(
            user=self.stranger,
            classroom=self.second,
            started_at=timezone.localdate(),
        )
        self.client.force_authenticate(self.student)
        response = self.client.get("/api/v1/memberships/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(
            str(response.data["results"][0]["classroom"]), str(self.classroom.pk)
        )
        self.assertEqual(
            self.client.get(f"/api/v1/memberships/{other_membership.pk}/").status_code,
            404,
        )
        payload = {
            "course": str(self.course.pk),
            "classroom": str(self.classroom.pk),
            "user": str(self.student.pk),
        }
        response = self.client.post("/api/v1/enrollments/", payload, format="json")
        self.assertIn(response.status_code, (200, 201))
        self.assertEqual(str(response.data["id"]), str(self.enrollment.pk))
        payload["classroom"] = str(self.second.pk)
        response = self.client.post("/api/v1/enrollments/", payload, format="json")
        self.assertIn(response.status_code, (400, 403))

    def test_draft_revision_resubmission_and_completion(self):
        work = create_work(
            self.student,
            {
                "assignment": self.assignment,
                "enrollment": self.enrollment,
                "text": "Черновик",
            },
        )
        self.assertEqual(LearningActivity.objects.count(), 0)
        edit_work(self.student, work, "Первая версия")
        send_work(self.student, work)
        self.assertEqual(progress(self.enrollment), 0)
        review_work(self.teacher, work, "revision", "Добавьте измерения")
        work.refresh_from_db()
        revised = create_work(
            self.student,
            {
                "assignment": self.assignment,
                "enrollment": self.enrollment,
                "text": "С измерениями",
                "previous": work,
            },
        )
        send_work(self.student, revised)
        review_work(self.teacher, revised, "accepted", "Принято")
        self.assertEqual(progress(self.enrollment), 100)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.status, "completed")
        self.assertEqual(CourseReview.objects.count(), 2)
        self.assertEqual(LearningActivity.objects.count(), 2)
        with self.assertRaises(BusinessError):
            review_work(self.teacher, revised, "revision", "Перезапись")
        with self.assertRaises(BusinessError):
            edit_work(self.student, revised, "Мутация")

    def test_submission_does_not_notify_revoked_teacher_assignment(self):
        TeachingAssignment.objects.filter(
            staff=self.staff, classroom=self.classroom
        ).update(active=False)
        work = create_work(
            self.student,
            {
                "assignment": self.assignment,
                "enrollment": self.enrollment,
                "text": "Готовая работа",
            },
        )
        send_work(self.student, work)
        self.assertFalse(Notification.objects.filter(kind="course.submitted").exists())
        self.assertTrue(
            TeachingAssignment.objects.filter(
                staff=self.staff, classroom=self.second, active=True
            ).exists()
        )

    def test_repeat_enrollment_and_foreign_scope(self):
        self.assertEqual(
            enroll(self.student, self.course, self.student, self.classroom).pk,
            self.enrollment.pk,
        )
        self.client.force_authenticate(self.stranger)
        self.assertEqual(
            self.client.get(f"/api/v1/enrollments/{self.enrollment.pk}/").status_code,
            404,
        )
        self.client.force_authenticate(self.student)
        response = self.client.post(
            "/api/v1/course-submissions/",
            {
                "assignment": str(self.assignment.pk),
                "enrollment": str(self.enrollment.pk),
                "text": "Подмена",
                "status": "accepted",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("status", response.data["fields"])
