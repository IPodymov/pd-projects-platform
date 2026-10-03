import io
from unittest.mock import patch
from datetime import timedelta
from openpyxl import load_workbook
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.exceptions import ValidationError, PermissionDenied
from accounts.models import User
from common.testing import PlatformCase
from common.models import AuditEvent
from institutions.models import StudentMembership
from .models import Prospect
from . import services


class InvitationTests(PlatformCase):
    def invite(self, email="new@example.test"):
        p = Prospect.objects.create(
            full_name="Новый ученик", email=email, classroom=self.classroom
        )
        inv = services.issue(
            self.teacher, self.school, email, "student", self.classroom, p
        )
        token = services.cipher().decrypt(inv.encrypted_token.encode()).decode()
        return p, inv, token

    def code(self, token):
        with patch("invitations.services.queue_mail") as mail:
            services.request_code(token)
            return services.cipher().decrypt(mail.call_args.args[1].encode()).decode()

    def test_link_alone_or_wrong_code_is_insufficient(self):
        _, inv, token = self.invite()
        with self.assertRaises(ValidationError):
            services.accept(token, "000000", "SecurePassword!291")
        inv.refresh_from_db()
        self.assertEqual(inv.attempts, 1)
        self.assertFalse(User.objects.filter(email=inv.email).exists())

    def test_email_proof_password_and_single_use(self):
        p, inv, token = self.invite()
        code = self.code(token)
        user = services.accept(token, code, "SecurePassword!291")
        self.assertIsNotNone(user.email_verified_at)
        self.assertTrue(
            StudentMembership.objects.filter(
                user=user, classroom=self.classroom
            ).exists()
        )
        inv.refresh_from_db()
        self.assertEqual(inv.encrypted_token, "")
        with self.assertRaises(ValidationError):
            services.accept(token, code, "OtherPassword!89")

    def test_correct_email_revokes_old_link_and_codes(self):
        p, inv, token = self.invite()
        code = self.code(token)
        new = services.correct_email(self.teacher, p, "fixed@example.test")
        inv.refresh_from_db()
        self.assertEqual(inv.status, "revoked")
        self.assertEqual(inv.code_hash, "")
        self.assertEqual(new.email, "fixed@example.test")
        with self.assertRaises(ValidationError):
            services.accept(token, code, "SecurePassword!291")
        self.assertTrue(
            AuditEvent.objects.filter(action="prospect.email_changed").exists()
        )

    def test_expiry_and_attempt_limit(self):
        _, inv, token = self.invite()
        inv.expires_at = timezone.now() - timedelta(seconds=1)
        inv.save()
        with self.assertRaises(ValidationError):
            services.request_code(token)
        services.expire()
        inv.refresh_from_db()
        self.assertEqual(inv.encrypted_token, "")

    def test_existing_account_must_login_and_password_unchanged(self):
        _, inv, token = self.invite("student@example.test")
        code = self.code(token)
        old = self.student.password
        with self.assertRaises(PermissionDenied):
            services.accept(token, code, "new-password")
        u = services.accept(token, code, "new-password", self.student)
        self.assertEqual(u.pk, self.student.pk)
        self.assertEqual(u.password, old)

    def test_registered_email_cannot_be_corrected_by_teacher(self):
        p, inv, token = self.invite()
        services.accept(token, self.code(token), "SecurePassword!291")
        p.refresh_from_db()
        with self.assertRaises(ValidationError):
            services.correct_email(self.teacher, p, "other@example.test")

    def test_import_preview_apply_idempotence_and_conflicts(self):
        def file():
            return SimpleUploadedFile(
                "students.csv", "ФИО,email\nИван Иванов,ivan@example.test\n".encode()
            )

        batch = services.preview_import(self.teacher, self.classroom, file())
        self.assertEqual(batch.errors, [])
        self.assertEqual(services.apply_import(self.teacher, batch)["created"], 1)
        self.assertEqual(services.apply_import(self.teacher, batch)["created"], 0)
        batch2 = services.preview_import(self.teacher, self.classroom, file())
        self.assertEqual(services.apply_import(self.teacher, batch2)["skipped"], 1)
        conflict = services.preview_import(
            self.teacher,
            self.classroom,
            SimpleUploadedFile(
                "x.csv", "ФИО,email\nДругое ФИО,ivan@example.test\n".encode()
            ),
        )
        self.assertEqual(conflict.errors[0]["row"], 2)
        with self.assertRaises(ValidationError):
            services.apply_import(self.teacher, conflict)

    def test_duplicate_file_and_registered_conflict(self):
        b = services.preview_import(
            self.teacher,
            self.classroom,
            SimpleUploadedFile(
                "x.csv",
                "ФИО,email\nA,student@example.test\nB,student@example.test\n".encode(),
            ),
        )
        self.assertEqual(len(b.errors), 2)

    def test_export_permissions_formula_safety_and_expired_link(self):
        p, inv, token = self.invite()
        p.full_name = '=HYPERLINK("bad")'
        p.save()
        data = services.export_class(self.teacher, self.classroom)
        row = list(load_workbook(io.BytesIO(data)).active.values)[1]
        self.assertTrue(row[0].startswith("'="))
        self.assertIn("#", row[2])
        self.assertNotIn(token, inv.token_hash)
        with self.assertRaises(PermissionDenied):
            services.export_class(self.stranger, self.classroom)
        inv.expires_at = timezone.now() - timedelta(seconds=1)
        inv.save()
        row = list(
            load_workbook(
                io.BytesIO(services.export_class(self.teacher, self.classroom))
            ).active.values
        )[1]
        self.assertIsNone(row[2])

    def test_foreign_import_forbidden(self):
        with self.assertRaises(PermissionDenied):
            services.preview_import(
                self.teacher, self.foreign, SimpleUploadedFile("x.csv", b"")
            )
