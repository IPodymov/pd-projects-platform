from datetime import timedelta
from unittest.mock import patch
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from common.testing import PlatformCase
from common.models import Notification
from invitations.models import Invitation, Prospect
from invitations.services import cipher, request_code
from institutions.models import Institution
from rest_framework.test import APIClient
import re


class JourneyClient(APIClient):
    """Exercise the canonical contract, reading revisions before each action."""

    def version(self, path):
        return (
            path.replace("/api/", "/api/v1/", 1)
            if not path.startswith("/api/v1/")
            else path
        )

    def get(self, path, *args, **kwargs):
        response = super().get(self.version(path), *args, **kwargs)
        if (
            hasattr(response, "data")
            and isinstance(response.data, dict)
            and "results" in response.data
        ):
            response.data = response.data["results"]
        return response

    def write(self, method, path, *args, **kwargs):
        path = self.version(path)
        parent = re.search(r"(/api/v1/[^/]+/[0-9a-f-]{36}/)", path)
        if parent:
            current = self.get(parent.group(1))
            if (
                current.status_code == 200
                and hasattr(current, "data")
                and "updated_at" in current.data
            ):
                kwargs["HTTP_IF_MATCH"] = current.data["updated_at"]
        return getattr(super(), method)(path, *args, **kwargs)

    def post(self, path, *args, **kwargs):
        return self.write("post", path, *args, **kwargs)

    def patch(self, path, *args, **kwargs):
        return self.write("patch", path, *args, **kwargs)


class CompleteJourneyTest(PlatformCase):
    def proof(self, inv):
        token = cipher().decrypt(inv.encrypted_token.encode()).decode()
        with patch("invitations.services.queue_mail") as mail:
            request_code(token)
            code = cipher().decrypt(mail.call_args.args[1].encode()).decode()
        return token, code

    def test_ten_steps_via_v1_api(self):
        self.client = JourneyClient()
        self.client.force_authenticate(self.admin)
        r = self.client.post(
            "/api/institutions/",
            {"name": "Новая школа", "kind": "school"},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        school = r.data["id"]
        r = self.client.post(
            "/api/classrooms/",
            {"name": "9А", "academic_year": "2026/2027", "institution": school},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        cl = r.data["id"]
        r = self.client.post(
            "/api/invitations/",
            {
                "email": "journey.teacher@example.test",
                "role": "teacher",
                "institution": school,
                "classroom": cl,
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        inv = Invitation.objects.get(pk=r.data["id"])
        token, code = self.proof(inv)
        self.client.force_authenticate(None)
        r = self.client.post(
            "/api/invitation-accept/",
            {"token": token, "code": code, "password": "JourneyPassword!912"},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.data)
        from accounts.models import User

        teacher = User.objects.get(email=inv.email)
        self.client.force_authenticate(teacher)
        self.assertEqual(
            [c["id"] for c in self.client.get("/api/classrooms/").data], [cl]
        )
        self.client.force_authenticate(self.admin)
        second = self.client.post(
            "/api/classrooms/",
            {"name": "9Б", "academic_year": "2026/2027", "institution": school},
            format="json",
        )
        self.assertEqual(second.status_code, 201, second.data)
        from institutions.models import StaffAssignment

        assignment = StaffAssignment.objects.get(
            user=teacher, institution_id=school, role="teacher"
        )
        added = self.client.post(
            "/api/teaching-assignments/",
            {"staff": str(assignment.pk), "classroom": second.data["id"]},
            format="json",
        )
        self.assertEqual(added.status_code, 201, added.data)
        self.client.force_authenticate(teacher)
        self.assertEqual(len(self.client.get("/api/classrooms/").data), 2)
        r = self.client.post(
            "/api/imports/preview/",
            {
                "classroom": cl,
                "file": SimpleUploadedFile(
                    "students.csv", "ФИО,email\nАлексей,wrong@example.test\n".encode()
                ),
            },
            format="multipart",
        )
        self.assertEqual(r.status_code, 200, r.data)
        r = self.client.post("/api/imports/" + r.data["id"] + "/apply/")
        self.assertEqual(r.status_code, 200, r.data)
        prospect = Prospect.objects.get(email="wrong@example.test")
        old = prospect.invitation_set.get()
        r = self.client.post(
            "/api/prospects/" + str(prospect.pk) + "/correct_email/",
            {"email": "journey.student@example.test"},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.data)
        old.refresh_from_db()
        self.assertEqual(old.status, "revoked")
        r = self.client.get("/api/classrooms/" + cl + "/export/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("no-store", r["Cache-Control"])
        inv = (
            Invitation.objects.get(pk=r.data["id"])
            if hasattr(r, "data")
            else prospect.invitation_set.get(status="pending")
        )
        token, code = self.proof(inv)
        self.client.force_authenticate(None)
        r = self.client.post(
            "/api/invitation-accept/",
            {"token": token, "code": code, "password": "JourneyStudent!912"},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.data)
        student = User.objects.get(email="journey.student@example.test")
        self.client.force_authenticate(student)
        self.assertEqual(len(self.client.get("/api/classrooms/").data), 1)
        self.client.force_authenticate(self.admin)
        r = self.client.post(
            "/api/invitations/",
            {"email": self.curator.email, "role": "curator", "institution": school},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        token, code = self.proof(Invitation.objects.get(pk=r.data["id"]))
        self.client.force_authenticate(self.curator)
        r = self.client.post(
            "/api/invitation-accept/", {"token": token, "code": code}, format="json"
        )
        self.assertEqual(r.status_code, 200, r.data)
        start = timezone.now() + timedelta(days=3)
        r = self.client.post(
            "/api/lessons/",
            {
                "title": "Обучение",
                "classroom": cl,
                "teacher": teacher.pk,
                "curator": self.curator.pk,
                "starts_at": start.isoformat(),
                "ends_at": (start + timedelta(hours=1)).isoformat(),
                "format": "online",
                "online_url": "https://example.test/lesson",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        r = self.client.patch(
            "/api/lessons/" + r.data["id"] + "/",
            {"format": "onsite", "location": "Школа", "room": "101"},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(
            Notification.objects.filter(
                recipient=student, title__startswith="Обновлено"
            ).exists()
        )
        self.client.force_authenticate(self.admin)
        university = Institution.objects.create(name="Вуз", kind="university")
        r = self.client.post(
            "/api/partnerships/",
            {
                "university": str(university.pk),
                "school": school,
                "starts_on": timezone.localdate().isoformat(),
                "ends_on": (timezone.localdate() + timedelta(days=30)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(
            self.client.post(
                "/api/partnerships/" + r.data["id"] + "/transition/",
                {"status": "active"},
                format="json",
            ).status_code,
            200,
        )
        self.client.force_authenticate(teacher)
        self.assertEqual(
            self.client.post(
                "/api/subscriptions/",
                {"school": school, "email_enabled": False},
                format="json",
            ).status_code,
            201,
        )
        self.client.force_authenticate(self.admin)
        r = self.client.post(
            "/api/workshops/",
            {
                "university": str(university.pk),
                "title": "Мастер-класс",
                "description": "Опыт",
                "topic": "Роботы",
                "starts_at": start.isoformat(),
                "ends_at": (start + timedelta(hours=1)).isoformat(),
                "format": "onsite",
                "location": "Лаборатория",
                "capacity": 2,
                "registration_opens_at": timezone.now().isoformat(),
                "registration_closes_at": (start - timedelta(days=1)).isoformat(),
                "audience": "partners",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        w = r.data["id"]
        self.assertEqual(
            self.client.post("/api/workshops/" + w + "/publish/").status_code, 200
        )
        self.client.force_authenticate(teacher)
        self.assertTrue(
            Notification.objects.filter(
                recipient=teacher, title__startswith="Доступен"
            ).exists()
        )
        self.assertEqual(
            self.client.post(
                "/api/workshops/" + w + "/register/",
                {"school": school, "users": [student.pk]},
                format="json",
            ).status_code,
            200,
        )
        r = self.client.post(
            "/api/projects/", {"title": "Проект", "classroom": cl}, format="json"
        )
        self.assertEqual(r.status_code, 201, r.data)
        project = r.data["id"]
        self.assertEqual(
            self.client.post(
                "/api/project-members/",
                {"project": project, "user": student.pk},
                format="json",
            ).status_code,
            201,
        )
        r = self.client.post(
            "/api/tasks/",
            {"project": project, "title": "Работа", "due_at": start.isoformat()},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        task = r.data["id"]
        self.client.force_authenticate(student)
        r = self.client.post(
            "/api/submissions/",
            {"task": task, "text": "Готовый результат"},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        submission = r.data["id"]
        self.client.force_authenticate(teacher)
        self.assertEqual(
            self.client.post(
                "/api/submissions/" + submission + "/review/",
                {"result": "accepted", "feedback": "Принято"},
                format="json",
            ).status_code,
            200,
        )
        # Course lifecycle and immutable correction chain through HTTP.
        self.client.force_authenticate(self.curator)
        course = self.client.post(
            "/api/courses/",
            {"title": "Подготовка", "institution": school},
            format="json",
        )
        self.assertEqual(course.status_code, 201, course.data)
        course_id = course.data["id"]
        assignment = self.client.post(
            "/api/assignments/",
            {
                "course": course_id,
                "title": "Гипотеза",
                "instructions": "Проверка",
                "criteria": "Измерения",
                "due_at": start.isoformat(),
            },
            format="json",
        )
        self.assertEqual(assignment.status_code, 201, assignment.data)
        self.assertEqual(
            self.client.post(
                "/api/courses/" + course_id + "/transition/",
                {"status": "published"},
                format="json",
            ).status_code,
            200,
        )
        self.client.force_authenticate(teacher)
        enrollment = self.client.post(
            "/api/enrollments/",
            {"course": course_id, "classroom": cl, "user": student.pk},
            format="json",
        )
        self.assertEqual(enrollment.status_code, 201, enrollment.data)
        self.client.force_authenticate(student)
        work = self.client.post(
            "/api/course-submissions/",
            {
                "assignment": assignment.data["id"],
                "enrollment": enrollment.data["id"],
                "text": "Гипотеза",
            },
            format="json",
        )
        self.assertEqual(work.status_code, 201, work.data)
        self.assertEqual(
            self.client.post(
                "/api/course-submissions/" + work.data["id"] + "/send/"
            ).status_code,
            200,
        )
        self.client.force_authenticate(teacher)
        self.assertEqual(
            self.client.post(
                "/api/course-submissions/" + work.data["id"] + "/review/",
                {"result": "revision", "feedback": "Добавьте измерения"},
                format="json",
            ).status_code,
            200,
        )
        self.client.force_authenticate(student)
        corrected = self.client.post(
            "/api/course-submissions/",
            {
                "assignment": assignment.data["id"],
                "enrollment": enrollment.data["id"],
                "text": "Измерения",
                "previous": work.data["id"],
            },
            format="json",
        )
        self.assertEqual(corrected.status_code, 201, corrected.data)
        self.assertEqual(
            self.client.post(
                "/api/course-submissions/" + corrected.data["id"] + "/send/"
            ).status_code,
            200,
        )
        self.client.force_authenticate(teacher)
        self.assertEqual(
            self.client.post(
                "/api/course-submissions/" + corrected.data["id"] + "/review/",
                {"result": "accepted", "feedback": ""},
                format="json",
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get("/api/enrollments/" + enrollment.data["id"] + "/").data[
                "progress"
            ],
            100,
        )
        # Document versions and queued comparison; actual worker is tested by smoke_services.
        self.client.force_authenticate(student)
        document = self.client.post(
            "/api/documents/", {"project": project, "title": "Отчёт"}, format="json"
        )
        self.assertEqual(document.status_code, 201, document.data)
        versions = []
        for value in [b"first\nline", b"first\nchanged"]:
            uploaded = self.client.post(
                "/api/documents/" + document.data["id"] + "/upload/",
                {"file": SimpleUploadedFile("report.txt", value)},
                format="multipart",
            )
            self.assertEqual(uploaded.status_code, 201, uploaded.data)
            versions.append(uploaded.data["id"])
        comparison = self.client.post(
            "/api/document-versions/" + versions[0] + "/compare/",
            {"other": versions[1]},
            format="json",
        )
        self.assertEqual(comparison.status_code, 202, comparison.data)
        from documents.tasks import run_comparison

        run_comparison(comparison.data["id"])
        result = self.client.get("/api/comparisons/" + comparison.data["id"] + "/")
        self.assertEqual(result.data["status"], "succeeded")
        self.assertTrue(
            any(line["kind"] == "add" for line in result.data["result"]["lines"])
        )
        self.client.force_authenticate(self.stranger)
        self.assertEqual(
            self.client.get("/api/projects/" + project + "/").status_code, 404
        )
        self.assertEqual(
            self.client.get(
                "/api/document-versions/" + versions[0] + "/download/"
            ).status_code,
            404,
        )
        self.client.force_authenticate(teacher)
        metrics = self.client.get("/api/crm/").data
        self.assertEqual(metrics["learning"]["educationally_active"], 1)
        self.assertEqual(metrics["learning"]["progress_percent"], 100)
        self.assertEqual(metrics["workshops"]["confirmed"], 1)
        self.assertEqual(metrics["learning"]["course_accepted_works"], 1)
        self.assertEqual(metrics["learning"]["course_submitted_works"], 2)
