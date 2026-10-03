from django.utils import timezone
from common.testing import PlatformCase
from projects.models import Project, Task, Submission
from .models import LearningActivity


class MetricTests(PlatformCase):
    def test_login_not_learning_and_submitted_not_accepted(self):
        self.student.last_login = timezone.now()
        self.student.save()
        from accounts.models import LoginEvent

        LoginEvent.objects.create(user=self.student)
        p = Project.objects.create(title="Проект", classroom=self.classroom)
        task = Task.objects.create(project=p, title="Задание", due_at=timezone.now())
        s = Submission.objects.create(task=task, author=self.student, text="Работа")
        r = self.client.get("/api/crm/").data["learning"]
        self.assertEqual(r["registered"], 1)
        self.assertEqual(r["logged_in_during_period"], 1)
        self.assertEqual(r["educationally_active"], 0)
        self.assertEqual(r["progress_percent"], 0)
        LearningActivity.objects.create(
            actor=self.student,
            classroom=self.classroom,
            kind="task.submitted",
            target=str(s.pk),
        )
        s.result = "accepted"
        s.save()
        r = self.client.get("/api/crm/").data["learning"]
        self.assertEqual(r["educationally_active"], 1)
        self.assertEqual(r["progress_percent"], 100)
        r = self.client.get("/api/crm/", {"classroom": str(self.foreign.pk)}).data[
            "learning"
        ]
        self.assertEqual(r["registered"], 0)
        self.assertEqual(r["projects"], 0)
