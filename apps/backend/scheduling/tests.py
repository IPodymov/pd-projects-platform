from datetime import timedelta, datetime
from zoneinfo import ZoneInfo
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied
from common.testing import PlatformCase
from common.models import Notification, AuditEvent
from .services import create_lesson, change_lesson


class ScheduleTests(PlatformCase):
    def values(self):
        start = timezone.now() + timedelta(days=2)
        return dict(
            title="Проектное занятие",
            classroom=self.classroom,
            teacher=self.teacher,
            curator=self.curator,
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            timezone="Europe/Moscow",
            format="online",
            online_url="https://example.test/meeting",
        )

    def test_rights_and_notification_after_format_change(self):
        lesson = create_lesson(self.admin, self.values())[0]
        with self.assertRaises(PermissionDenied):
            change_lesson(
                self.teacher,
                lesson,
                {"format": "onsite", "location": "Школа", "room": "101"},
            )
        change_lesson(
            self.curator,
            lesson,
            {"format": "onsite", "location": "Школа", "room": "101"},
        )
        lesson.refresh_from_db()
        self.assertEqual(lesson.online_url, "")
        self.assertEqual(lesson.format, "onsite")
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.student, title__startswith="Обновлено"
            ).exists()
        )
        self.assertTrue(AuditEvent.objects.filter(action="lesson.changed").exists())

    def test_intersections_and_cancelled_event(self):
        lesson = create_lesson(self.admin, self.values())[0]
        with self.assertRaises(ValidationError):
            create_lesson(self.admin, self.values())
        change_lesson(self.admin, lesson, {"status": "cancelled"})
        self.assertEqual(len(create_lesson(self.admin, self.values())), 1)

    def test_required_location_url_and_cross_class_teacher(self):
        v = self.values()
        v["online_url"] = "javascript:alert(1)"
        with self.assertRaises(ValidationError):
            create_lesson(self.admin, v)
        v = self.values()
        v["format"] = "onsite"
        v["room"] = ""
        with self.assertRaises(ValidationError):
            create_lesson(self.admin, v)
        v = self.values()
        v["classroom"] = self.foreign
        with self.assertRaises(ValidationError):
            create_lesson(self.admin, v)

    def test_weekly_timezone_and_single_event_exception(self):
        v = self.values()
        v["timezone"] = "Europe/Berlin"
        v["starts_at"] = datetime(2026, 10, 18, 14, tzinfo=ZoneInfo("Europe/Berlin"))
        v["ends_at"] = v["starts_at"] + timedelta(hours=1)
        lessons = create_lesson(self.admin, v, weeks=3)
        self.assertEqual(
            [l.starts_at.astimezone(ZoneInfo("Europe/Berlin")).hour for l in lessons],
            [14, 14, 14],
        )
        self.assertNotEqual(
            lessons[0].starts_at.utcoffset(), lessons[1].starts_at.utcoffset()
        )
        change_lesson(self.curator, lessons[1], {"status": "cancelled"})
        change_lesson(
            self.curator, lessons[0], {"title": "Серия изменена"}, whole_series=True
        )
        lessons[1].refresh_from_db()
        self.assertEqual(lessons[1].title, "Проектное занятие")
        self.assertTrue(lessons[1].is_exception)

    def test_bulk_time_shift_preserves_exception_and_dst_wall_clock(self):
        v = self.values()
        v["timezone"] = "Europe/Berlin"
        v["starts_at"] = datetime(2026, 10, 18, 14, tzinfo=ZoneInfo("Europe/Berlin"))
        v["ends_at"] = v["starts_at"] + timedelta(hours=1)
        lessons = create_lesson(self.admin, v, weeks=3)
        change_lesson(self.curator, lessons[1], {"status": "cancelled"})
        change_lesson(
            self.curator,
            lessons[0],
            {
                "starts_at": v["starts_at"] + timedelta(hours=2),
                "ends_at": v["ends_at"] + timedelta(hours=2),
            },
            whole_series=True,
        )
        for event in lessons:
            event.refresh_from_db()
        self.assertEqual(
            [x.starts_at.astimezone(ZoneInfo("Europe/Berlin")).hour for x in lessons],
            [16, 14, 16],
        )
        self.assertEqual(lessons[1].status, "cancelled")

    def test_bulk_conflict_rolls_back_all_events(self):
        v = self.values()
        lessons = create_lesson(self.admin, v, weeks=2)
        block = {
            **v,
            "starts_at": lessons[1].starts_at + timedelta(hours=2),
            "ends_at": lessons[1].ends_at + timedelta(hours=2),
        }
        create_lesson(self.admin, block)
        with self.assertRaises(ValidationError):
            change_lesson(
                self.curator,
                lessons[0],
                {
                    "starts_at": lessons[0].starts_at + timedelta(hours=2),
                    "ends_at": lessons[0].ends_at + timedelta(hours=2),
                },
                whole_series=True,
            )
        lessons[0].refresh_from_db()
        self.assertEqual(lessons[0].starts_at, v["starts_at"])

    def test_attendance_time_membership_and_idempotence(self):
        from .services import record_class_attendance
        from common.api import BusinessError

        lesson = create_lesson(self.admin, self.values())[0]
        with self.assertRaises(BusinessError):
            record_class_attendance(self.teacher, lesson, self.student, True)
        lesson.starts_at = timezone.now() - timedelta(minutes=10)
        lesson.ends_at = timezone.now() + timedelta(minutes=50)
        lesson.save()
        first = record_class_attendance(self.teacher, lesson, self.student, True)
        self.assertEqual(
            record_class_attendance(self.teacher, lesson, self.student, True).pk,
            first.pk,
        )
        with self.assertRaises(PermissionDenied):
            record_class_attendance(self.stranger, lesson, self.student, True)

    def test_course_calendar_requires_enrollment_and_same_institution(self):
        from courses.models import Course, Enrollment

        course = Course.objects.create(
            title="Курс", institution=self.school, status="published"
        )
        lesson = create_lesson(self.admin, {**self.values(), "course": course})[0]
        self.client.force_authenticate(self.student)
        url = f"/api/v1/lessons/{lesson.pk}/"
        self.assertEqual(self.client.get(url).status_code, 404)
        Enrollment.objects.create(
            course=course, user=self.student, classroom=self.classroom
        )
        self.assertEqual(self.client.get(url).status_code, 200)
        foreign = Course.objects.create(
            title="Чужой", institution=self.other, status="published"
        )
        with self.assertRaises(ValidationError):
            create_lesson(self.admin, {**self.values(), "course": foreign})
