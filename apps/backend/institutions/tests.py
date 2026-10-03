from common.testing import PlatformCase
from .models import StaffAssignment


class AccessTests(PlatformCase):
    def test_teacher_sees_two_assigned_classes_only(self):
        r = self.client.get("/api/classrooms/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            {x["id"] for x in r.data}, {str(self.classroom.pk), str(self.second.pk)}
        )
        self.assertEqual(
            self.client.get(
                "/api/classrooms/" + str(self.private.pk) + "/"
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                "/api/classrooms/" + str(self.foreign.pk) + "/"
            ).status_code,
            404,
        )

    def test_institution_admin_isolation_and_no_escalation(self):
        StaffAssignment.objects.create(
            user=self.stranger, institution=self.school, role="admin"
        )
        self.client.force_authenticate(self.stranger)
        self.assertEqual(
            self.client.patch(
                "/api/institutions/" + str(self.other.pk) + "/", {"name": "hacked"}
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                "/api/invitations/",
                {
                    "email": "x@example.test",
                    "institution": str(self.school.pk),
                    "role": "admin",
                },
                format="json",
            ).status_code,
            403,
        )

    def test_curator_can_cover_multiple_institutions(self):
        StaffAssignment.objects.create(
            user=self.curator, institution=self.other, role="curator"
        )
        self.client.force_authenticate(self.curator)
        self.assertEqual(len(self.client.get("/api/classrooms/").data), 4)

    def test_teacher_cannot_assign_other_teacher(self):
        r = self.client.post(
            "/api/teaching-assignments/",
            {"staff": str(self.staff.pk), "classroom": str(self.private.pk)},
            format="json",
        )
        self.assertEqual(r.status_code, 403)

    def test_anonymous_cannot_access_crm(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/crm/").status_code, 401)

    def test_revoked_class_assignment_and_transfer_history(self):
        from institutions.models import TeachingAssignment, StudentMembership
        from .services import set_teaching_active, transfer_student

        assignment = TeachingAssignment.objects.get(
            staff=self.staff, classroom=self.classroom
        )
        set_teaching_active(self.admin, assignment, False)
        self.assertEqual(
            self.client.get(
                "/api/v1/classrooms/" + str(self.classroom.pk) + "/"
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                "/api/v1/classrooms/" + str(self.second.pk) + "/"
            ).status_code,
            200,
        )
        membership = StudentMembership.objects.get(user=self.student)
        moved = transfer_student(self.admin, membership, self.second)
        membership.refresh_from_db()
        self.assertIsNotNone(membership.ended_at)
        self.assertEqual(moved.classroom, self.second)
        self.assertEqual(StudentMembership.objects.filter(user=self.student).count(), 2)

    def test_v1_stale_form_and_pagination(self):
        self.client.force_authenticate(self.admin)
        url = f"/api/v1/classrooms/{self.classroom.pk}/"
        revision = self.client.get(url).data["updated_at"]
        self.assertEqual(
            self.client.patch(url, {"name": "10Б"}, format="json").status_code, 428
        )
        self.assertEqual(
            self.client.patch(
                url, {"name": "10Б"}, format="json", HTTP_IF_MATCH=revision
            ).status_code,
            200,
        )
        response = self.client.patch(
            url, {"name": "Перезапись"}, format="json", HTTP_IF_MATCH=revision
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "stale_revision")
        listing = self.client.get("/api/v1/classrooms/?page_size=1")
        self.assertEqual(listing.data["count"], 4)
        self.assertEqual(len(listing.data["results"]), 1)
        self.assertIsNotNone(listing.data["next"])
