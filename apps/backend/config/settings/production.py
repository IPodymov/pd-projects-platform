from .base import *
from django.core.exceptions import ImproperlyConfigured

required = [
    "SECRET_KEY",
    "DATABASE_URL",
    "REDIS_URL",
    "ALLOWED_HOSTS",
    "CORS_ALLOWED_ORIGINS",
    "CSRF_TRUSTED_ORIGINS",
    "WEB_URL",
    "S3_BUCKET",
    "S3_ENDPOINT_URL",
    "S3_ACCESS_KEY",
    "S3_SECRET_KEY",
    "INVITATION_ENCRYPTION_KEY",
    "EMAIL_HOST",
    "EMAIL_USERNAME",
    "EMAIL_PASSWORD",
    "DEFAULT_FROM_EMAIL",
]
missing = [key for key in required if not os.getenv(key)]
if missing:
    raise ImproperlyConfigured(
        "Missing production configuration: " + ", ".join(missing)
    )
if not DATABASES["default"]["ENGINE"].endswith("postgresql"):
    raise ImproperlyConfigured("Production requires PostgreSQL")
DEBUG = False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
from urllib.parse import urlparse
from cryptography.fernet import Fernet

try:
    Fernet(INVITATION_ENCRYPTION_KEY.encode())
except ValueError, TypeError:
    raise ImproperlyConfigured("INVITATION_ENCRYPTION_KEY must be a valid Fernet key")
if len(SECRET_KEY) < 50 or "*" in ",".join(ALLOWED_HOSTS):
    raise ImproperlyConfigured(
        "Use a strong SECRET_KEY (50+ characters) and explicit ALLOWED_HOSTS"
    )
for origin in CORS_ALLOWED_ORIGINS + CSRF_TRUSTED_ORIGINS + [WEB_URL]:
    parsed = urlparse(origin)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or "*" in origin
        or parsed.path not in ("", "/")
    ):
        raise ImproperlyConfigured("Production origins must be explicit HTTPS origins")
if WEB_URL not in CORS_ALLOWED_ORIGINS or WEB_URL not in CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured(
        "WEB_URL must be in CORS_ALLOWED_ORIGINS and CSRF_TRUSTED_ORIGINS"
    )
# Railway's readiness probe can use HTTP within the platform network.
SECURE_REDIRECT_EXEMPT = [r"^health/"]
