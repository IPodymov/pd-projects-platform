from django.apps import AppConfig


class CommonConfig(AppConfig):
    name = "common"

    def ready(self):
        from . import checks  # noqa: F401 -- registers Django system checks
