from abc import ABC, abstractmethod
from dataclasses import dataclass
import re
import httpx


@dataclass(frozen=True)
class RemotePullRequest:
    number: int
    status: str
    url: str
    title: str
    head_sha: str = ""
    updated_at: str = ""


class RepositoryAdapter(ABC):
    @abstractmethod
    def pull_requests(self, owner: str, repo: str) -> list[RemotePullRequest]: ...


class GithubAdapter(RepositoryAdapter):
    def __init__(self, token, transport=None):
        if not token:
            raise ValueError("GITHUB_TOKEN required")
        self.client = httpx.Client(
            base_url="https://api.github.com",
            headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=15,
            transport=transport,
        )

    def pull_requests(self, owner, repo):
        if not all(re.fullmatch(r"[A-Za-z0-9_.-]+", v) for v in [owner, repo]):
            raise ValueError("Invalid repository path")
        result = []
        for page in range(1, 11):
            response = self.client.get(
                f"/repos/{owner}/{repo}/pulls",
                params={"state": "all", "per_page": 100, "page": page},
            )
            response.raise_for_status()
            rows = response.json()
            for r in rows:
                result.append(
                    RemotePullRequest(
                        r["number"],
                        "merged" if r.get("merged_at") else r["state"],
                        r["html_url"],
                        r["title"],
                        r.get("head", {}).get("sha", ""),
                        r.get("updated_at", ""),
                    )
                )
            if len(rows) < 100:
                return result
        raise RuntimeError(
            "Pagination limit exceeded; refusing incomplete synchronization"
        )


class GitverseAdapter(RepositoryAdapter):
    """GitVerse v1 transport; its Accept/version and Link pagination are independent."""

    def __init__(self, token=None, transport=None):
        if not token:
            raise ValueError("GITVERSE_TOKEN required")
        self.client = httpx.Client(
            base_url="https://api.gitverse.ru",
            headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/vnd.gitverse.object+json;version=1",
            },
            timeout=15,
            transport=transport,
        )

    def pull_requests(self, owner, repo):
        from urllib.parse import urlparse

        if not all(
            re.fullmatch(r"[A-Za-z0-9_.-]+", v) and v not in (".", "..")
            for v in (owner, repo)
        ):
            raise ValueError("Invalid repository path")
        path = f"/repos/{owner}/{repo}/pulls"
        url = path
        result = []
        for page in range(1, 11):
            response = self.client.get(
                url,
                params={"state": "all", "per_page": 100, "page": page}
                if url == path
                else None,
            )
            response.raise_for_status()
            rows = response.json()
            for row in rows:
                result.append(
                    RemotePullRequest(
                        row["number"],
                        "merged"
                        if row.get("merged") or row.get("merged_at")
                        else row["state"],
                        row["html_url"],
                        row["title"],
                        row["head"]["sha"],
                        row["updated_at"],
                    )
                )
            following = response.links.get("next", {}).get("url")
            if not following:
                if len(rows) < 100:
                    return result
                url = path
            else:
                parsed = urlparse(following)
                if (
                    parsed.scheme != "https"
                    or parsed.hostname != "api.gitverse.ru"
                    or parsed.port not in (None, 443)
                    or parsed.username
                    or parsed.path != path
                ):
                    raise ValueError("Unsafe provider pagination URL")
                url = following
        raise RuntimeError("Pagination limit exceeded")
