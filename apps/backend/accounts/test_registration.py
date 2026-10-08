from datetime import timedelta
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError
from common.testing import PlatformCase
from common.models import Outbox
from common.outbox import execute
from invitations.services import cipher
from .models import User, RegistrationRequest
from .registration import request_registration, confirm_registration
from .tasks import expire_registrations


class PublicRegistrationTests(PlatformCase):
    def payload(self, **kwargs):
        return {
            "email": "new@example.test",
            "display_name": "Анна Новая",
            "password": "Strong-signup-456!",
            **kwargs,
        }

    def test_csrf_verification_mail_session_and_no_privileges(self):
        client = APIClient(enforce_csrf_checks=True)
        path = "/api/v1/registration/request/"
        self.assertEqual(
            client.post(path, self.payload(), format="json").status_code, 403
        )
        csrf = client.get("/api/v1/session/").data["csrf"]
        response = client.post(
            path,
            self.payload(email="New@Example.Test"),
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(response.status_code, 202, response.data)
        self.assertFalse(User.objects.filter(email__iexact="new@example.test").exists())
        pending = RegistrationRequest.objects.get(pk=response.data["id"])
        self.assertNotEqual(pending.password_hash, self.payload()["password"])
        job = Outbox.objects.get(task="registration")
        self.assertEqual(job.payload, {"pk": str(pending.pk)})
        execute(job.pk)
        self.assertEqual(mail.outbox[-1].to, ["new@example.test"])
        code = cipher().decrypt(pending.encrypted_code.encode()).decode()
        self.assertIn(code, mail.outbox[-1].body)
        response = client.post(
            "/api/v1/registration/confirm/",
            {"id": str(pending.pk), "code": code},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(response.status_code, 200, response.data)
        user = User.objects.get(pk=response.data["id"])
        self.assertTrue(user.check_password(self.payload()["password"]))
        self.assertIsNotNone(user.email_verified_at)
        self.assertEqual(user.email, "new@example.test")
        self.assertFalse(user.is_superuser or user.is_staff)
        self.assertFalse(user.studentmembership_set.exists())
        self.assertEqual(response.data["roles"], [])
        self.assertEqual(client.get("/api/v1/session/").data["id"], user.pk)
        self.assertTrue(client.cookies["sessionid"]["httponly"])
        pending.refresh_from_db()
        self.assertEqual(
            (pending.encrypted_code, pending.code_hash, pending.password_hash),
            ("", "", ""),
        )
        with self.assertRaises(ValidationError):
            confirm_registration(pending.pk, code)

    def test_weak_password_duplicate_email_and_role_injection(self):
        self.client.force_authenticate(user=None)
        path = "/api/v1/registration/request/"
        self.assertEqual(
            self.client.post(
                path, self.payload(password="12345678"), format="json"
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                path, self.payload(email=self.student.email.upper()), format="json"
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                path, self.payload(is_superuser=True), format="json"
            ).status_code,
            400,
        )
        self.assertEqual(RegistrationRequest.objects.count(), 0)
        self.assertEqual(
            self.client.post(
                path,
                self.payload(
                    date_of_birth=(timezone.localdate() + timedelta(days=1)).isoformat()
                ),
                format="json",
            ).status_code,
            400,
        )

    def test_wrong_attempts_persist_cooldown_resend_and_expiry(self):

        pending = request_registration(self.payload())
        previous_code = cipher().decrypt(pending.encrypted_code.encode()).decode()
        wrong = "000000" if previous_code != "000000" else "111111"
        for _ in range(5):
            with self.assertRaises(ValidationError):
                confirm_registration(pending.pk, wrong)
        pending.refresh_from_db()
        self.assertEqual(pending.attempts, 5)
        with self.assertRaises(ValidationError):
            confirm_registration(pending.pk, previous_code)
        with self.assertRaises(ValidationError):
            request_registration(self.payload())
        RegistrationRequest.objects.filter(pk=pending.pk).update(
            updated_at=timezone.now() - timedelta(minutes=2)
        )
        resent = request_registration(self.payload(password="Another-secure-789!"))
        self.assertEqual(resent.pk, pending.pk)
        self.assertEqual(resent.attempts, 0)
        RegistrationRequest.objects.filter(pk=pending.pk).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        expire_registrations()
        pending.refresh_from_db()
        self.assertEqual(pending.password_hash, "")
        with self.assertRaises(ValidationError):
            confirm_registration(
                pending.pk, cipher().decrypt(resent.encrypted_code.encode()).decode()
            )
