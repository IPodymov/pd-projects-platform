from datetime import timedelta
from django.utils import timezone
from common.testing import PlatformCase
from common.api import BusinessError
from .models import Project, ProjectMember, Task, ReviewEvent
from .services import create_submission, send_draft, review_submission


class ProjectWorkflowTests(PlatformCase):
    def test_submission_chain_review_history_and_foreign_access(self):
        project = Project.objects.create(title="Команда", classroom=self.classroom)
        ProjectMember.objects.create(project=project, user=self.student, role="leader")
        task = Task.objects.create(
            project=project,
            title="Прототип",
            due_at=timezone.now() + timedelta(days=1),
            criteria="Рабочая демонстрация",
        )
        draft = create_submission(
            self.student, {"task": task, "text": "План"}, draft=True
        )
        send_draft(self.student, draft)
        draft.refresh_from_db()
        review_submission(self.teacher, draft, "revision", "Нет измерений")
        draft.refresh_from_db()
        revised = create_submission(
            self.student,
            {"task": task, "text": "Измерения приложены", "previous": draft},
        )
        review_submission(self.teacher, revised, "accepted", "")
        self.assertEqual(ReviewEvent.objects.count(), 2)
        with self.assertRaises(BusinessError):
            review_submission(self.teacher, revised, "revision", "Повтор")
        self.client.force_authenticate(self.student)
        self.assertEqual(
            self.client.get(f"/api/v1/projects/{project.pk}/").data["progress"], 100
        )
        self.client.force_authenticate(self.stranger)
        self.assertEqual(
            self.client.get(f"/api/v1/submissions/{revised.pk}/").status_code, 404
        )
