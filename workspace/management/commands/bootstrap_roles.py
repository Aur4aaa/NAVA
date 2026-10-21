from django.core.management.base import BaseCommand
from workspace.permissions import ensure_roles

class Command(BaseCommand):
    help = 'Create missing role presets without assigning business authority to any account.'

    def handle(self, *args, **options):
        ensure_roles()
        self.stdout.write(self.style.SUCCESS('Role presets are available. Existing assignments were preserved.'))
