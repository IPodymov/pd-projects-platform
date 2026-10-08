from django.utils import timezone
from common.testing import PlatformCase
from common.models import AuditEvent
from institutions.models import StaffAssignment, StudentMembership
from courses.models import Course, Enrollment
from projects.models import Project, ProjectMember
from .models import User


class AccountManagementTests(PlatformCase):
    def setUp(self):
        super().setUp()
        self.school_admin = User.objects.create_user(
            "school_admin", "admin-school@example.test", "Password-123!"
        )
        StaffAssignment.objects.create(
            user=self.school_admin, institution=self.school, role="admin"
        )
        self.course = Course.objects.create(
            title="Курс", institution=self.school, status="published"
        )
        self.project = Project.objects.create(title="Проект", classroom=self.classroom)
        self.client.force_authenticate(self.school_admin)

    def revision(self, user=None):
        user = user or self.student
        return self.client.get(f"/api/v1/users/{user.pk}/").data["updated_at"]

    def action(self, action, payload, user=None, revision=None):
        user = user or self.student
        return self.client.post(
            f"/api/v1/users/{user.pk}/{action}/",
            payload,
            format="json",
            HTTP_IF_MATCH=revision or self.revision(user),
        )

    def test_account_list_scoped_and_no_privilege_escalation(self):
        StudentMembership.objects.create(
            user=self.stranger, classroom=self.foreign, started_at=timezone.localdate()
        )
        ids = {user["id"] for user in self.client.get("/api/v1/users/").data["results"]}
        self.assertIn(self.student.pk, ids)
        self.assertNotIn(self.stranger.pk, ids)
        self.assertNotIn(self.admin.pk, ids)
        self.assertEqual(
            self.client.get(f"/api/v1/users/{self.stranger.pk}/").status_code, 404
        )
        response = self.client.patch(
            f"/api/v1/users/{self.student.pk}/",
            {"is_superuser": True},
            format="json",
            HTTP_IF_MATCH=self.revision(),
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(
            f"/api/v1/users/{self.student.pk}/",
            {"is_active": False},
            format="json",
            HTTP_IF_MATCH=self.revision(),
        )
        self.assertEqual(response.status_code, 403)
        for role in [self.teacher, self.curator, self.student]:
            self.client.force_authenticate(role)
            self.assertEqual(self.client.get("/api/v1/users/").status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(
            self.client.get(f"/api/v1/users/{self.stranger.pk}/").status_code, 200
        )

    def test_profile_revision_and_foreign_relations(self):
        path = f"/api/v1/users/{self.student.pk}/"
        self.assertEqual(
            self.client.patch(path, {"display_name": "Имя"}, format="json").status_code,
            428,
        )
        revision = self.revision()
        response = self.client.patch(
            path, {"display_name": "Новое имя"}, format="json", HTTP_IF_MATCH=revision
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            self.client.patch(
                path,
                {"display_name": "Старое имя"},
                format="json",
                HTTP_IF_MATCH=revision,
            ).status_code,
            409,
        )
        self.assertEqual(
            self.action("set_class", {"classroom": str(self.foreign.pk)}).status_code,
            403,
        )
        foreign_course = Course.objects.create(
            title="Чужой курс", institution=self.other, status="published"
        )
        self.assertEqual(
            self.action(
                "add_course",
                {"course": str(foreign_course.pk), "classroom": str(self.classroom.pk)},
            ).status_code,
            403,
        )
        foreign_project = Project.objects.create(
            title="Чужой проект", classroom=self.foreign
        )
        self.assertEqual(
            self.action(
                "add_project", {"project": str(foreign_project.pk)}
            ).status_code,
            403,
        )
        self.student.refresh_from_db()
        self.assertEqual(self.student.display_name, "Новое имя")

    def test_enrollment_project_and_creation_are_idempotent_and_atomic(self):
        response = self.action(
            "add_course",
            {"course": str(self.course.pk), "classroom": str(self.classroom.pk)},
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            self.action(
                "add_course",
                {"course": str(self.course.pk), "classroom": str(self.classroom.pk)},
            ).status_code,
            200,
        )
        self.assertEqual(Enrollment.objects.filter(user=self.student).count(), 1)
        response = self.action(
            "add_project", {"project": str(self.project.pk), "role": "leader"}
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            self.action("add_project", {"project": str(self.project.pk)}).status_code,
            200,
        )
        self.assertEqual(
            ProjectMember.objects.get(project=self.project, user=self.student).role,
            "leader",
        )
        response = self.action(
            "create_project",
            {"title": "Личный проект", "classroom": str(self.classroom.pk)},
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(
            Project.objects.filter(title="Личный проект", members=self.student).exists()
        )
        count = Project.objects.count()
        response = self.action(
            "create_project",
            {"title": "Неверный класс", "classroom": str(self.second.pk)},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Project.objects.count(), count)
        self.assertTrue(
            AuditEvent.objects.filter(action="project.member_added").exists()
        )

    def test_transfer_keeps_history_and_moves_active_enrollments(self):
        membership = StudentMembership.objects.get(
            user=self.student, classroom=self.classroom
        )
        enrollment = Enrollment.objects.create(
            user=self.student, course=self.course, classroom=self.classroom
        )
        ProjectMember.objects.create(project=self.project, user=self.student)
        response = self.action(
            "set_class",
            {"membership": str(membership.pk), "classroom": str(self.second.pk)},
        )
        self.assertEqual(response.status_code, 200, response.data)
        membership.refresh_from_db()
        enrollment.refresh_from_db()
        self.assertIsNotNone(membership.ended_at)
        self.assertEqual(enrollment.classroom, self.second)
        self.assertTrue(
            StudentMembership.objects.filter(
                user=self.student, classroom=self.second, ended_at__isnull=True
            ).exists()
        )
        self.assertTrue(
            ProjectMember.objects.filter(
                user=self.student, project=self.project
            ).exists()
        )

    def test_add_confirmed_unassigned_student_then_manage(self):
        user = User.objects.create_user(
            "new", "new@example.test", "Password-123!", email_verified_at=timezone.now()
        )
        self.assertEqual(self.client.get(f"/api/v1/users/{user.pk}/").status_code, 404)
        response = self.client.post(
            "/api/v1/users/add_student/",
            {"email": user.email.upper(), "classroom": str(self.classroom.pk)},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.client.get(f"/api/v1/users/{user.pk}/").status_code, 200)
        self.assertEqual(
            self.client.post(
                "/api/v1/users/add_student/",
                {"email": user.email, "classroom": str(self.classroom.pk)},
                format="json",
            ).status_code,
            200,
        )
        self.assertEqual(StudentMembership.objects.filter(user=user).count(), 1)
        StudentMembership.objects.create(
            user=self.stranger, classroom=self.foreign, started_at=timezone.localdate()
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/users/add_student/",
                {"email": self.stranger.email, "classroom": str(self.classroom.pk)},
                format="json",
            ).status_code,
            403,
        )

    def test_platform_can_disable_regular_accounts(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            f"/api/v1/users/{self.student.pk}/",
            {"is_active": False},
            format="json",
            HTTP_IF_MATCH=self.revision(),
        )
        self.assertEqual(response.status_code, 200)
        response = self.action("add_project", {"project": str(self.project.pk)})
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(
            f"/api/v1/users/{self.admin.pk}/",
            {"is_active": False},
            format="json",
            HTTP_IF_MATCH=self.revision(self.admin),
        )
        self.assertEqual(response.status_code, 400)

    def test_signup_to_class_course_project_with_real_student_session(self):
        from rest_framework.test import APIClient
        from invitations.services import cipher
        from .models import RegistrationRequest

        student_client = APIClient(enforce_csrf_checks=True)
        csrf = student_client.get("/api/v1/session/").data["csrf"]
        response = student_client.post(
            "/api/v1/registration/request/",
            {
                "email": "journey@example.test",
                "display_name": "Новый ученик",
                "password": "Secure-journey-123!",
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(response.status_code, 202, response.data)
        pending = RegistrationRequest.objects.get(pk=response.data["id"])
        code = cipher().decrypt(pending.encrypted_code.encode()).decode()
        response = student_client.post(
            "/api/v1/registration/confirm/",
            {"id": str(pending.pk), "code": code},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(response.status_code, 200, response.data)
        user = User.objects.get(pk=response.data["id"])
        self.assertEqual(
            student_client.get(f"/api/v1/projects/{self.project.pk}/").status_code, 404
        )
        response = self.client.post(
            "/api/v1/users/add_student/",
            {"email": user.email, "classroom": str(self.classroom.pk)},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            self.action(
                "add_course",
                {"course": str(self.course.pk), "classroom": str(self.classroom.pk)},
                user=user,
            ).status_code,
            200,
        )
        self.assertEqual(
            self.action(
                "add_project", {"project": str(self.project.pk)}, user=user
            ).status_code,
            200,
        )
        enrollments = student_client.get("/api/v1/enrollments/").data["results"]
        self.assertEqual(len(enrollments), 1)
        self.assertEqual(str(enrollments[0]["course"]), str(self.course.pk))
        self.assertEqual(
            student_client.get(f"/api/v1/projects/{self.project.pk}/").status_code, 200
        )
        csrf = student_client.get("/api/v1/session/").data["csrf"]
        response = student_client.post(
            "/api/v1/documents/",
            {"title": "Мой материал", "project": str(self.project.pk)},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(response.status_code, 201, response.data)

    def test_assignment_revision_is_required_and_stale_actions_do_not_modify(self):
        path = f"/api/v1/users/{self.student.pk}/add_project/"
        self.assertEqual(
            self.client.post(
                path, {"project": str(self.project.pk)}, format="json"
            ).status_code,
            428,
        )
        revision = self.revision()
        self.assertEqual(
            self.action(
                "add_course",
                {"course": str(self.course.pk), "classroom": str(self.classroom.pk)},
            ).status_code,
            200,
        )
        response = self.action(
            "add_project", {"project": str(self.project.pk)}, revision=revision
        )
        self.assertEqual(response.status_code, 409)
        self.assertFalse(
            ProjectMember.objects.filter(
                user=self.student, project=self.project
            ).exists()
        )
