from django.core.management.base import BaseCommand
from invitations.services import expire


class Command(BaseCommand):
    help = "Удалить зашифрованные токены истёкших приглашений"

    def handle(self, *args, **options):
        self.stdout.write(str(expire()))
