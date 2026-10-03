import httpx
from django.test import SimpleTestCase
from .adapters import GithubAdapter, GitverseAdapter


class AdapterTests(SimpleTestCase):
    def test_github_contract_and_merged_status(self):
        def handler(request):
            self.assertEqual(request.url.host, "api.github.com")
            self.assertEqual(request.headers["X-GitHub-Api-Version"], "2022-11-28")
            return httpx.Response(
                200,
                json=[
                    {
                        "number": 1,
                        "state": "closed",
                        "merged_at": "2026-01-01",
                        "html_url": "https://github.com/a/b/pull/1",
                        "title": "Change",
                    }
                ],
            )

        rows = GithubAdapter("test-token", httpx.MockTransport(handler)).pull_requests(
            "a", "b"
        )
        self.assertEqual(rows[0].status, "merged")

    def test_gitverse_contract_is_independent(self):
        def handler(request):
            self.assertEqual(request.url.host, "api.gitverse.ru")
            self.assertEqual(
                request.headers["Accept"],
                "application/vnd.gitverse.object+json;version=1",
            )
            self.assertNotIn("X-GitHub-Api-Version", request.headers)
            return httpx.Response(
                200,
                json=[
                    {
                        "number": 3,
                        "state": "closed",
                        "merged": True,
                        "html_url": "https://gitverse.ru/a/b/pull/3",
                        "title": "Review",
                        "head": {"sha": "a" * 40},
                        "updated_at": "2026-01-01T00:00:00Z",
                    }
                ],
            )

        rows = GitverseAdapter("synthetic", httpx.MockTransport(handler)).pull_requests(
            "a", "b"
        )
        self.assertEqual(rows[0].status, "merged")
        self.assertEqual(rows[0].head_sha, "a" * 40)

    def test_gitverse_rejects_cross_host_pagination(self):
        def handler(request):
            return httpx.Response(
                200,
                json=[],
                headers={"Link": '<https://attacker.example/pulls>; rel="next"'},
            )

        with self.assertRaises(ValueError):
            GitverseAdapter("synthetic", httpx.MockTransport(handler)).pull_requests(
                "a", "b"
            )


from common.testing import PlatformCase
from django.test import override_settings
from projects.models import Project, ProjectMember
from .models import Repository, PullRequest, WebhookEvent, SyncJob
from .services import receive_webhook, assign_review, decide_review
from common.api import BusinessError
from rest_framework.exceptions import PermissionDenied
import hashlib, hmac, json


class GitWorkflowTests(PlatformCase):
    def setUp(self):
        super().setUp()
        self.project = Project.objects.create(title="Робот", classroom=self.classroom)
        ProjectMember.objects.create(project=self.project, user=self.student)
        self.repo = Repository.objects.create(
            project=self.project,
            provider="github",
            owner="school",
            name="robot",
            enabled=True,
        )
        self.pull = PullRequest.objects.create(
            repository=self.repo,
            external_number=1,
            status="open",
            url="https://github.com/school/robot/pull/1",
            head_sha="a" * 40,
        )

    @override_settings(GITHUB_WEBHOOK_SECRET="synthetic-test-secret")
    def test_verified_webhook_is_idempotent_and_payload_bound(self):
        body = json.dumps({"repository": {"full_name": "school/robot"}}).encode()
        headers = {
            "X-GitHub-Delivery": "delivery-1",
            "X-Hub-Signature-256": "sha256="
            + hmac.new(b"synthetic-test-secret", body, hashlib.sha256).hexdigest(),
        }
        event, created = receive_webhook(self.repo, body, headers)
        self.assertTrue(created)
        self.assertFalse(receive_webhook(self.repo, body, headers)[1])
        self.assertEqual(WebhookEvent.objects.count(), 1)
        self.assertEqual(SyncJob.objects.count(), 1)
        with self.assertRaises(PermissionDenied):
            receive_webhook(
                self.repo, body, {**headers, "X-Hub-Signature-256": "wrong"}
            )
        changed = json.dumps(
            {"repository": {"full_name": "school/robot"}, "action": "closed"}
        ).encode()
        headers["X-Hub-Signature-256"] = (
            "sha256="
            + hmac.new(b"synthetic-test-secret", changed, hashlib.sha256).hexdigest()
        )
        with self.assertRaises(BusinessError):
            receive_webhook(self.repo, changed, headers)

    def test_review_is_bound_to_revision_and_independent_of_pr_status(self):
        review = assign_review(self.teacher, self.pull, self.teacher)
        self.pull.head_sha = "b" * 40
        self.pull.save()
        with self.assertRaises(BusinessError):
            decide_review(self.teacher, review, "accepted", "")
        current = assign_review(self.teacher, self.pull, self.teacher)
        decide_review(self.teacher, current, "accepted", "")
        self.pull.refresh_from_db()
        self.assertEqual(self.pull.status, "open")
        with self.assertRaises(BusinessError):
            decide_review(self.teacher, current, "revision", "Повтор")

    @override_settings(GITHUB_TOKEN="synthetic-test-token")
    def test_out_of_order_sync_cannot_restore_an_old_revision(self):
        from unittest.mock import patch
        from .adapters import RemotePullRequest
        from .tasks import synchronize

        for sha, stamp in [
            ("b" * 40, "2026-10-03T12:00:00Z"),
            ("a" * 40, "2026-10-02T12:00:00Z"),
        ]:
            job = SyncJob.objects.create(
                repository=self.repo, requested_by=self.teacher
            )
            with patch("integrations.tasks.GithubAdapter") as factory:
                factory.return_value.pull_requests.return_value = [
                    RemotePullRequest(
                        number=1,
                        status="open",
                        url=self.pull.url,
                        title="Ревизия",
                        head_sha=sha,
                        updated_at=stamp,
                    )
                ]
                synchronize(str(job.pk))
        self.pull.refresh_from_db()
        self.assertEqual(self.pull.head_sha, "b" * 40)
        self.assertEqual(
            self.pull.source_updated_at.isoformat(), "2026-10-03T12:00:00+00:00"
        )
