from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from workspace.permissions import ROLE_NAMES, ensure_roles
from workspace.services import log_event


class Command(BaseCommand):
    help = 'Explicitly grant business roles to a local account; records this local-operator action.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--role', choices=ROLE_NAMES, action='append', required=True)

    def handle(self, *args, **options):
        try:
            user = get_user_model().objects.get(username=options['username'])
        except get_user_model().DoesNotExist:
            raise CommandError('Account not found. Create it first using createsuperuser or workspace settings.')
        groups = ensure_roles()
        user.groups.add(*(groups[role] for role in options['role']))
        log_event(None, 'permissions.local_operator_grant', detail=f'Account {user.pk}; explicit roles: ' + ', '.join(options['role']))
        self.stdout.write(self.style.SUCCESS('Requested role assignments saved; existing assignments preserved.'))
