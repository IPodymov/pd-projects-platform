"""Explicit development fixtures. Never called during normal app startup/deploy."""

import secrets
from datetime import timedelta
from django.utils import timezone
from accounts.models import User
from institutions.models import (
    Classroom,
    Institution,
    StaffAssignment,
    TeachingAssignment,
    StudentMembership,
)
from courses.models import Assignment, Enrollment
from courses.services import create_work, send_work, review_work
from projects.models import Project, ProjectMember, Milestone, Task
from publications.models import Competition
from scheduling.models import Lesson
from workshops.models import Partnership, Workshop, Subscription
from invitations.models import Prospect, Invitation
from invitations.services import issue


def populate_scenarios(command, school, classroom, course, reset_passwords=False):
    now = timezone.now()
    university, _ = Institution.objects.get_or_create(
        name="Инженерный университет · DEMO", kind="university"
    )
    users = {}
    for name, full_name in [
        ("student2", "Мария Иванова · DEMO"),
        ("student3", "Илья Петров · DEMO"),
        ("organizer", "Организатор вуза · DEMO"),
        ("platform", "Администратор платформы · DEMO"),
    ]:
        user, created = User.objects.get_or_create(
            username="demo-" + name,
            defaults={
                "email": name + "@example.test",
                "display_name": full_name,
                "email_verified_at": now,
                "is_staff": name == "platform",
                "is_superuser": name == "platform",
            },
        )
        if created or reset_passwords:
            password = secrets.token_urlsafe(14)
            user.set_password(password)
            user.save()
            command.stdout.write(f"DEV ONLY {user.email}: {password}")
        users[name] = user
    teacher = User.objects.get(username="demo-teacher")
    curator = User.objects.get(username="demo-curator")
    second, _ = Classroom.objects.get_or_create(
        institution=school, name="9Б · DEMO", academic_year="2026/2027"
    )
    staff = StaffAssignment.objects.get(
        user=teacher, institution=school, role="teacher"
    )
    TeachingAssignment.objects.get_or_create(staff=staff, classroom=second)
    StaffAssignment.objects.get_or_create(
        user=users["organizer"], institution=university, role="organizer"
    )
    for key, cl in [("student2", classroom), ("student3", second)]:
        StudentMembership.objects.get_or_create(
            user=users[key], classroom=cl, defaults={"started_at": timezone.localdate()}
        )
        Enrollment.objects.get_or_create(
            user=users[key], course=course, defaults={"classroom": cl}
        )
    assignment, created = Assignment.objects.get_or_create(
        course=course,
        title="Презентация решения · DEMO",
        defaults={
            "instructions": "Опишите прототип и результаты измерений.",
            "criteria": "Проблема, схема прототипа и результаты испытаний.",
            "due_at": now + timedelta(days=10),
            "position": 2,
        },
    )
    enrollment = Enrollment.objects.get(user=users["student2"], course=course)
    # Use real use cases: reviews and CRM activity match the seeded work.
    if created and course.status == "published" and enrollment.status == "active":
        work = create_work(
            users["student2"],
            {
                "assignment": assignment,
                "enrollment": enrollment,
                "text": "DEMO: прототип проверен на трёх режимах, измерения приложены в описании.",
            },
        )
        send_work(users["student2"], work)
        review_work(
            teacher,
            work,
            "accepted",
            "DEMO: измеримые результаты и критерии представлены.",
        )
    project, _ = Project.objects.get_or_create(
        classroom=second,
        title="Мониторинг качества воздуха · DEMO",
        defaults={
            "description": "Командный проект: датчики, измерения и отчёт",
            "due_at": now + timedelta(days=21),
        },
    )
    ProjectMember.objects.get_or_create(
        project=project, user=users["student3"], defaults={"role": "leader"}
    )
    milestone, _ = Milestone.objects.get_or_create(
        project=project,
        title="Прототип · DEMO",
        defaults={
            "criteria": "Получены измерения от датчика",
            "due_at": now + timedelta(days=14),
            "status": "active",
        },
    )
    Task.objects.get_or_create(
        project=project,
        title="Выбрать датчик · DEMO",
        defaults={
            "milestone": milestone,
            "criteria": "Обоснована точность и стоимость",
            "due_at": now + timedelta(days=5),
        },
    )
    for offset, title, format_ in [
        (1, "Защита гипотез · DEMO", "online"),
        (3, "Сборка прототипа · DEMO", "onsite"),
    ]:
        start = (now + timedelta(days=offset)).replace(
            hour=12, minute=0, second=0, microsecond=0
        )
        Lesson.objects.get_or_create(
            classroom=classroom,
            title=title,
            defaults={
                "course": course,
                "teacher": teacher,
                "curator": curator,
                "starts_at": start,
                "ends_at": start + timedelta(hours=1),
                "format": format_,
                "online_url": "https://example.test/demo-lesson"
                if format_ == "online"
                else "",
                "location": "Демонстрационная школа" if format_ == "onsite" else "",
                "room": "Лаборатория 12" if format_ == "onsite" else "",
            },
        )
    Partnership.objects.get_or_create(
        university=university,
        school=school,
        defaults={
            "status": "active",
            "starts_on": now.date(),
            "ends_on": (now + timedelta(days=365)).date(),
        },
    )
    Subscription.objects.get_or_create(user=curator, school=school)
    for title, audience, capacity in [
        ("Робототехника для начинающих · DEMO", "all", 20),
        ("Инженерная лаборатория партнёров · DEMO", "partners", 2),
    ]:
        Workshop.objects.get_or_create(
            university=university,
            title=title,
            defaults={
                "organizer": users["organizer"],
                "leader": users["organizer"],
                "description": "Тестовое мероприятие для знакомства с записью и листом ожидания.",
                "topic": "Робототехника",
                "requirements": "Тестовые записи, участие не является реальной регистрацией.",
                "starts_at": now + timedelta(days=14),
                "ends_at": now + timedelta(days=14, hours=2),
                "registration_opens_at": now - timedelta(days=1),
                "registration_closes_at": now + timedelta(days=12),
                "format": "onsite",
                "location": "Университет · лаборатория 101 · DEMO",
                "capacity": capacity,
                "audience": audience,
                "published": True,
            },
        )
    Competition.objects.get_or_create(
        slug="demo-future-engineers",
        defaults={
            "title": "Инженерные идеи · DEMO",
            "requirements": "Представьте описание проблемы, прототипа и измерений. Это тестовый конкурс.",
            "deadline": now + timedelta(days=30),
            "topic_id": "engineering",
            "published": True,
            "is_demo": True,
        },
    )
    prospect, created = Prospect.objects.get_or_create(
        classroom=classroom,
        email="invited-student@example.test",
        defaults={"full_name": "Приглашённый школьник · DEMO"},
    )
    if created and not Invitation.objects.filter(prospect=prospect).exists():
        issue(teacher, school, prospect.email, "student", classroom, prospect)
    command.stdout.write(
        "DEMO: 2 класса, 3 ученика, проверенная работа, проекты, занятия, приглашение, конкурс и 2 мастер-класса."
    )
