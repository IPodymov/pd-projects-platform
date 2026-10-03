import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from publications.seed import import_seed


class Command(BaseCommand):
    help = "Dry-run по умолчанию; --apply выполняет транзакционный импорт"

    def add_arguments(self, p):
        p.add_argument("path")
        p.add_argument("--apply", action="store_true")
        p.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **o):
        if o["apply"] and o["dry_run"]:
            raise CommandError("Выберите --apply или --dry-run")
        try:
            report = import_seed(
                json.loads(Path(o["path"]).read_text()), dry_run=not o["apply"]
            )
        except (ValidationError, ValueError, OSError) as e:
            raise CommandError(str(e))
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
