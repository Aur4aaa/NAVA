"""Checks structural catalog integrity, not legal/standards equivalence."""
from collections import Counter
from io import StringIO
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, SimpleTestCase
from workspace import catalog
from workspace.models import FrameworkVersion, RequirementReference, ControlReference


class CatalogStructureTests(SimpleTestCase):
    def test_all_93_unique_annex_a_identifiers_and_theme_counts(self):
        expected = {f'A.{theme}.{index}' for theme, count in [(5, 37), (6, 8), (7, 14), (8, 34)] for index in range(1, count + 1)}
        self.assertEqual(len(catalog.CONTROLS), 93)
        self.assertEqual({row['identifier'] for row in catalog.CONTROLS}, expected)
        self.assertEqual(Counter(row['theme'] for row in catalog.CONTROLS), {'organizational': 37, 'people': 8, 'physical': 14, 'technological': 34})
        self.assertTrue(all(row['summary'] and row['title'] for row in catalog.CONTROLS))

    def test_clauses_remain_distinct_and_climate_context_present(self):
        self.assertEqual([row[0] for row in catalog.CLAUSES], ['4', '5', '6', '7', '8', '9', '10'])
        self.assertIn('climate', catalog.CLAUSES[0][2].lower())
        self.assertFalse(catalog.VERIFIED)
        self.assertIsNone(catalog.VERIFICATION_DATE)


class CatalogInstallationTests(TestCase):
    def test_repeated_seed_is_idempotent(self):
        call_command('seed_framework', stdout=StringIO())
        first = list(ControlReference.objects.values_list('pk', flat=True))
        call_command('seed_framework', stdout=StringIO())
        self.assertEqual(FrameworkVersion.objects.count(), 1)
        self.assertEqual(RequirementReference.objects.count(), 7)
        self.assertEqual(list(ControlReference.objects.values_list('pk', flat=True)), first)
        self.assertFalse(RequirementReference.objects.filter(mandatory=False).exists())
        framework = FrameworkVersion.objects.get()
        self.assertEqual(framework.verification_status, 'unverified')
        self.assertIsNone(framework.verified_on)

    def test_seed_refuses_to_overwrite_changed_reference(self):
        call_command('seed_framework', stdout=StringIO())
        ref = ControlReference.objects.get(identifier='A.5.1')
        ref.summary = 'Existing organization-maintained catalog wording'
        ref.save()
        with self.assertRaises(CommandError):
            call_command('seed_framework', stdout=StringIO())
        ref.refresh_from_db()
        self.assertEqual(ref.summary, 'Existing organization-maintained catalog wording')

    def test_new_release_preserves_existing_catalog(self):
        call_command('seed_framework', stdout=StringIO())
        old = FrameworkVersion.objects.get()
        new = FrameworkVersion.objects.create(
            name=old.name, edition=old.edition, catalog_release='future-reviewed-release',
            provenance='Independent release with preserved old identifiers',
        )
        self.assertNotEqual(old.pk, new.pk)
        self.assertEqual(old.controls.count(), 93)
        self.assertEqual(old.requirements.count(), 7)
