import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from publications.seed import validate_seed


class Command(BaseCommand):
    help = "Проверка allowlist, зависимостей, версии и checksum без записи"

    def add_arguments(self, p):
        p.add_argument("path")

    def handle(self, *args, **o):
        try:
            seed = validate_seed(json.loads(Path(o["path"]).read_text()))
        except (ValidationError, ValueError, OSError) as e:
            raise CommandError(str(e))
        self.stdout.write(f"Valid: {len(seed['records'])} records")
