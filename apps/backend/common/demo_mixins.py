"""Reusable development fixture loading and environment protection."""

from django.conf import settings
from django.core.management.base import CommandError


class LocalDemoMixin:
    def require_local_demo(self):
        if not settings.DEBUG or not getattr(settings, "LOCAL_DEMO_ENABLED", False):
            raise CommandError("Demo разрешено только в локальном development")
        database = settings.DATABASES["default"]
        if database["ENGINE"] == "django.db.backends.sqlite3":
            return
        if database["ENGINE"] != "django.db.backends.postgresql" or database.get(
            "HOST"
        ) not in {"postgres", "localhost", "127.0.0.1", "::1"}:
            raise CommandError(
                "Demo запрещено для внешней БД; используйте локальную БД"
            )


class DemoScenariosMixin:
    def populate_demo_scenarios(self, school, classroom, course, reset_passwords=False):
        from common.demo import populate_scenarios

        populate_scenarios(self, school, classroom, course, reset_passwords)
