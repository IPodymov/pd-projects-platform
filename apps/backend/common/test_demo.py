from io import StringIO
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from accounts.models import User
from institutions.models import Classroom
from courses.models import CourseSubmission
from workshops.models import Workshop
from invitations.models import Invitation
from crm.models import LearningActivity


class DemoDataTests(TestCase):
    def test_production_or_test_settings_reject_demo(self):
        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            call_command("demo_data", stdout=StringIO())
        self.assertEqual(User.objects.count(), 0)

    @override_settings(DEBUG=True)
    def test_repeated_seed_preserves_passwords_work_and_invites(self):
        output = StringIO()
        call_command("demo_data", stdout=output)
        self.assertIn("DEV ONLY", output.getvalue())
        student = User.objects.get(username="demo-student")
        password = student.password
        counts = [
            model.objects.count()
            for model in (
                User,
                Classroom,
                CourseSubmission,
                Workshop,
                Invitation,
                LearningActivity,
            )
        ]
        self.assertEqual(Workshop.objects.count(), 2)
        self.assertTrue(CourseSubmission.objects.filter(status="accepted").exists())
        self.assertGreater(LearningActivity.objects.count(), 0)
        call_command("demo_data", stdout=StringIO())
        student.refresh_from_db()
        self.assertEqual(student.password, password)
        self.assertEqual(
            counts,
            [
                model.objects.count()
                for model in (
                    User,
                    Classroom,
                    CourseSubmission,
                    Workshop,
                    Invitation,
                    LearningActivity,
                )
            ],
        )
        call_command("demo_data", reset_passwords=True, stdout=StringIO())
        student.refresh_from_db()
        self.assertNotEqual(student.password, password)
        self.assertEqual(
            counts,
            [
                model.objects.count()
                for model in (
                    User,
                    Classroom,
                    CourseSubmission,
                    Workshop,
                    Invitation,
                    LearningActivity,
                )
            ],
        )
