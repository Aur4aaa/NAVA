"""Install one independent, explicitly unverified reference-catalog release."""
import json
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from workspace import catalog
from workspace.models import ControlReference, FrameworkVersion, RequirementReference


class Command(BaseCommand):
    help = 'Install the original NAVA reference catalog without overwriting existing releases or organizational records.'

    @transaction.atomic
    def handle(self, *args, **options):
        provenance = '\n'.join([
            catalog.PROVENANCE,
            f'Catalog release: {catalog.CATALOG_RELEASE}',
            f'Verification attempt: {catalog.VERIFICATION_ATTEMPT_DATE}; verified: no',
            json.dumps(catalog.SOURCES, ensure_ascii=False),
        ])
        framework, created = FrameworkVersion.objects.get_or_create(
            name=catalog.FRAMEWORK_NAME,
            edition=catalog.FRAMEWORK_EDITION,
            catalog_release=catalog.CATALOG_RELEASE,
            defaults={
                'source_url': catalog.SOURCES[0]['url'],
                'verified_on': catalog.VERIFICATION_DATE,
                'verification_status': 'unverified',
                'provenance': provenance,
            },
        )
        added = 0
        for identifier, title, summary in catalog.CLAUSES:
            values = {'title': title, 'summary': summary, 'mandatory': True}
            ref, was_created = RequirementReference.objects.get_or_create(
                framework=framework, identifier=identifier,
                defaults={**values, 'provenance': provenance},
            )
            self._check_unchanged(ref, values)
            added += int(was_created)
        for control in catalog.CONTROLS:
            identifier = control['identifier']
            values = {key: control[key] for key in ('title', 'summary', 'theme')}
            values['is_custom'] = False
            ref, was_created = ControlReference.objects.get_or_create(
                framework=framework, identifier=identifier,
                defaults={**values, 'provenance': provenance},
            )
            self._check_unchanged(ref, values)
            added += int(was_created)
        self.stdout.write(self.style.SUCCESS(
            f'Catalog {catalog.CATALOG_RELEASE}: {added} new reference records; '
            '7 management-system areas and 93 Annex A references available.'
        ))
        self.stdout.write(self.style.WARNING(
            'UNVERIFIED catalog: official ISO source retrieval was blocked. '
            'Review docs/standards.md and licensed material before authoritative use.'
        ))

    @staticmethod
    def _check_unchanged(reference, expected):
        if any(getattr(reference, key) != value for key, value in expected.items()):
            raise CommandError(
                f'Existing reference {reference.identifier} differs from this catalog release. '
                'Nothing was overwritten. Create a new catalog release and preserve historical references.'
            )
