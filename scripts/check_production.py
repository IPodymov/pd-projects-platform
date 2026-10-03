"""Only synthetic configuration. check --deploy does not connect to this DB."""

import os, subprocess, sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
variables = {
    "DJANGO_SETTINGS_MODULE": "config.settings.production",
    "SECRET_KEY": "synthetic-check-only-" + "x" * 60,
    "DATABASE_URL": "postgresql://synthetic:synthetic@127.0.0.1:15432/synthetic",
    "REDIS_URL": "redis://127.0.0.1:16379/15",
    "ALLOWED_HOSTS": "api.example.test,healthcheck.railway.app",
    "CORS_ALLOWED_ORIGINS": "https://app.example.test",
    "CSRF_TRUSTED_ORIGINS": "https://app.example.test",
    "WEB_URL": "https://app.example.test",
    "S3_BUCKET": "synthetic-check-only",
    "S3_ENDPOINT_URL": "https://s3.example.test",
    "S3_ACCESS_KEY": "synthetic",
    "S3_SECRET_KEY": "synthetic",
    "INVITATION_ENCRYPTION_KEY": "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
    "EMAIL_HOST": "smtp.example.test",
    "EMAIL_USERNAME": "synthetic",
    "EMAIL_PASSWORD": "synthetic",
    "DEFAULT_FROM_EMAIL": "platform@example.test",
    "EMAIL_PORT": "587",
    "EMAIL_USE_TLS": "true",
}
raise SystemExit(
    subprocess.run(
        [
            sys.executable,
            str(root / "apps/backend/manage.py"),
            "check",
            "--deploy",
            "--fail-level",
            "WARNING",
        ],
        env={**os.environ, **variables},
    ).returncode
)
