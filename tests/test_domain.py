"""Business-authority, frozen-version and traceability acceptance checks."""
import hashlib
import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from workspace import models as m
from workspace import services as s
from workspace.permissions import can_approve, can_edit, can_view, ensure_roles, visible_queryset

urlpatterns = []  # Allows this domain suite to run independently of unfinished HTTP views.


class DomainTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        roles = ensure_roles()
        cls.manager = get_user_model().objects.create_user('manager', first_name='ISMS', last_name='Manager')
        cls.manager.groups.add(roles['Manager'])
        cls.approver = get_user_model().objects.create_user('approver')
        cls.approver.groups.add(roles['Approver'])
        cls.risk_owner = get_user_model().objects.create_user('risk.owner')
        cls.risk_owner.groups.add(roles['Risk owner'])
        cls.control_owner = get_user_model().objects.create_user('control.owner')
        cls.control_owner.groups.add(roles['Control owner'])
        cls.auditor = get_user_model().objects.create_user('auditor')
        cls.auditor.groups.add(roles['Internal auditor'])
        cls.external = get_user_model().objects.create_user('external')
        cls.external.groups.add(roles['External auditor'])
        cls.viewer = get_user_model().objects.create_user('viewer')
        cls.viewer.groups.add(roles['Viewer'])
        cls.admin = get_user_model().objects.create_user('sysadmin', is_staff=True, is_superuser=True)
        cls.admin.groups.add(roles['System administrator'])
        cls.framework = m.FrameworkVersion.objects.create(name='Test framework', edition='2022 + 2024', catalog_release='test')
        cls.control = m.ControlReference.objects.create(framework=cls.framework, identifier='A.5.15', title='Access authorization', summary='Original test summary.', theme='organizational')
        cls.requirement_reference = m.RequirementReference.objects.create(framework=cls.framework, identifier='9', title='Performance evaluation', summary='Original test summary.')

    def setUp(self):
        self.media = tempfile.TemporaryDirectory(prefix='nava-domain-')
        self.override = override_settings(MEDIA_ROOT=self.media.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(self.media.cleanup)

    def create(self, model, **fields):
        fields.setdefault('title', model.__name__)
        fields.setdefault('owner', self.manager)
        return s.create_record(self.manager, model, **fields)

    def approve(self, record, actor=None):
        s.transition_record(self.manager, record, 'submit')
        return s.approve_record(actor or self.approver, record, 'Reviewed for the recorded purpose.')

    def scope(self, approved=True):
        scope = self.create(m.ScopeVersion, statement='Operate the customer service platform.', boundaries='Application operations and support team.', climate_relevance='not_relevant', climate_rationale='Context review identified no additional direct requirement.')
        return self.approve(scope) if approved else scope

    def methodology(self, approved=True):
        method = self.create(m.RiskMethodologyVersion)
        return self.approve(method) if approved else method

    def risk(self, approved=True, **fields):
        fields.setdefault('methodology', self.methodology())
        fields.setdefault('owner', self.risk_owner)
        fields.setdefault('scenario', 'An unrevoked service account is misused after a contractor leaves.')
        fields.setdefault('scoring_rationale', 'Quarterly reviews have found several stale accounts; misuse would expose customer data.')
        risk = self.create(m.RiskAssessmentVersion, **fields)
        return self.approve(risk) if approved else risk

    def evidence(self, accepted=True, **fields):
        fields.setdefault('title', 'Access review test record')
        fields.setdefault('owner', self.control_owner)
        evidence = s.upload_evidence(self.manager, SimpleUploadedFile('review.txt', b'Fictional evidence test bytes.', content_type='text/plain'), **fields)
        if accepted:
            s.transition_record(self.manager, evidence, 'review_evidence', 'Reviewed the named accounts and coverage period.')
            s.transition_record(self.manager, evidence, 'accept_evidence', 'Accepted as supporting evidence for this access review sample.')
        return evidence

    def finding_action(self):
        audit = self.create(m.Audit, auditor=self.auditor, independence_notes='Auditor is independent of operations.', report='Two sample exceptions were recorded.')
        finding = self.create(m.Finding, owner=self.control_owner, audit=audit, control=self.control, condition='One departure ticket lacked account disablement evidence.', objective_evidence='Sample ticket EX-42 lacked the required timestamp.')
        action = self.create(m.CorrectiveAction, owner=self.control_owner, finding=finding, root_cause='Checklist did not require a final account verification.', plan='Add independent verification and train the service desk.', implementation_notes='Checklist published and service desk trained.', effectiveness_notes='Independent sampling found all departures verified.', evidence=[self.evidence()])
        return finding, action

    def test_scope_approval_revision_preserves_original_and_creates_impact_task(self):
        scope = self.scope()
        original_statement = scope.statement
        revised = s.revise_record(self.manager, scope, {'statement': 'Expanded operations and new regional support team.'})
        scope.refresh_from_db()
        self.assertEqual(scope.statement, original_statement)
        self.assertEqual(scope.status, 'approved')
        self.assertEqual(revised.version, 2)
        self.assertEqual(revised.previous_id, scope.pk)
        self.assertEqual(revised.series, scope.series)
        self.assertEqual(revised.status, 'draft')
        self.assertTrue(m.Task.objects.filter(scope=revised, title__contains='Review impact').exists())

    def test_scope_requires_climate_relevance_rationale_and_boundaries(self):
        scope = self.create(m.ScopeVersion, statement='Service operations')
        s.transition_record(self.manager, scope, 'submit')
        with self.assertRaisesMessage(ValidationError, 'boundaries'):
            s.approve_record(self.approver, scope)
        scope.refresh_from_db()
        self.assertEqual(scope.status, 'in_review')
        self.assertEqual(m.Approval.objects.count(), 0)

    def test_obligation_links_party_risk_and_control(self):
        scope = self.scope()
        party = self.create(m.InterestedParty, scope=scope, expectations='Disable departed contractor accounts promptly.')
        obligation = self.create(m.Requirement, scope=scope, party=party, source='Fictional service contract section 6', applicability_rationale='Applies to customer support access.', controls=[self.control])
        risk = self.risk(scope=scope, requirements=[obligation], controls=[self.control])
        self.assertEqual(risk.requirements.get().party_id, party.pk)
        self.assertEqual(risk.controls.get(), obligation.controls.get())

    def test_risk_requires_approved_methodology_and_keeps_scores_when_control_linked(self):
        method = self.methodology(approved=False)
        risk = self.risk(approved=False, methodology=method)
        s.transition_record(self.manager, risk, 'submit')
        with self.assertRaisesMessage(ValidationError, 'methodology'):
            s.approve_record(self.approver, risk)
        self.approve(method)
        original_score = risk.current_score
        s.update_record(self.manager, risk, {'controls': [self.control]}, risk.revision)
        s.approve_record(self.approver, risk)
        self.assertEqual(risk.current_score, original_score)
        self.assertEqual(risk.methodology_id, method.pk)

    def test_treatment_and_acceptance_require_business_authority(self):
        risk = self.risk()
        treatment = self.create(m.TreatmentPlan, risk=risk, owner=self.risk_owner, rationale='Reduce stale privileged access.', actions='Run monthly access review and timely offboarding.', controls=[self.control])
        s.transition_record(self.manager, treatment, 'submit')
        with self.assertRaises(PermissionDenied):
            s.approve_record(self.manager, treatment)
        s.approve_record(self.risk_owner, treatment)
        acceptance = self.create(m.RiskAcceptance, risk=risk, treatment=treatment, owner=self.risk_owner, rationale='Accept recorded current exposure while the approved treatment is implemented.', accepted_score=risk.current_score, expires_on=timezone.localdate() + timedelta(days=90))
        s.transition_record(self.manager, acceptance, 'submit')
        with self.assertRaises(PermissionDenied):
            s.approve_record(self.viewer, acceptance)
        s.approve_record(self.risk_owner, acceptance)
        self.assertEqual(acceptance.status, 'approved')
        self.assertTrue(m.Approval.objects.filter(object_id=acceptance.pk, actor=self.risk_owner).exists())

    def test_acceptance_cannot_reduce_score_by_claim_or_accept_expired_period(self):
        risk = self.risk()
        acceptance = self.create(m.RiskAcceptance, risk=risk, rationale='Residual acceptance rationale.', accepted_score=1, expires_on=timezone.localdate() - timedelta(days=1))
        s.transition_record(self.manager, acceptance, 'submit')
        with self.assertRaises(ValidationError) as caught:
            s.approve_record(self.approver, acceptance)
        self.assertIn('future expiry', str(caught.exception))
        self.assertIn('current risk score', str(caught.exception))

    def test_system_administrator_is_not_automatic_business_approver(self):
        scope = self.scope(approved=False)
        s.transition_record(self.manager, scope, 'submit')
        self.assertFalse(can_approve(self.admin, scope))
        with self.assertRaises(PermissionDenied):
            s.approve_record(self.admin, scope)
        with self.assertRaises(PermissionDenied):
            s.create_record(self.admin, m.Task, title='Unauthorized business action')

    def test_generic_approval_cannot_approve_tasks_or_bypass_evidence_review(self):
        task = self.create(m.Task)
        evidence = self.evidence(accepted=False)
        self.assertFalse(can_approve(self.approver, task))
        with self.assertRaises(PermissionDenied):
            s.approve_record(self.approver, task)
        with self.assertRaises(ValidationError):
            s.approve_record(self.manager, evidence)

    def test_soa_reports_omissions_and_freezes_complete_applicability(self):
        scope = self.scope()
        soa = self.create(m.SoAVersion, scope=scope, framework=self.framework)
        s.transition_record(self.manager, soa, 'submit')
        with self.assertRaisesMessage(ValidationError, 'omissions'):
            s.approve_record(self.approver, soa)
        row = self.create(m.ControlImplementation, scope=scope, control=self.control, applicability='applicable', justification='Required by the customer obligation and risk assessment.')
        s.approve_record(self.approver, soa)
        frozen = soa.snapshot[0]['justification']
        s.update_record(self.manager, row, {'justification': 'Revised current reasoning.'}, row.revision)
        soa.refresh_from_db()
        self.assertEqual(soa.snapshot[0]['justification'], frozen)
        self.assertEqual(soa.omissions, [])

    def test_evidence_review_and_immutable_new_file_versions(self):
        original = self.evidence()
        digest = hashlib.sha256(b'Fictional evidence test bytes.').hexdigest()
        self.assertEqual(original.checksum, digest)
        new = s.upload_evidence(self.manager, SimpleUploadedFile('review-next.txt', b'Updated sample bytes.'), previous=original, title='Next access review')
        self.assertEqual(new.version, 2)
        self.assertEqual(new.previous_id, original.pk)
        self.assertNotEqual(new.file.name, original.file.name)
        self.assertEqual(original.file.read(), b'Fictional evidence test bytes.')
        self.assertEqual(new.file.read(), b'Updated sample bytes.')
        self.assertEqual(new.status, 'uploaded')

    def test_evidence_acceptance_requires_review_and_nonexpired_period(self):
        evidence = self.evidence(accepted=False, expires_on=timezone.localdate() - timedelta(days=1))
        with self.assertRaisesMessage(ValidationError, 'Expired'):
            s.transition_record(self.manager, evidence, 'accept_evidence', 'Accepting current evidence.')
        s.update_record(self.manager, evidence, {'expires_on': timezone.localdate() + timedelta(days=20)})
        with self.assertRaisesMessage(ValidationError, 'Review the evidence'):
            s.transition_record(self.manager, evidence, 'accept_evidence', 'Accepting current evidence.')
        with self.assertRaises(PermissionDenied):
            s.transition_record(self.viewer, evidence, 'review_evidence', 'Review attempt.')

    def test_evidence_rejects_executable_and_oversized_uploads(self):
        with self.assertRaisesMessage(ValidationError, 'Allowed files'):
            s.upload_evidence(self.manager, SimpleUploadedFile('payload.html', b'<script>alert(1)</script>'), title='Unsafe content')
        with override_settings(NAVA_MAX_UPLOAD_BYTES=4):
            with self.assertRaisesMessage(ValidationError, 'smaller'):
                s.upload_evidence(self.manager, SimpleUploadedFile('too-big.txt', b'12345'), title='Too big')
        self.assertEqual(m.EvidenceVersion.objects.count(), 0)

    def test_document_publication_requires_approval_and_preserves_prior_version(self):
        doc = self.create(m.DocumentVersion, body='Policy body.', approver=self.approver, controls=[self.control])
        with self.assertRaises(ValidationError):
            s.transition_record(self.approver, doc, 'publish')
        self.approve(doc)
        with self.assertRaises(PermissionDenied):
            s.transition_record(self.manager, doc, 'publish')
        s.transition_record(self.approver, doc, 'publish')
        revised = s.revise_record(self.manager, doc)
        s.update_record(self.manager, revised, {'body': 'Updated policy body.'})
        doc.refresh_from_db()
        self.assertEqual(doc.body, 'Policy body.')
        self.assertEqual(doc.status, 'published')
        self.assertEqual(revised.body, 'Updated policy body.')
        self.assertEqual(revised.controls.get(), self.control)

    def test_approved_content_and_forward_reverse_relationships_are_frozen(self):
        risk = self.risk(controls=[self.control])
        risk.scenario = 'Mutated approved scenario'
        with self.assertRaisesMessage(ValidationError, 'frozen'):
            risk.save()
        with self.assertRaisesMessage(ValidationError, 'relationships'), transaction.atomic():
            risk.controls.clear()
        with self.assertRaisesMessage(ValidationError, 'relationships'), transaction.atomic():
            self.control.risks.remove(risk)
        self.assertEqual(risk.controls.count(), 1)

    def test_restricted_records_are_filtered_for_manager_without_explicit_access(self):
        private = s.create_record(self.control_owner, m.DocumentVersion, title='Restricted employee record', body='Private detail.', classification='restricted')
        self.assertFalse(can_view(self.manager, private))
        self.assertFalse(visible_queryset(self.manager, m.DocumentVersion).filter(pk=private.pk).exists())
        self.assertTrue(can_view(self.control_owner, private))
        self.assertFalse(can_view(self.viewer, private))

    def test_external_shares_expire_and_revision_preserves_expiry(self):
        evidence = self.evidence(classification='restricted')
        expiry = timezone.now() + timedelta(days=7)
        with self.assertRaisesMessage(ValidationError, 'expiry'):
            s.share_record(self.manager, evidence, [self.external], reason='Audit review')
        s.share_record(self.manager, evidence, [self.external], expires_at=expiry, reason='Time limited audit review')
        self.assertTrue(can_view(self.external, evidence))
        self.assertEqual(evidence.status, 'accepted')
        self.assertEqual(evidence.file.read(), b'Fictional evidence test bytes.')
        new = s.upload_evidence(self.manager, SimpleUploadedFile('new.txt', b'New evidence.'), previous=evidence, title='Updated review')
        self.assertEqual(new.access_expires, expiry)
        self.assertEqual(new.classification, 'restricted')
        s.share_record(self.manager, evidence, [], reason='Audit access revoked')
        self.assertFalse(can_view(self.external, evidence))
        with self.assertRaises(PermissionDenied):
            s.share_record(self.viewer, evidence, [self.viewer], reason='Unauthorized share')

    def test_owner_can_edit_unchanged_access_fields_but_cannot_reassign(self):
        task = self.create(m.Task, owner=self.control_owner)
        s.update_record(self.control_owner, task, {'description': 'An owner edit.', 'owner': self.control_owner, 'classification': 'internal'})
        with self.assertRaises(PermissionDenied):
            s.update_record(self.control_owner, task, {'owner': self.viewer})

    def test_corrective_action_requires_approved_plan_and_independent_verification(self):
        finding, action = self.finding_action()
        with self.assertRaisesMessage(ValidationError, 'authorized approval'):
            s.transition_record(self.auditor, action, 'close', 'Verified effective.')
        s.transition_record(self.approver, action, 'approve_plan', 'Resources and corrective approach approved.')
        s.transition_record(self.control_owner, action, 'start')
        self.control_owner.groups.add(ensure_roles()['Internal auditor'])
        with self.assertRaisesMessage(ValidationError, 'independent'):
            s.transition_record(self.control_owner, action, 'close', 'Self review is invalid.')
        s.transition_record(self.auditor, action, 'close', 'Independent sample supports sustained effectiveness.')
        self.assertEqual(action.status, 'closed')
        self.assertEqual(action.verified_by, self.auditor)
        s.transition_record(self.auditor, finding, 'close', 'All corrective actions independently verified.')
        self.assertEqual(finding.status, 'closed')

    def test_changed_corrective_plan_requires_new_approval(self):
        _, action = self.finding_action()
        s.transition_record(self.approver, action, 'approve_plan', 'Approved.')
        s.update_record(self.manager, action, {'plan': 'A different remediation plan.'})
        with self.assertRaisesMessage(ValidationError, 'authorized approval'):
            s.transition_record(self.auditor, action, 'close', 'Verification rationale.')

    def test_closed_action_requires_reopen_and_preserves_closure_event(self):
        _, action = self.finding_action()
        s.transition_record(self.approver, action, 'approve_plan', 'Approved.')
        s.transition_record(self.auditor, action, 'close', 'Independent check passed.')
        with self.assertRaises(PermissionDenied):
            s.update_record(self.manager, action, {'plan': 'Silent historical change.'})
        s.transition_record(self.manager, action, 'reopen', 'New sample found recurrence.')
        self.assertEqual(action.status, 'open')
        self.assertIsNone(action.verified_by)
        self.assertTrue(m.ActivityEvent.objects.filter(object_id=action.pk, action='record.close').exists())
        self.assertTrue(m.ActivityEvent.objects.filter(object_id=action.pk, action='record.reopen').exists())

    def test_management_review_freezes_records_considered(self):
        scope = self.scope()
        task = self.create(m.Task, scope=scope, title='Original action')
        review = self.create(m.ManagementReview, scope=scope, attendees='Manager and authorized approver', minutes='Reviewed open actions and current risks.', decisions='Fund the access review remediation.', actions=[task])
        self.approve(review)
        s.update_record(self.manager, task, {'title': 'Changed current action'})
        review.refresh_from_db()
        self.assertEqual(review.snapshot['tasks'][0]['title'], 'Original action')

    def test_internal_audit_records_conflict_and_external_stages_are_separate(self):
        internal = self.create(m.Audit, auditor=self.manager, report='Sample report.', independence_notes='Same owner and auditor.')
        with self.assertRaisesMessage(ValidationError, 'distinct'):
            s.transition_record(self.manager, internal, 'complete')
        stage1 = self.create(m.Audit, audit_type='stage1', report='Stage 1 report recorded.', independence_notes='External certification body auditor.')
        stage2 = self.create(m.Audit, audit_type='stage2')
        s.transition_record(self.manager, stage1, 'complete')
        stage2.refresh_from_db()
        self.assertEqual(stage2.status, 'draft')
        self.assertFalse(m.CertificationRecord.objects.exists())

    def test_certification_decision_requires_supporting_documentation(self):
        record = self.create(m.CertificationRecord, scope=self.scope(), decision='granted')
        s.transition_record(self.manager, record, 'submit')
        with self.assertRaisesMessage(ValidationError, 'requires issuer'):
            s.approve_record(self.approver, record)

    def test_recurring_generation_is_idempotent_and_inherits_access(self):
        source = self.create(m.Task, due_date=timezone.localdate() - timedelta(days=65), recurrence_days=30, classification='restricted', allowed_users=[self.control_owner])
        first = s.generate_recurring_tasks(self.manager)
        second = s.generate_recurring_tasks(self.manager)
        self.assertEqual(len(first), 2)
        self.assertEqual(second, [])
        self.assertEqual(m.Task.objects.filter(recurrence_source=source).count(), 2)
        self.assertTrue(all(task.allowed_users.filter(pk=self.control_owner.pk).exists() for task in first))

    def test_dependencies_block_completion_and_cycles_are_rejected(self):
        before = self.create(m.Task, title='Before')
        after = self.create(m.Task, title='After', dependencies=[before])
        with self.assertRaisesMessage(ValidationError, 'blocking'):
            s.transition_record(self.manager, after, 'complete', 'Claimed completion.')
        with self.assertRaisesMessage(ValidationError, 'cycle'):
            s.update_record(self.manager, before, {'dependencies': [after]})
        s.transition_record(self.manager, before, 'complete', 'Required predecessor output recorded.')
        s.transition_record(self.manager, after, 'complete', 'Dependent output recorded.')
        self.assertEqual(after.status, 'complete')

    def test_optimistic_revision_rejects_lost_updates(self):
        task = self.create(m.Task, title='Original task')
        stale = m.Task.objects.get(pk=task.pk)
        expected = stale.revision
        s.update_record(self.manager, task, {'title': 'First editor changed this'}, expected)
        with self.assertRaisesMessage(ValidationError, 'changed while'):
            s.update_record(self.manager, stale, {'title': 'Second editor lost update'}, expected)
        stale.refresh_from_db()
        self.assertEqual(stale.title, 'First editor changed this')

    def test_business_events_and_approvals_are_append_only(self):
        scope = self.scope()
        approval = m.Approval.objects.filter(object_id=scope.pk).first()
        approval.reason = 'Overwritten history'
        with self.assertRaisesMessage(ValidationError, 'append-only'):
            approval.save()
        event = m.ActivityEvent.objects.filter(action='record.approved').first()
        with self.assertRaisesMessage(ValidationError, 'append-only'):
            event.delete()

    def test_role_setup_is_repeatable_without_assigning_authority(self):
        before = set(self.admin.groups.values_list('name', flat=True))
        first = ensure_roles()
        second = ensure_roles()
        self.assertEqual(set(first), set(second))
        self.assertEqual({name: group.pk for name, group in first.items()}, {name: group.pk for name, group in second.items()})
        self.assertEqual(set(self.admin.groups.values_list('name', flat=True)), before)

    def test_snapshot_derivative_redacts_restricted_sources_and_revoked_links(self):
        scope = self.scope()
        risk = self.risk(approved=False, scope=scope, classification='restricted')
        review = self.create(m.ManagementReview, scope=scope, attendees='Authorized reviewers', minutes='Discussed risk and actions.', decisions='Fund the proposed improvement.')
        # Give the approver explicit access to the underlying restricted record.
        s.share_record(self.manager, risk, [self.approver], reason='Authorized risk review')
        self.approve(risk)
        self.approve(review)
        self.assertEqual(review.snapshot['risks'][0]['scenario'], risk.scenario)
        derivative = s.filtered_snapshot(self.viewer, review.snapshot)
        self.assertNotIn(risk.scenario, str(derivative))
        self.assertEqual(derivative['risks'][0], {'omitted': 'Restricted or unavailable source record'})
        self.assertEqual(review.snapshot['risks'][0]['scenario'], risk.scenario)
        s.share_record(self.manager, risk, [], reason='Underlying risk access revoked after review')
        self.assertNotIn(risk.scenario, str(s.filtered_snapshot(self.approver, review.snapshot)))

    def test_soa_snapshot_derivative_redacts_restricted_implementation(self):
        scope = self.scope()
        implementation = self.create(m.ControlImplementation, scope=scope, control=self.control,
                                     classification='restricted', applicability='applicable',
                                     justification='Restricted acquisition risk rationale.')
        rows, _ = s.soa_snapshot(self.manager, scope, self.framework)
        self.assertIn(implementation.justification, str(rows))
        derivative = s.filtered_snapshot(self.viewer, rows)
        self.assertNotIn(implementation.justification, str(derivative))
        self.assertEqual(derivative[0]['identifier'], self.control.identifier)
        self.assertTrue(derivative[0]['omissions'])

    def test_blind_evidence_link_does_not_allow_completion_or_corrective_closure(self):
        evidence = self.evidence(classification='restricted', owner=self.manager)
        task = self.create(m.Task, owner=self.control_owner, requires_evidence=True, evidence=[evidence])
        self.assertFalse(can_view(self.control_owner, evidence))
        with self.assertRaisesMessage(ValidationError, 'accepted, current evidence'):
            s.transition_record(self.control_owner, task, 'complete', 'I cannot see the attached evidence.')
        finding, action = self.finding_action()
        s.update_record(self.manager, action, {'evidence': [evidence]})
        s.transition_record(self.approver, action, 'approve_plan', 'Approved corrective approach.')
        self.assertFalse(can_view(self.auditor, evidence))
        with self.assertRaisesMessage(ValidationError, 'accepted, current evidence'):
            s.transition_record(self.auditor, action, 'close', 'Blind verification must not be accepted.')

    def test_acceptance_cannot_use_a_treatment_for_another_risk_version(self):
        first = self.risk()
        other = self.risk()
        treatment = self.create(m.TreatmentPlan, risk=other, rationale='Treatment for the other risk.',
                                actions='Apply selected controls.', controls=[self.control])
        self.approve(treatment)
        acceptance = self.create(m.RiskAcceptance, risk=first, treatment=treatment,
                                 rationale='Claimed acceptance.', accepted_score=first.current_score,
                                 expires_on=timezone.localdate() + timedelta(days=30))
        s.transition_record(self.manager, acceptance, 'submit')
        with self.assertRaisesMessage(ValidationError, 'same risk assessment'):
            s.approve_record(self.approver, acceptance)
