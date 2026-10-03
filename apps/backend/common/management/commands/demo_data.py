import secrets
from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from accounts.models import User
from institutions.models import (
    Institution,
    Classroom,
    StaffAssignment,
    TeachingAssignment,
    StudentMembership,
)
from courses.models import Course, Enrollment, Assignment
from projects.models import Project, ProjectMember, Task
from publications.models import Topic, Publication


class Command(BaseCommand):
    help = "Локальные данные для тестирования продукта; повторный запуск не сбрасывает результаты"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-passwords",
            action="store_true",
            help="Явно перевыпустить пароли только демонстрационных аккаунтов",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo разрешено только при DEBUG=True в development")
        inst, _ = Institution.objects.get_or_create(
            name="Демонстрационная школа", kind="school"
        )
        cl, _ = Classroom.objects.get_or_create(
            institution=inst, name="9А · DEMO", academic_year="2026/2027"
        )
        for name, role in [
            ("teacher", "teacher"),
            ("curator", "curator"),
            ("student", "student"),
            ("admin", "admin"),
        ]:
            u, new = User.objects.get_or_create(
                username="demo-" + name,
                defaults={
                    "email": name + "@example.test",
                    "first_name": {
                        "teacher": "Преподаватель",
                        "curator": "Куратор",
                        "student": "Ученик",
                        "admin": "Администратор",
                    }[name],
                    "email_verified_at": timezone.now(),
                },
            )
            if new or options["reset_passwords"]:
                password = secrets.token_urlsafe(14)
                u.set_password(password)
                u.save()
                self.stdout.write(f"DEV ONLY {u.email}: {password}")
            if role == "student":
                StudentMembership.objects.get_or_create(
                    user=u, classroom=cl, defaults={"started_at": timezone.localdate()}
                )
            else:
                staff, _ = StaffAssignment.objects.get_or_create(
                    user=u, institution=inst, role=role
                )
                if role == "teacher":
                    TeachingAssignment.objects.get_or_create(staff=staff, classroom=cl)
        course, _ = Course.objects.get_or_create(
            institution=inst,
            title="Основы проектной деятельности",
            defaults={"description": "Демонстрационный курс"},
        )
        Assignment.objects.get_or_create(
            course=course,
            title="План исследования · DEMO",
            defaults={
                "instructions": "Опишите проблему и способ проверки гипотезы.",
                "criteria": "Есть проверяемая гипотеза и измеримый критерий.",
                "due_at": timezone.now() + timedelta(days=7),
            },
        )
        if course.status == "draft" and course.description == "Демонстрационный курс":
            course.status = "published"
            course.save()
        u = User.objects.get(username="demo-student")
        Enrollment.objects.get_or_create(
            user=u, course=course, defaults={"classroom": cl}
        )
        project, _ = Project.objects.get_or_create(
            classroom=cl,
            title="Умная теплица · DEMO",
            defaults={
                "description": "Демонстрационный проект для проверки рабочего процесса."
            },
        )
        ProjectMember.objects.get_or_create(project=project, user=u)
        Task.objects.get_or_create(
            project=project,
            title="Сформулировать проблему",
            defaults={"due_at": timezone.now() + timedelta(days=7)},
        )
        topic, _ = Topic.objects.get_or_create(
            code="engineering", defaults={"title": "Инженерные проекты"}
        )
        Publication.objects.get_or_create(
            slug="demo-welcome",
            defaults={
                "title": "Начало работы · DEMO",
                "body": "Это демонстрационная запись. Она никогда не экспортируется в production seed.",
                "topic": topic,
                "published": True,
                "is_demo": True,
            },
        )
        from common.demo import populate_scenarios

        populate_scenarios(self, inst, cl, course, options["reset_passwords"])
        self.stdout.write(
            "Development demo ready. Results preserved; passwords reset only with --reset-passwords."
        )
