import re
from urllib.parse import urlparse
from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils.dateparse import parse_datetime
from common.access import project_access
from .models import SyncJob, Repository, PullRequest
from .adapters import GithubAdapter, GitverseAdapter


@shared_task(time_limit=60, soft_time_limit=55)
def synchronize(pk):
    job = SyncJob.objects.select_related("repository__project", "requested_by").get(
        pk=pk
    )
    if job.status == "succeeded":
        return
    if not job.repository.enabled:
        SyncJob.objects.filter(pk=pk).update(
            status="failed", error_code="repository_disabled"
        )
        return
    if job.requested_by_id:
        try:
            project_access(job.requested_by, job.repository.project, True)
        except Exception:
            SyncJob.objects.filter(pk=pk).update(
                status="failed", error_code="access_revoked"
            )
            return
    SyncJob.objects.filter(pk=pk).update(status="processing")
    try:
        token = getattr(
            settings,
            "GITHUB_TOKEN" if job.repository.provider == "github" else "GITVERSE_TOKEN",
            "",
        )
        adapter = (
            GithubAdapter if job.repository.provider == "github" else GitverseAdapter
        )(token)
        try:
            rows = adapter.pull_requests(job.repository.owner, job.repository.name)
        finally:
            adapter.client.close()
        with transaction.atomic():
            repository = Repository.objects.select_for_update().get(
                pk=job.repository_id
            )
            if not repository.enabled:
                raise ValueError("Disabled")
            for row in rows:
                host = (
                    "github.com" if repository.provider == "github" else "gitverse.ru"
                )
                url = urlparse(row.url)
                source = parse_datetime(row.updated_at)
                if (
                    not re.fullmatch(r"[a-fA-F0-9]{40,64}", row.head_sha)
                    or not source
                    or not source.tzinfo
                    or url.scheme != "https"
                    or url.hostname != host
                    or row.status not in ("open", "closed", "merged")
                ):
                    raise ValueError("Invalid provider contract")
                pull, created = PullRequest.objects.select_for_update().get_or_create(
                    repository=repository,
                    external_number=row.number,
                    defaults={"status": row.status, "url": row.url},
                )
                if (
                    not created
                    and pull.source_updated_at
                    and source < pull.source_updated_at
                ):
                    continue
                (
                    pull.status,
                    pull.url,
                    pull.title,
                    pull.head_sha,
                    pull.source_updated_at,
                ) = row.status, row.url, row.title[:200], row.head_sha, source
                pull.save()
            SyncJob.objects.filter(pk=pk).update(status="succeeded", error_code="")
            if job.webhook_id:
                job.webhook.__class__.objects.filter(pk=job.webhook_id).update(
                    status="processed"
                )
    except Exception:
        SyncJob.objects.filter(pk=pk).update(
            status="failed", error_code="provider_sync_failed"
        )
        raise
