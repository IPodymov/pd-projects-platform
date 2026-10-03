from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from accounts.models import User
from institutions.models import (
    Institution,
    Classroom,
    StaffAssignment,
    TeachingAssignment,
    StudentMembership,
)


class PlatformCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            "platform", "platform@example.test", "Password-123!"
        )
        self.teacher = User.objects.create_user(
            "teacher", "teacher@example.test", "Password-123!"
        )
        self.curator = User.objects.create_user(
            "curator", "curator@example.test", "Password-123!"
        )
        self.student = User.objects.create_user(
            "student", "student@example.test", "Password-123!"
        )
        self.stranger = User.objects.create_user(
            "stranger", "stranger@example.test", "Password-123!"
        )
        self.school = Institution.objects.create(name="Школа А", kind="school")
        self.other = Institution.objects.create(name="Школа Б", kind="school")
        self.classroom = Classroom.objects.create(
            institution=self.school, name="9А", academic_year="2026/2027"
        )
        self.second = Classroom.objects.create(
            institution=self.school, name="9Б", academic_year="2026/2027"
        )
        self.private = Classroom.objects.create(
            institution=self.school, name="10А", academic_year="2026/2027"
        )
        self.foreign = Classroom.objects.create(
            institution=self.other, name="9А", academic_year="2026/2027"
        )
        self.staff = StaffAssignment.objects.create(
            user=self.teacher, institution=self.school, role="teacher"
        )
        TeachingAssignment.objects.create(staff=self.staff, classroom=self.classroom)
        TeachingAssignment.objects.create(staff=self.staff, classroom=self.second)
        StaffAssignment.objects.create(
            user=self.curator, institution=self.school, role="curator"
        )
        StudentMembership.objects.create(
            user=self.student, classroom=self.classroom, started_at=timezone.localdate()
        )
        self.client.force_authenticate(self.teacher)
