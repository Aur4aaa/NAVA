from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from workspace.services import generate_recurring_tasks


class Command(BaseCommand):
    help = 'Create due recurring task instances once per recurrence date.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)

    def handle(self, *args, **options):
        try:
            user = get_user_model().objects.get(username=options['username'])
        except get_user_model().DoesNotExist:
            raise CommandError('Account not found.')
        created = generate_recurring_tasks(user)
        self.stdout.write(f'{len(created)} recurring task instances created.')
