from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError
from common.testing import PlatformCase
from invitations.services import cipher
from .services import request_email_change, confirm_email_change


class AccountTests(PlatformCase):
    def test_email_change_requires_password_and_new_mail_code(self):
        with self.assertRaises(ValidationError):
            request_email_change(self.student, "changed@example.test", "bad-password")
        change = request_email_change(
            self.student, "changed@example.test", "Password-123!"
        )
        code = cipher().decrypt(change.encrypted_code.encode()).decode()
        with self.assertRaises(ValidationError):
            confirm_email_change(self.teacher, change.pk, code)
        user = confirm_email_change(self.student, change.pk, code)
        self.assertEqual(user.email, "changed@example.test")
        change.refresh_from_db()
        self.assertEqual(change.encrypted_code, "")
        with self.assertRaises(ValidationError):
            confirm_email_change(self.student, change.pk, code)

    def test_login_csrf_and_session(self):
        c = APIClient(enforce_csrf_checks=True)
        self.assertEqual(
            c.post(
                "/api/login/",
                {"email": self.student.email, "password": "Password-123!"},
                format="json",
            ).status_code,
            403,
        )
        token = c.get("/api/session/").data["csrf"]
        r = c.post(
            "/api/login/",
            {"email": self.student.email, "password": "Password-123!"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["id"], self.student.pk)
        self.assertTrue(c.cookies["sessionid"]["httponly"])
