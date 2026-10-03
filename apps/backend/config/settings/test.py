from .base import *

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
STORAGES["default"] = {"BACKEND": "django.core.files.storage.InMemoryStorage"}
CELERY_TASK_ALWAYS_EAGER = True
INVITATION_ENCRYPTION_KEY = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
if os.getenv("TEST_DATABASE_URL"):
    DATABASES = {"default": dj_database_url.parse(os.environ["TEST_DATABASE_URL"])}
