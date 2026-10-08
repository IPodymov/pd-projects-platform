from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from common.testing import PlatformCase
from .models import Course, Assignment, CourseMaterial
from .services import enroll, create_work, send_work, review_work


class CourseAuthoringTests(PlatformCase):
    def test_teacher_creates_publishes_and_completes_course(self):
        response = self.client.post(
            "/api/v1/courses/",
            {"title": "Курс", "institution": str(self.school.pk)},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        course = Course.objects.get(pk=response.data["id"])
        task = self.client.post(
            "/api/v1/assignments/",
            {
                "course": str(course.pk),
                "title": "Практика",
                "instructions": "Сделать",
                "criteria": "Готово",
                "due_at": timezone.now().isoformat(),
            },
            format="json",
        )
        self.assertEqual(task.status_code, 201, task.data)
        response = self.client.post(
            f"/api/v1/courses/{course.pk}/transition/",
            {"status": "published"},
            format="json",
            HTTP_IF_MATCH=course.updated_at.isoformat(),
        )
        self.assertEqual(response.status_code, 200, response.data)
        course.refresh_from_db()
        enrollment = enroll(self.teacher, course, self.teacher, self.classroom)
        work = create_work(
            self.teacher,
            {
                "assignment": Assignment.objects.get(pk=task.data["id"]),
                "enrollment": enrollment,
                "text": "Результат",
            },
        )
        send_work(self.teacher, work)
        review_work(self.curator, work, "accepted", "")
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, "completed")
        self.client.force_authenticate(self.student)
        denied = self.client.post(
            "/api/v1/courses/",
            {"title": "Запрещено", "institution": str(self.school.pk)},
            format="json",
        )
        self.assertEqual(denied.status_code, 403)

    def test_files_are_private_and_upload_requires_enrollment(self):
        course = Course.objects.create(
            title="Курс", institution=self.school, status="published"
        )
        enroll(self.student, course, self.student, self.classroom)
        self.client.force_authenticate(self.student)
        response = self.client.post(
            "/api/v1/course-materials/",
            {
                "course": str(course.pk),
                "title": "Моя работа",
                "file": SimpleUploadedFile("work.txt", b"result"),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.data)
        pk = response.data["id"]
        self.assertFalse(response.data["teaching_resource"])
        self.assertEqual(
            self.client.get(f"/api/v1/course-materials/{pk}/download/").status_code, 200
        )
        self.client.force_authenticate(self.stranger)
        self.assertEqual(
            self.client.get(f"/api/v1/course-materials/{pk}/download/").status_code, 404
        )
        response = self.client.post(
            "/api/v1/course-materials/",
            {
                "course": str(course.pk),
                "title": "Чужая работа",
                "file": SimpleUploadedFile("work.txt", b"result"),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 403)
        from institutions.models import StudentMembership

        StudentMembership.objects.create(
            user=self.stranger,
            classroom=self.classroom,
            started_at=timezone.localdate(),
        )
        enroll(self.stranger, course, self.stranger, self.classroom)
        self.assertEqual(
            self.client.get(f"/api/v1/course-materials/{pk}/download/").status_code, 404
        )
        self.client.force_authenticate(self.teacher)
        self.assertEqual(
            self.client.get(f"/api/v1/course-materials/{pk}/download/").status_code, 200
        )
        response = self.client.post(
            "/api/v1/course-materials/",
            {
                "course": str(course.pk),
                "title": "Подмена PDF",
                "file": SimpleUploadedFile("work.pdf", b"<script>bad</script>"),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(CourseMaterial.objects.count(), 1)

    def test_lesson_only_course_and_idempotent_completion(self):
        from .models import CourseLesson, LessonCompletion
        from .services import change_course, complete_lesson, progress

        course = Course.objects.create(title="Теория", institution=self.school)
        lesson = CourseLesson.objects.create(
            course=course, title="Введение", body="Текст"
        )
        change_course(self.teacher, course, "published")
        course.refresh_from_db()
        enrollment = enroll(self.student, course, self.student, self.classroom)
        self.assertEqual(progress(enrollment), 0)
        complete_lesson(self.student, lesson)
        complete_lesson(self.student, lesson)
        enrollment.refresh_from_db()
        self.assertEqual(progress(enrollment), 100)
        self.assertEqual(enrollment.status, "completed")
        self.assertEqual(LessonCompletion.objects.count(), 1)
        self.client.force_authenticate(self.stranger)
        response = self.client.post(f"/api/v1/course-lessons/{lesson.pk}/complete/")
        self.assertEqual(response.status_code, 404)
