import hashlib
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from workspace import models as m
from workspace.services import create_record


class DemoSeedTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.media.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(self.media.cleanup)
        self.manager = get_user_model().objects.create_user(username="local.manager", password=None)

    def seed(self, **kwargs):
        call_command("seed_demo", user=self.manager.username, stdout=StringIO(), **kwargs)

    def test_complete_traceable_demo_and_repeat_preserves_edits_and_bytes(self):
        self.seed()
        self.assertTrue(m.Organization.objects.get().is_demo)
        self.assertEqual(m.ControlImplementation.objects.count(), 93)
        self.assertEqual(m.RiskAssessmentVersion.objects.count(), 8)
        self.assertEqual(m.DocumentVersion.objects.count(), 4)
        self.assertEqual(m.EvidenceVersion.objects.count(), 8)
        self.assertEqual(m.Task.objects.count(), 18)
        self.assertEqual(m.ScopeVersion.objects.get().status, "approved")
        self.assertEqual(m.TreatmentPlan.objects.get().status, "approved")
        self.assertEqual(m.SoAVersion.objects.get().status, "published")
        self.assertEqual(len(m.SoAVersion.objects.get().snapshot), 93)
        self.assertEqual(m.SoAVersion.objects.get().omissions, [])
        self.assertEqual(m.CorrectiveAction.objects.get().status, "closed")
        self.assertNotEqual(m.CorrectiveAction.objects.get().verified_by_id, m.CorrectiveAction.objects.get().owner_id)
        self.assertEqual(m.Finding.objects.get().status, "closed")
        self.assertTrue(m.ManagementReview.objects.get().snapshot["risks"])
        self.assertEqual(set(m.Audit.objects.values_list("audit_type", flat=True)), {"internal", "stage1", "stage2"})
        self.assertEqual(m.CertificationRecord.objects.get().decision, "pending")
        self.assertFalse(m.CertificationRecord.objects.exclude(certificate_number="").exists())
        self.assertEqual(m.EvidenceLink.objects.count(), 1)
        for person in get_user_model().objects.filter(username__startswith="demo."):
            self.assertFalse(person.has_usable_password())
        files_before = {}
        for evidence in m.EvidenceVersion.objects.all():
            data = Path(evidence.file.path).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), evidence.checksum)
            self.assertIn(b"FICTIONAL DEMONSTRATION EVIDENCE", data)
            files_before[evidence.file.name] = data
        task = m.Task.objects.first()
        task.title = "A local edit that must survive seeding"
        task.save()
        organization = m.Organization.objects.get()
        organization.name = "A renamed demonstration organization"
        organization.save()
        event_count = m.ActivityEvent.objects.count()
        self.seed()
        task.refresh_from_db()
        self.assertEqual(task.title, "A local edit that must survive seeding")
        self.assertEqual(m.Organization.objects.get().name, "A renamed demonstration organization")
        self.assertEqual(m.ActivityEvent.objects.count(), event_count)
        self.assertEqual(m.ControlImplementation.objects.count(), 93)
        self.assertEqual({e.file.name: Path(e.file.path).read_bytes() for e in m.EvidenceVersion.objects.all()}, files_before)

    def test_real_organization_is_never_modified(self):
        m.Organization.objects.create(name="Real organization", is_demo=False)
        with self.assertRaisesMessage(CommandError, "empty organization database"):
            self.seed()
        self.assertEqual(m.Organization.objects.get().name, "Real organization")
        self.assertFalse(self.manager.groups.exists())

    def test_business_data_without_organization_is_protected(self):
        m.Task.objects.create(title="Existing work")
        with self.assertRaisesMessage(CommandError, "Existing business records"):
            self.seed()
        self.assertEqual(m.Task.objects.get().title, "Existing work")

    def test_user_must_exist_and_demo_users_must_not_collide(self):
        with self.assertRaisesMessage(CommandError, "active account"):
            call_command("seed_demo", user="missing", stdout=StringIO())
        get_user_model().objects.create_user(username="demo.amina", password=None)
        with self.assertRaisesMessage(CommandError, "Reserved demo usernames"):
            self.seed()
        self.assertFalse(m.Organization.objects.exists())

    def test_failed_seed_rolls_back_database_and_removes_only_new_files(self):
        untouched = Path(self.media.name) / "pre-existing-file.txt"
        untouched.write_text("This unrelated file must survive.")

        def fail_after_uploads(actor, model, **fields):
            if model is m.ControlImplementation:
                raise RuntimeError("Simulated interrupted seed")
            return create_record(actor, model, **fields)

        with patch("workspace.management.commands.seed_demo.create_record", side_effect=fail_after_uploads):
            with self.assertRaisesMessage(RuntimeError, "Simulated interrupted seed"):
                self.seed()
        self.assertFalse(m.Organization.objects.exists())
        self.assertFalse(m.EvidenceVersion.objects.exists())
        self.assertFalse(self.manager.groups.exists())
        self.assertFalse(get_user_model().objects.filter(username__startswith="demo.").exists())
        remaining = [path for path in Path(self.media.name).rglob("*") if path.is_file()]
        self.assertEqual(remaining, [untouched])
