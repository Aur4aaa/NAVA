"""HTTP permission and workflow regressions, using real views and forms."""
import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from workspace import models as m
from workspace.permissions import ensure_roles
from workspace.registry import MODULES
from workspace.services import create_record, transition_record, upload_evidence


TEST_STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


@override_settings(STORAGES=TEST_STORAGES)
class HttpWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        User = get_user_model()
        cls.manager = User.objects.create_user('manager', password='Test-only-passphrase-847!')
        cls.manager.groups.add(Group.objects.get(name='Manager'))
        cls.approver = User.objects.create_user('approver', password='Test-only-passphrase-849!')
        cls.approver.groups.add(Group.objects.get(name='Approver'))
        cls.viewer = User.objects.create_user('viewer', password='Test-only-passphrase-845!')
        cls.viewer.groups.add(Group.objects.get(name='Viewer'))
        cls.contributor = User.objects.create_user('contributor', password='Test-only-passphrase-843!')
        cls.contributor.groups.add(Group.objects.get(name='Contributor'))
        cls.external = User.objects.create_user('external', password='Test-only-passphrase-841!')
        cls.external.groups.add(Group.objects.get(name='External auditor'))
        cls.administrator = User.objects.create_superuser('administrator', password='Test-only-passphrase-839!')

    def setUp(self):
        cache.clear()
        self.media = tempfile.TemporaryDirectory(prefix='nava-http-evidence-')
        self.media_override = override_settings(MEDIA_ROOT=self.media.name)
        self.media_override.enable()
        self.addCleanup(self.media.cleanup)
        self.addCleanup(self.media_override.disable)

    def scope(self, **changes):
        fields = {'title': 'HTTP test scope', 'statement': 'Hosting the customer support service.', 'boundaries': 'One support team and its application.', 'owner': self.manager, 'climate_relevance': 'not_relevant', 'climate_rationale': 'No material climate dependency identified for this review.'}
        fields.update(changes)
        return create_record(self.manager, m.ScopeVersion, **fields)

    def scope_post(self, **changes):
        data = {'title': 'HTTP-created scope', 'statement': 'Delivery of the support service.', 'boundaries': 'Support team and infrastructure.', 'owner': str(self.manager.pk), 'classification': 'internal', 'climate_relevance': 'not_relevant', 'climate_rationale': 'Reviewed relevant dependencies; no material issue identified.'}
        data.update(changes)
        return data

    def upload(self, **changes):
        fields = {'title': 'Restricted board evidence', 'description': 'Board-secret-description-7281', 'owner': self.manager, 'classification': 'restricted'}
        fields.update(changes)
        return upload_evidence(self.manager, SimpleUploadedFile('minutes.txt', b'Private operating record, fictional test data.', content_type='text/plain'), **fields)

    def action(self, kind, record, action, **data):
        return self.client.post(f'/records/{kind}/{record.pk}/action/{action}/', {'revision': record.revision, 'reason': 'Reviewed the scope and its documented boundaries.', **data})

    def test_anonymous_pages_and_file_links_require_authentication(self):
        evidence = self.upload()
        for url in ['/', '/records/scopes/', '/search/?q=board', f'/evidence/{evidence.pk}/download/']:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith('/accounts/login/?next='))
        self.assertEqual(self.client.get('/health/').json(), {'status': 'ok'})

    def test_empty_workspace_pages_and_all_register_forms_render(self):
        self.client.force_login(self.manager)
        for url in ['/', '/roadmap/', '/traceability/', '/approvals/', '/search/']:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        for kind in MODULES:
            with self.subTest(kind=kind):
                self.assertEqual(self.client.get(f'/records/{kind}/').status_code, 200)
                self.assertEqual(self.client.get(f'/records/{kind}/new/').status_code, 200)

    def test_scope_http_create_approve_and_revise_preserves_approved_content(self):
        self.client.force_login(self.manager)
        response = self.client.post('/records/scopes/new/', self.scope_post())
        self.assertEqual(response.status_code, 302)
        scope = m.ScopeVersion.objects.get(title='HTTP-created scope')
        original_statement = scope.statement
        response = self.action('scopes', scope, 'submit')
        self.assertEqual(response.status_code, 302)
        scope.refresh_from_db()
        self.assertEqual(scope.status, 'in_review')
        self.client.force_login(self.approver)
        self.assertEqual(self.action('scopes', scope, 'approve').status_code, 302)
        scope.refresh_from_db()
        self.assertEqual(scope.status, 'approved')
        self.assertEqual(m.Approval.objects.filter(object_id=scope.pk).count(), 1)
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(f'/records/scopes/{scope.pk}/edit/').status_code, 403)
        response = self.action('scopes', scope, 'revise')
        self.assertEqual(response.status_code, 302)
        revised = m.ScopeVersion.objects.get(previous=scope)
        self.assertEqual(revised.status, 'draft')
        self.assertEqual(revised.version, 2)
        response = self.client.post(f'/records/scopes/{revised.pk}/edit/', self.scope_post(title='Expanded scope', statement='Expanded service boundary.', expected_revision=revised.revision))
        self.assertEqual(response.status_code, 302)
        scope.refresh_from_db()
        revised.refresh_from_db()
        self.assertEqual(scope.statement, original_statement)
        self.assertEqual(scope.status, 'approved')
        self.assertEqual(revised.statement, 'Expanded service boundary.')
        self.assertTrue(m.Task.objects.filter(scope=revised, stage=1).exists())

    def test_viewer_and_system_administrator_cannot_approve_business_records(self):
        scope = self.scope()
        transition_record(self.manager, scope, 'submit')
        for user in [self.viewer, self.administrator]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.post('/records/scopes/new/', self.scope_post()).status_code, 403)
                self.assertIn(self.client.get(f'/records/scopes/{scope.pk}/edit/').status_code, (403, 404))
                self.assertIn(self.action('scopes', scope, 'approve').status_code, (403, 404))
                scope.refresh_from_db()
                self.assertEqual(scope.status, 'in_review')
        self.assertFalse(m.Approval.objects.exists())

    def test_restricted_evidence_hidden_from_guessed_url_search_and_exports(self):
        evidence = self.upload()
        self.client.force_login(self.viewer)
        for url in [f'/records/evidence/{evidence.pk}/', f'/records/evidence/{evidence.pk}/edit/', f'/evidence/{evidence.pk}/download/']:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
        response = self.client.get('/records/evidence/')
        self.assertNotContains(response, evidence.title)
        response = self.client.get('/search/?q=board')
        self.assertNotContains(response, evidence.title)
        self.assertNotContains(response, evidence.description)
        for format in ['csv', 'xlsx', 'pdf']:
            with self.subTest(format=format):
                response = self.client.get(f'/records/evidence/export/{format}/')
                self.assertEqual(response.status_code, 200)
                if format == 'csv':
                    self.assertNotContains(response, evidence.title)
        self.assertNotContains(self.client.get('/records/tasks/new/'), evidence.title, status_code=403)

    def test_related_field_querysets_do_not_disclose_restricted_records(self):
        evidence = self.upload()
        self.client.force_login(self.contributor)
        response = self.client.get('/records/tasks/new/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, evidence.title)
        response = self.client.post('/records/tasks/new/', {'title': 'Illicit linked task', 'classification': 'internal', 'stage': 1, 'priority': 'medium', 'evidence': [evidence.pk]})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertFalse(m.Task.objects.filter(title='Illicit linked task').exists())

    def test_evidence_upload_download_and_review_are_real_http_operations(self):
        self.client.force_login(self.manager)
        payload = b'Operating review data for the selected period.'
        response = self.client.post('/records/evidence/new/', {'title': 'Access review evidence', 'owner': self.manager.pk, 'classification': 'internal', 'collected_on': timezone.localdate().isoformat(), 'file': SimpleUploadedFile('access-review.txt', payload, content_type='text/plain')})
        self.assertEqual(response.status_code, 302)
        evidence = m.EvidenceVersion.objects.get(title='Access review evidence')
        self.assertEqual(evidence.status, 'uploaded')
        self.assertEqual(evidence.size_bytes, len(payload))
        response = self.client.get(f'/evidence/{evidence.pk}/download/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertEqual(response['Content-Type'], 'application/octet-stream')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(b''.join(response.streaming_content), payload)
        self.assertEqual(self.action('evidence', evidence, 'review_evidence').status_code, 302)
        evidence.refresh_from_db()
        self.assertEqual(evidence.status, 'reviewed')
        self.assertEqual(self.action('evidence', evidence, 'accept_evidence').status_code, 302)
        evidence.refresh_from_db()
        self.assertEqual(evidence.status, 'accepted')

    def test_concurrent_edits_reject_stale_revision_without_lost_update(self):
        scope = self.scope()
        old_revision = scope.revision
        self.client.force_login(self.manager)
        response = self.client.post(f'/records/scopes/{scope.pk}/edit/', self.scope_post(title='First editor saved', expected_revision=old_revision))
        self.assertEqual(response.status_code, 302)
        response = self.client.post(f'/records/scopes/{scope.pk}/edit/', self.scope_post(title='Stale editor overwrite', expected_revision=old_revision))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'changed while you were editing')
        scope.refresh_from_db()
        self.assertEqual(scope.title, 'First editor saved')
        self.assertGreater(scope.revision, old_revision)
        self.assertEqual(self.action('scopes', scope, 'submit', revision=old_revision).status_code, 302)
        scope.refresh_from_db()
        self.assertEqual(scope.status, 'draft')

    def test_csrf_is_required_for_mutations_and_actions_are_post_only(self):
        scope = self.scope()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.manager)
        url = f'/records/scopes/{scope.pk}/action/submit/'
        self.assertEqual(client.get(url).status_code, 405)
        self.assertEqual(client.post(url, {'revision': scope.revision}).status_code, 403)
        client.get(f'/records/scopes/{scope.pk}/')
        token = client.cookies['csrftoken'].value
        self.assertEqual(client.post(url, {'revision': scope.revision, 'csrfmiddlewaretoken': token}).status_code, 302)
        scope.refresh_from_db()
        self.assertEqual(scope.status, 'in_review')

    def test_login_failure_is_audited_without_credentials(self):
        password = 'incorrect-private-value-abc'
        response = self.client.post('/accounts/login/', {'username': self.manager.username, 'password': password})
        self.assertEqual(response.status_code, 200)
        event = m.ActivityEvent.objects.get(action='auth.login_failed')
        self.assertNotIn(password, event.detail)
        self.assertIsNone(event.actor)
        response = self.client.post('/accounts/login/', {'username': self.manager.username, 'password': 'Test-only-passphrase-847!'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(m.ActivityEvent.objects.filter(action='auth.login', actor=self.manager).exists())

    def test_expired_evidence_and_overdue_tasks_have_actionable_filtered_views(self):
        evidence = self.upload(classification='internal', expires_on=timezone.localdate() - timedelta(days=1))
        task = create_record(self.manager, m.Task, title='Overdue review action', owner=self.manager, due_date=timezone.localdate() - timedelta(days=1))
        self.client.force_login(self.manager)
        response = self.client.get('/')
        self.assertContains(response, '/records/tasks/?overdue=1')
        self.assertContains(response, '/records/evidence/?expired=1')
        self.assertContains(self.client.get('/records/evidence/?expired=1'), evidence.title)
        self.assertContains(self.client.get('/records/tasks/?overdue=1'), task.title)

    def test_existing_record_detail_pages_render(self):
        scope = self.scope()
        framework = m.FrameworkVersion.objects.create(name='Test framework', edition='2022', catalog_release='http-test')
        reference = m.RequirementReference.objects.create(framework=framework, identifier='4', title='Context')
        control = m.ControlReference.objects.create(framework=framework, identifier='A.5.1', title='Policy direction', theme='organizational')
        party = create_record(self.manager, m.InterestedParty, title='Customer', owner=self.manager, scope=scope)
        methodology = create_record(self.manager, m.RiskMethodologyVersion, title='Methodology', owner=self.manager)
        risk = create_record(self.manager, m.RiskAssessmentVersion, title='Unauthorized access', owner=self.manager, scope=scope, methodology=methodology)
        treatment = create_record(self.manager, m.TreatmentPlan, title='Access treatment', owner=self.manager, risk=risk)
        audit = create_record(self.manager, m.Audit, title='Internal audit', owner=self.manager, scope=scope)
        finding = create_record(self.manager, m.Finding, title='Access finding', owner=self.manager, audit=audit)
        records = {'scopes': scope, 'parties': party, 'methodologies': methodology, 'risks': risk, 'treatments': treatment, 'audits': audit, 'findings': finding}
        fixture_fields = {
            'requirements': {'scope': scope, 'party': party},
            'gaps': {'scope': scope, 'requirement': reference},
            'acceptances': {'risk': risk, 'treatment': treatment, 'rationale': 'Documented rationale', 'expires_on': timezone.localdate() + timedelta(days=30)},
            'controls': {'scope': scope, 'control': control},
            'soa': {'scope': scope, 'framework': framework},
            'documents': {'scope': scope, 'body': 'Working policy content'},
            'tasks': {'scope': scope},
            'actions': {'finding': finding},
            'reviews': {'scope': scope},
            'certifications': {'scope': scope},
            'packs': {'scope': scope, 'framework': framework},
        }
        for kind, fields in fixture_fields.items():
            records[kind] = create_record(self.manager, MODULES[kind].model, title=f'Fixture {kind}', owner=self.manager, **fields)
        records['evidence'] = self.upload()
        self.client.force_login(self.manager)
        for kind, record in records.items():
            with self.subTest(kind=kind):
                self.assertEqual(self.client.get(f'/records/{kind}/{record.pk}/').status_code, 200)
                self.assertEqual(self.client.get(f'/records/{kind}/{record.pk}/edit/').status_code, 200)

