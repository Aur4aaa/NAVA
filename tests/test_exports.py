import csv
import hashlib
import io
import json
import tempfile
import zipfile
from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from openpyxl import load_workbook

from workspace import models as m
from workspace.exports import build_audit_pack, export_table, pack_download_response, spreadsheet_safe
from workspace.permissions import ensure_roles
from workspace.services import approve_record, create_record, revise_record, share_record, transition_record, upload_evidence


class ExportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        roles = ensure_roles()
        cls.manager = get_user_model().objects.create_user('export-manager', password='long-test-password')
        cls.manager.groups.add(roles['Manager'], roles['Approver'])
        cls.viewer = get_user_model().objects.create_user('export-viewer', password='long-test-password')
        cls.viewer.groups.add(roles['Viewer'])
        cls.external = get_user_model().objects.create_user('external-auditor', password='long-test-password')
        cls.external.groups.add(roles['External auditor'])
        cls.other = get_user_model().objects.create_user('unrelated-user', password='long-test-password')
        cls.other.groups.add(roles['Manager'])
        cls.scope = create_record(cls.manager, m.ScopeVersion, title='Managed services', statement='Cloud platform operations', boundaries='Primary service environment and operations team', climate_relevance='not_relevant', climate_rationale='Recorded organizational assessment for this fixture.', owner=cls.manager)
        transition_record(cls.manager, cls.scope, 'submit')
        approve_record(cls.manager, cls.scope, reason='Approved boundary')
        cls.framework = m.FrameworkVersion.objects.create(name='Example framework', edition='2022', provenance='Test-only original reference data')

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=Path(self.temp_dir.name))
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(self.temp_dir.cleanup)

    def evidence(self, title='Access review', body=b'Original review bytes', **extra):
        return upload_evidence(self.manager, SimpleUploadedFile('review.txt', body, content_type='text/plain'), title=title, owner=self.manager, scope=self.scope, **extra)

    def package(self, evidence=None, **extra):
        pack = create_record(self.manager, m.AuditPack, title='Stage 1 selected materials', scope=self.scope, framework=self.framework, owner=self.manager, selection_criteria='Approved records and the selected access review.', **extra)
        if evidence:
            pack.evidence.add(*evidence)
        return pack

    def archive(self, response):
        try:
            return zipfile.ZipFile(io.BytesIO(b''.join(response.streaming_content)))
        finally:
            response.close()

    def test_formula_prefixes_are_neutralized_in_csv_and_xlsx(self):
        title = ' \t=HYPERLINK("https://invalid.example", "click")'
        create_record(self.manager, m.Task, title=title, description='@SUM(1,2)', owner=self.manager)
        response = export_table(self.manager, 'tasks', m.Task.objects.all(), 'csv')
        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8-sig'))))
        self.assertTrue(rows[1][1].startswith("'"))
        self.assertEqual(rows[1][2], "'@SUM(1,2)")
        workbook = load_workbook(io.BytesIO(export_table(self.manager, 'tasks', m.Task.objects.all(), 'xlsx').content))
        self.assertEqual(workbook.active['B2'].data_type, 's')
        self.assertTrue(workbook.active['B2'].value.startswith("'"))
        for text in ['=1', '+1', '-1', '@x', ' \t=1', '\ufeff +1', '\r=1']:
            self.assertTrue(spreadsheet_safe(text).startswith("'"), text)

    def test_export_filters_restricted_records_even_for_unfiltered_queryset(self):
        create_record(self.manager, m.Task, title='Visible work', owner=self.manager)
        create_record(self.manager, m.Task, title='Restricted investigation', owner=self.manager, classification='restricted')
        response = export_table(self.viewer, 'tasks', m.Task.objects.all(), 'csv')
        self.assertIn(b'Visible work', response.content)
        self.assertNotIn(b'Restricted investigation', response.content)

    def test_soa_export_has_all_catalog_rows_and_pdf_is_real_document(self):
        call_command('seed_framework', verbosity=0)
        framework = m.FrameworkVersion.objects.exclude(pk=self.framework.pk).first()
        soa = create_record(self.manager, m.SoAVersion, title='Working SoA', scope=self.scope, framework=framework, owner=self.manager)
        rows = list(csv.reader(io.StringIO(export_table(self.manager, 'soa', m.SoAVersion.objects.filter(pk=soa.pk), 'csv').content.decode('utf-8-sig'))))
        self.assertEqual(len(rows), 94)
        self.assertTrue(any('No applicability decision' in cell for row in rows[1:] for cell in row))
        pdf = export_table(self.manager, 'scopes', m.ScopeVersion.objects.all(), 'pdf')
        self.assertTrue(pdf.content.startswith(b'%PDF-'))
        self.assertGreater(len(pdf.content), 1000)

    def test_frozen_soa_export_redacts_currently_restricted_implementation(self):
        control = m.ControlReference.objects.create(framework=self.framework, identifier='A.5.1', title='Governance', summary='Original test summary', theme='organizational')
        implementation = create_record(self.manager, m.ControlImplementation, title='Restricted program', owner=self.manager, scope=self.scope, control=control, classification='restricted', justification='Confidential investigation rationale')
        soa = m.SoAVersion.objects.create(title='Approved snapshot', owner=self.manager, scope=self.scope, framework=self.framework, status='approved', snapshot=[{'identifier': control.identifier, 'summary': control.summary, 'record_id': implementation.pk, 'justification': implementation.justification, 'omissions': []}])
        response = export_table(self.viewer, 'soa', m.SoAVersion.objects.filter(pk=soa.pk), 'csv')
        self.assertIn(b'Original test summary', response.content)
        self.assertIn(b'Restricted or unavailable implementation', response.content)
        self.assertNotIn(b'Confidential investigation rationale', response.content)
        soa.refresh_from_db()
        self.assertEqual(soa.snapshot[0]['justification'], implementation.justification)

    def test_frozen_pack_preserves_exact_scope_and_evidence_versions(self):
        evidence = self.evidence()
        pack = self.package([evidence])
        build_audit_pack(self.manager, pack, pack.revision)
        original_checksum = pack.checksum
        revised = revise_record(self.manager, self.scope, {'statement': 'Expanded scope for next year'})
        replacement = upload_evidence(self.manager, SimpleUploadedFile('replacement.txt', b'New review bytes'), previous=evidence, title='Updated access review', owner=self.manager, scope=self.scope)
        archive = self.archive(pack_download_response(self.manager, pack))
        manifest = json.loads(archive.read('manifest.json'))
        frozen_scope = next(row for row in manifest['records'] if row['model'] == 'workspace.scopeversion')
        self.assertEqual(frozen_scope['id'], self.scope.pk)
        self.assertNotEqual(frozen_scope['id'], revised.pk)
        self.assertEqual(frozen_scope['statement'], 'Cloud platform operations')
        item = manifest['evidence'][0]
        self.assertEqual(item['id'], evidence.pk)
        self.assertNotEqual(item['id'], replacement.pk)
        self.assertEqual(archive.read(item['archive_path']), b'Original review bytes')
        self.assertEqual(item['checksum'], hashlib.sha256(b'Original review bytes').hexdigest())
        pack.refresh_from_db()
        self.assertEqual(pack.checksum, original_checksum)
        self.assertEqual(pack.status, 'complete')

    def test_package_requires_manager_approved_scope_and_current_revision(self):
        pack = self.package()
        with self.assertRaises(PermissionDenied):
            build_audit_pack(self.viewer, pack)
        with self.assertRaises(ValidationError):
            build_audit_pack(self.manager, pack, pack.revision + 1)
        draft_scope = create_record(self.manager, m.ScopeVersion, title='Draft boundary', statement='Draft', owner=self.manager)
        draft_pack = create_record(self.manager, m.AuditPack, title='Draft scope package', scope=draft_scope, framework=self.framework, owner=self.manager)
        with self.assertRaises(ValidationError):
            build_audit_pack(self.manager, draft_pack)

    def test_cross_scope_evidence_is_rejected(self):
        other_scope = create_record(self.manager, m.ScopeVersion, title='Other boundary', statement='Different scope', owner=self.manager)
        evidence = upload_evidence(self.manager, SimpleUploadedFile('elsewhere.txt', b'Other evidence'), title='Other evidence', owner=self.manager, scope=other_scope)
        pack = self.package([evidence])
        with self.assertRaisesMessage(ValidationError, 'All selected evidence'):
            build_audit_pack(self.manager, pack)
        pack.refresh_from_db()
        self.assertEqual(pack.status, 'draft')
        self.assertFalse(pack.file)

    def test_hidden_selected_evidence_is_rejected_without_packaging_it(self):
        evidence = upload_evidence(self.other, SimpleUploadedFile('restricted.txt', b'Hidden bytes'), title='Restricted file', owner=self.other, scope=self.scope, classification='restricted')
        pack = self.package([evidence])
        with self.assertRaises(PermissionDenied):
            build_audit_pack(self.manager, pack)

    def test_source_classification_raises_package_and_blocks_unshared_viewer(self):
        evidence = self.evidence(classification='restricted')
        pack = self.package([evidence])
        build_audit_pack(self.manager, pack)
        self.assertEqual(pack.classification, 'restricted')
        with self.assertRaises(PermissionDenied):
            pack_download_response(self.viewer, pack)

    def test_external_download_needs_timed_pack_and_evidence_shares(self):
        evidence = self.evidence(classification='restricted')
        pack = self.package([evidence])
        build_audit_pack(self.manager, pack)
        with self.assertRaises(PermissionDenied):
            pack_download_response(self.external, pack)
        expires = timezone.now() + timedelta(days=2)
        share_record(self.manager, pack, [self.external], expires_at=expires, reason='Named audit assignment')
        with self.assertRaises(PermissionDenied):
            pack_download_response(self.external, pack)
        share_record(self.manager, evidence, [self.external], expires_at=expires, reason='Named audit assignment')
        archive = self.archive(pack_download_response(self.external, pack))
        self.assertIn('manifest.json', archive.namelist())
        # Revocation applies to downloads even though the frozen package stays intact.
        share_record(self.manager, evidence, [], reason='Audit access revoked')
        with self.assertRaises(PermissionDenied):
            pack_download_response(self.external, pack)

    def test_corrupted_source_and_package_bytes_fail_integrity_checks(self):
        evidence = self.evidence()
        Path(evidence.file.path).write_bytes(b'Corrupted bytes')
        pack = self.package([evidence])
        with self.assertRaisesMessage(ValidationError, 'integrity check'):
            build_audit_pack(self.manager, pack)
        evidence2 = self.evidence(title='Intact evidence', body=b'Intact')
        pack2 = self.package([evidence2])
        build_audit_pack(self.manager, pack2)
        Path(pack2.file.path).write_bytes(b'Bad archive')
        with self.assertRaisesMessage(ValidationError, 'integrity verification failed'):
            pack_download_response(self.manager, pack2)

    def test_hidden_nested_review_snapshot_is_redacted_without_changing_original(self):
        hidden = create_record(self.other, m.Task, title='Private source action', owner=self.other, scope=self.scope, classification='restricted')
        review = m.ManagementReview.objects.create(title='Historical review', owner=self.manager, created_by=self.manager, scope=self.scope, status='approved', snapshot={'tasks': [{'model': 'workspace.task', 'id': hidden.pk, 'title': hidden.title}]})
        pack = self.package()
        build_audit_pack(self.manager, pack)
        snapshot = next(row for row in pack.manifest['records'] if row['model'] == 'workspace.managementreview')
        self.assertEqual(snapshot['snapshot']['tasks'], [{'omitted': 'Restricted or unavailable source record'}])
        review.refresh_from_db()
        self.assertEqual(review.snapshot['tasks'][0]['title'], 'Private source action')

    def test_frozen_pack_cannot_be_regenerated_or_relinked(self):
        pack = self.package([self.evidence()])
        build_audit_pack(self.manager, pack)
        with self.assertRaises(ValidationError):
            build_audit_pack(self.manager, pack)
        with self.assertRaises(ValidationError):
            pack.evidence.add(self.evidence(title='Late evidence'))
