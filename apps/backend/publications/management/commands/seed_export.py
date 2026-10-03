import json
from pathlib import Path
from django.core.management.base import BaseCommand
from publications.seed import export_seed, validate_seed


class Command(BaseCommand):
    help = "Явный экспорт технических справочников и утверждённых материалов"

    def add_arguments(self, p):
        p.add_argument("path")
        p.add_argument("--include-approved-materials", action="store_true")

    def handle(self, *args, **o):
        seed = export_seed(o["include_approved_materials"])
        validate_seed(seed)
        Path(o["path"]).write_text(
            json.dumps(seed, ensure_ascii=False, indent=2) + "\n"
        )
        self.stdout.write(
            f"Exported {len(seed['records'])} records; checksum {seed['checksum']}"
        )
