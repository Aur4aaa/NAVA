"""Relational ISMS records. Approved versions are frozen at application level.

A host/database administrator can still alter storage; this is not a tamper-proof ledger.
"""
import uuid
from pathlib import Path

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

USER = settings.AUTH_USER_MODEL
CLASSIFICATIONS = [('internal', 'Internal'), ('confidential', 'Confidential'), ('restricted', 'Restricted')]
STATUS = [('draft', 'Draft'), ('in_review', 'In review'), ('approved', 'Approved'), ('published', 'Published'), ('superseded', 'Superseded'), ('open', 'Open'), ('in_progress', 'In progress'), ('complete', 'Complete'), ('closed', 'Closed'), ('uploaded', 'Uploaded'), ('reviewed', 'Reviewed'), ('accepted', 'Accepted'), ('rejected', 'Rejected'), ('scheduled', 'Scheduled')]
IMPLEMENTATION = [('not_assessed', 'Not assessed'), ('planned', 'Planned'), ('partial', 'Partially implemented'), ('implemented', 'Implemented')]


def evidence_path(instance, filename):
    return f'versions/{uuid.uuid4().hex}{Path(filename).suffix.lower()}'


class Organization(models.Model):
    name = models.CharField(max_length=180, default='Your organization')
    timezone = models.CharField(max_length=64, default='Asia/Kuala_Lumpur')
    description = models.TextField(blank=True)
    is_demo = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Record(models.Model):
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(USER, null=True, blank=True, on_delete=models.PROTECT, related_name='owned_%(class)s_records')
    created_by = models.ForeignKey(USER, null=True, blank=True, on_delete=models.PROTECT, related_name='created_%(class)s_records')
    status = models.CharField(max_length=24, choices=STATUS, default='draft', db_index=True)
    revision = models.PositiveIntegerField(default=1)
    classification = models.CharField(max_length=20, choices=CLASSIFICATIONS, default='internal')
    allowed_users = models.ManyToManyField(USER, blank=True, related_name='shared_%(class)s_records')
    access_expires = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-updated_at', '-pk']

    @property
    def identifier(self):
        prefix = getattr(self, 'PREFIX', self.__class__.__name__[:3].upper())
        return f'{prefix}-{self.pk:03d}' if self.pk else f'{prefix}-NEW'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            if prior:
                if self.revision != prior.revision:
                    raise ValidationError('This record changed while you were editing. Reload it before saving.')
                if isinstance(self, VersionedRecord) and prior.status in self.FROZEN_STATUSES and not getattr(self, '_allow_transition', False):
                    raise ValidationError('Approved versions are frozen. Create a revision to make changes.')
                self.revision += 1
                if kwargs.get('update_fields'):
                    kwargs['update_fields'] = set(kwargs['update_fields']) | {'revision', 'updated_at'}
        try:
            return super().save(*args, **kwargs)
        finally:
            # The internal transition capability is single-use, not sticky on an instance.
            self.__dict__.pop('_allow_transition', None)

    def delete(self, *args, **kwargs):
        if isinstance(self, VersionedRecord) and self.status in self.FROZEN_STATUSES:
            raise ValidationError('Approved and audited versions must be retained.')
        return super().delete(*args, **kwargs)


class VersionedRecord(Record):
    series = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)
    version = models.PositiveIntegerField(default=1)
    previous = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='revisions')
    FROZEN_STATUSES = ('approved', 'published', 'superseded')

    class Meta(Record.Meta):
        abstract = True
        constraints = [models.UniqueConstraint(fields=['series', 'version'], name='%(app_label)s_%(class)s_series_version')]


class ScopeVersion(VersionedRecord):
    PREFIX = 'SCP'
    statement = models.TextField()
    boundaries = models.TextField(blank=True)
    exclusions = models.TextField(blank=True)
    locations = models.TextField(blank=True)
    processes = models.TextField(blank=True)
    technologies = models.TextField(blank=True)
    interfaces = models.TextField(blank=True)
    climate_relevance = models.CharField(max_length=12, choices=[('undecided', 'Not assessed'), ('relevant', 'Relevant'), ('not_relevant', 'Not relevant')], default='undecided')
    climate_rationale = models.TextField(blank=True)
    review_date = models.DateField(null=True, blank=True)


class FrameworkVersion(models.Model):
    name = models.CharField(max_length=160)
    edition = models.CharField(max_length=100)
    catalog_release = models.CharField(max_length=100, default='r1')
    source_url = models.URLField(blank=True)
    verified_on = models.DateField(null=True, blank=True)
    provenance = models.TextField(blank=True)
    verification_status = models.CharField(max_length=24, default='unverified')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['name', 'edition', 'catalog_release'], name='unique_framework_edition')]

    def __str__(self):
        return f'{self.name} · {self.edition}'


class RequirementReference(models.Model):
    framework = models.ForeignKey(FrameworkVersion, on_delete=models.PROTECT, related_name='requirements')
    identifier = models.CharField(max_length=30)
    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True)
    mandatory = models.BooleanField(default=True)
    provenance = models.TextField(blank=True)

    class Meta:
        ordering = ['identifier']
        constraints = [models.UniqueConstraint(fields=['framework', 'identifier'], name='unique_requirement_reference')]

    def __str__(self):
        return f'{self.identifier} · {self.title}'


class ControlReference(models.Model):
    framework = models.ForeignKey(FrameworkVersion, on_delete=models.PROTECT, related_name='controls')
    identifier = models.CharField(max_length=30)
    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True)
    theme = models.CharField(max_length=30, choices=[('organizational', 'Organizational'), ('people', 'People'), ('physical', 'Physical'), ('technological', 'Technological')])
    is_custom = models.BooleanField(default=False)
    provenance = models.TextField(blank=True)

    class Meta:
        ordering = ['identifier']
        constraints = [models.UniqueConstraint(fields=['framework', 'identifier'], name='unique_control_reference')]

    def __str__(self):
        return f'{self.identifier} · {self.title}'


class InterestedParty(Record):
    PREFIX = 'PTY'
    scope = models.ForeignKey(ScopeVersion, null=True, blank=True, on_delete=models.PROTECT, related_name='interested_parties')
    party_type = models.CharField(max_length=40, default='customer')
    expectations = models.TextField(blank=True)
    climate_requirements = models.TextField(blank=True)
    review_date = models.DateField(null=True, blank=True)


class Requirement(Record):
    PREFIX = 'REQ'
    scope = models.ForeignKey(ScopeVersion, null=True, blank=True, on_delete=models.PROTECT, related_name='obligations')
    party = models.ForeignKey(InterestedParty, null=True, blank=True, on_delete=models.PROTECT, related_name='requirements')
    source = models.CharField(max_length=500, blank=True)
    jurisdiction = models.CharField(max_length=120, blank=True)
    requirement_type = models.CharField(max_length=30, choices=[('legal', 'Legal'), ('regulatory', 'Regulatory'), ('contractual', 'Contractual'), ('customer', 'Customer'), ('internal', 'Internal')], default='contractual')
    applicability_rationale = models.TextField(blank=True)
    review_date = models.DateField(null=True, blank=True)
    controls = models.ManyToManyField(ControlReference, blank=True, related_name='obligations')


class Asset(Record):
    PREFIX = 'AST'
    scope = models.ForeignKey(ScopeVersion, null=True, blank=True, on_delete=models.PROTECT, related_name='assets')
    asset_type = models.CharField(max_length=40, default='process')
    custodian = models.CharField(max_length=160, blank=True)
    criticality = models.CharField(max_length=20, default='medium')
    confidentiality = models.PositiveSmallIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(5)])
    integrity = models.PositiveSmallIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(5)])
    availability = models.PositiveSmallIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(5)])
    dependencies = models.ManyToManyField('self', symmetrical=False, blank=True)


class Supplier(Record):
    PREFIX = 'SUP'
    scope = models.ForeignKey(ScopeVersion, null=True, blank=True, on_delete=models.PROTECT, related_name='suppliers')
    service = models.TextField(blank=True)
    information_access = models.TextField(blank=True)
    criticality = models.CharField(max_length=20, default='medium')
    review_date = models.DateField(null=True, blank=True)


def default_likelihood():
    return {'1': 'Rare: exceptional circumstances', '2': 'Unlikely: plausible but not expected', '3': 'Possible: could occur during the review period', '4': 'Likely: expected during the review period', '5': 'Almost certain: frequent or imminent'}


def default_impact():
    return {'1': 'Negligible: brief local disruption', '2': 'Minor: recoverable departmental impact', '3': 'Moderate: material service or contractual impact', '4': 'Major: significant organization-wide harm', '5': 'Severe: existential or prolonged critical harm'}


class RiskMethodologyVersion(VersionedRecord):
    PREFIX = 'MET'
    likelihood_criteria = models.JSONField(default=default_likelihood)
    impact_criteria = models.JSONField(default=default_impact)
    acceptance_threshold = models.PositiveSmallIntegerField(default=6, validators=[MinValueValidator(1), MaxValueValidator(25)])
    acceptance_authority = models.TextField(default='Assigned risk owner or a user explicitly assigned the Approver role.')
    review_frequency_days = models.PositiveIntegerField(default=180)


class RiskAssessmentVersion(VersionedRecord):
    PREFIX = 'RSK'
    scope = models.ForeignKey(ScopeVersion, null=True, blank=True, on_delete=models.PROTECT, related_name='risks')
    methodology = models.ForeignKey(RiskMethodologyVersion, on_delete=models.PROTECT, related_name='assessments')
    scenario = models.TextField(blank=True)
    causes = models.TextField(blank=True)
    consequences = models.TextField(blank=True)
    existing_controls = models.TextField(blank=True)
    likelihood = models.PositiveSmallIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(5)])
    impact = models.PositiveSmallIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(5)])
    current_likelihood = models.PositiveSmallIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(5)])
    current_impact = models.PositiveSmallIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(5)])
    scoring_rationale = models.TextField(blank=True)
    assessment_date = models.DateField(default=timezone.localdate)
    review_date = models.DateField(null=True, blank=True)
    requirements = models.ManyToManyField(Requirement, blank=True, related_name='risks')
    assets = models.ManyToManyField(Asset, blank=True, related_name='risks')
    controls = models.ManyToManyField(ControlReference, blank=True, related_name='risks')

    class Meta(VersionedRecord.Meta):
        constraints = VersionedRecord.Meta.constraints + [models.CheckConstraint(condition=models.Q(likelihood__gte=1, likelihood__lte=5, impact__gte=1, impact__lte=5, current_likelihood__gte=1, current_likelihood__lte=5, current_impact__gte=1, current_impact__lte=5), name='risk_scores_1_to_5')]

    @property
    def score(self):
        return self.likelihood * self.impact

    @property
    def current_score(self):
        return self.current_likelihood * self.current_impact

    @property
    def level(self):
        return 'critical' if self.current_score >= 20 else 'high' if self.current_score >= 12 else 'medium' if self.current_score >= 6 else 'low'


class TreatmentPlan(VersionedRecord):
    PREFIX = 'TRT'
    risk = models.ForeignKey(RiskAssessmentVersion, on_delete=models.PROTECT, related_name='treatments')
    decision = models.CharField(max_length=20, choices=[('modify', 'Modify / mitigate'), ('avoid', 'Avoid'), ('share', 'Share / transfer'), ('retain', 'Retain / accept')], default='modify')
    rationale = models.TextField(blank=True)
    actions = models.TextField(blank=True)
    resources = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    target_likelihood = models.PositiveSmallIntegerField(default=2, validators=[MinValueValidator(1), MaxValueValidator(5)])
    target_impact = models.PositiveSmallIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(5)])
    controls = models.ManyToManyField(ControlReference, blank=True, related_name='treatment_plans')

    @property
    def target_score(self):
        return self.target_likelihood * self.target_impact


class RiskAcceptance(VersionedRecord):
    PREFIX = 'ACC'
    risk = models.ForeignKey(RiskAssessmentVersion, on_delete=models.PROTECT, related_name='acceptances')
    treatment = models.ForeignKey(TreatmentPlan, null=True, blank=True, on_delete=models.PROTECT, related_name='acceptances')
    rationale = models.TextField()
    expires_on = models.DateField()
    accepted_score = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(25)])


class ControlImplementation(Record):
    PREFIX = 'CTL'
    scope = models.ForeignKey(ScopeVersion, null=True, blank=True, on_delete=models.PROTECT, related_name='implementations')
    control = models.ForeignKey(ControlReference, on_delete=models.PROTECT, related_name='implementations')
    applicability = models.CharField(max_length=20, choices=[('undecided', 'Undecided'), ('applicable', 'Applicable'), ('excluded', 'Excluded')], default='undecided')
    justification = models.TextField(blank=True)
    implementation_status = models.CharField(max_length=24, choices=IMPLEMENTATION, default='not_assessed')
    implementation_notes = models.TextField(blank=True)
    effectiveness = models.CharField(max_length=20, choices=[('not_tested', 'Not tested'), ('effective', 'Effective'), ('ineffective', 'Ineffective')], default='not_tested')
    effectiveness_notes = models.TextField(blank=True)
    tested_on = models.DateField(null=True, blank=True)
    review_date = models.DateField(null=True, blank=True)
    risks = models.ManyToManyField(RiskAssessmentVersion, blank=True, related_name='implementations')
    requirements = models.ManyToManyField(Requirement, blank=True, related_name='implementations')
    evidence = models.ManyToManyField('EvidenceVersion', blank=True, related_name='implementations')
    documents = models.ManyToManyField('DocumentVersion', blank=True, related_name='implementations')

    class Meta(Record.Meta):
        constraints = [models.UniqueConstraint(fields=['scope', 'control'], name='unique_scope_control_implementation')]


class GapAssessment(VersionedRecord):
    PREFIX = 'GAP'
    scope = models.ForeignKey(ScopeVersion, null=True, blank=True, on_delete=models.PROTECT, related_name='gap_assessments')
    requirement = models.ForeignKey(RequirementReference, null=True, blank=True, on_delete=models.PROTECT)
    control = models.ForeignKey(ControlReference, null=True, blank=True, on_delete=models.PROTECT)
    implementation_status = models.CharField(max_length=24, choices=IMPLEMENTATION, default='not_assessed')
    effectiveness_verified = models.BooleanField(default=False)
    rationale = models.TextField(blank=True)
    assessment_date = models.DateField(default=timezone.localdate)
    priority = models.CharField(max_length=20, default='medium')
    evidence = models.ManyToManyField('EvidenceVersion', blank=True, related_name='gap_assessments')

    class Meta(VersionedRecord.Meta):
        constraints = VersionedRecord.Meta.constraints + [models.CheckConstraint(condition=(models.Q(requirement__isnull=False, control__isnull=True) | models.Q(requirement__isnull=True, control__isnull=False)), name='gap_exactly_one_reference')]


class SoAVersion(VersionedRecord):
    PREFIX = 'SOA'
    scope = models.ForeignKey(ScopeVersion, on_delete=models.PROTECT, related_name='soa_versions')
    framework = models.ForeignKey(FrameworkVersion, on_delete=models.PROTECT, related_name='soa_versions')
    snapshot = models.JSONField(default=list, blank=True)
    omissions = models.JSONField(default=list, blank=True)


class DocumentVersion(VersionedRecord):
    PREFIX = 'DOC'
    scope = models.ForeignKey(ScopeVersion, null=True, blank=True, on_delete=models.PROTECT, related_name='documents')
    document_type = models.CharField(max_length=30, default='policy')
    body = models.TextField(blank=True)
    change_summary = models.TextField(blank=True)
    reviewer = models.ForeignKey(USER, null=True, blank=True, on_delete=models.PROTECT, related_name='documents_to_review')
    approver = models.ForeignKey(USER, null=True, blank=True, on_delete=models.PROTECT, related_name='documents_to_approve')
    effective_date = models.DateField(null=True, blank=True)
    review_date = models.DateField(null=True, blank=True)
    controls = models.ManyToManyField(ControlReference, blank=True, related_name='documents')


class EvidenceVersion(VersionedRecord):
    PREFIX = 'EVD'
    FROZEN_STATUSES = ('accepted', 'approved', 'published', 'superseded')
    scope = models.ForeignKey(ScopeVersion, null=True, blank=True, on_delete=models.PROTECT, related_name='evidence_versions')
    file = models.FileField(upload_to=evidence_path, blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    checksum = models.CharField(max_length=64, blank=True, editable=False)
    size_bytes = models.PositiveBigIntegerField(default=0)
    content_type = models.CharField(max_length=100, blank=True)
    source = models.CharField(max_length=500, blank=True)
    external_url = models.URLField(blank=True)
    collected_on = models.DateField(default=timezone.localdate)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    reviewer = models.ForeignKey(USER, null=True, blank=True, on_delete=models.PROTECT, related_name='evidence_to_review')
    retention_rule = models.TextField(blank=True)
    retention_hold = models.BooleanField(default=False)
    controls = models.ManyToManyField(ControlReference, blank=True, related_name='evidence_versions')
    risks = models.ManyToManyField(RiskAssessmentVersion, blank=True, related_name='evidence_versions')

    @property
    def is_expired(self):
        return self.expires_on is not None and self.expires_on < timezone.localdate()

    def save(self, *args, **kwargs):
        if self.pk:
            old = type(self).objects.get(pk=self.pk)
            if old.file.name != self.file.name or old.checksum != self.checksum:
                raise ValidationError('Evidence file bytes and checksums are immutable. Upload a new version.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.retention_hold or self.audit_packs.exists():
            raise ValidationError('Evidence under retention hold or included in an audit pack cannot be deleted.')
        return super().delete(*args, **kwargs)


class EvidenceLink(models.Model):
    evidence = models.ForeignKey(EvidenceVersion, on_delete=models.PROTECT, related_name='trace_links')
    requirement = models.ForeignKey(Requirement, null=True, blank=True, on_delete=models.PROTECT, related_name='evidence_links')
    control = models.ForeignKey(ControlReference, null=True, blank=True, on_delete=models.PROTECT, related_name='evidence_links')
    risk = models.ForeignKey(RiskAssessmentVersion, null=True, blank=True, on_delete=models.PROTECT, related_name='evidence_links')
    purpose = models.TextField()
    created_by = models.ForeignKey(USER, null=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class Task(Record):
    PREFIX = 'TSK'
    STAGES = [(1, 'Context & scope'), (2, 'Leadership & objectives'), (3, 'Gap assessment'), (4, 'Risk & treatment'), (5, 'SoA & controls'), (6, 'Documents & evidence'), (7, 'Monitoring & competence'), (8, 'Internal audit'), (9, 'Management review'), (10, 'Stage 1 preparation'), (11, 'Stage 2 preparation'), (12, 'Certification maintenance')]
    scope = models.ForeignKey(ScopeVersion, null=True, blank=True, on_delete=models.PROTECT, related_name='tasks')
    stage = models.PositiveSmallIntegerField(choices=STAGES, default=1)
    priority = models.CharField(max_length=20, choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')], default='medium')
    due_date = models.DateField(null=True, blank=True, db_index=True)
    dependencies = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='dependent_tasks')
    evidence = models.ManyToManyField(EvidenceVersion, blank=True, related_name='tasks')
    required_output = models.TextField(blank=True)
    completion_notes = models.TextField(blank=True)
    requires_evidence = models.BooleanField(default=False)
    recurrence_days = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    recurrence_source = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='recurrences')
    recurrence_key = models.CharField(max_length=100, unique=True, null=True, blank=True)

    @property
    def overdue(self):
        return bool(self.due_date and self.due_date < timezone.localdate() and self.status not in ('complete', 'closed'))

    @property
    def blockers(self):
        return self.dependencies.exclude(status__in=['complete', 'closed'])


class Approval(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.PositiveIntegerField()
    record = GenericForeignKey('content_type', 'object_id')
    actor = models.ForeignKey(USER, on_delete=models.PROTECT)
    decision = models.CharField(max_length=30, default='approved')
    reason = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError('Approval records are append-only.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Approval records are append-only.')


class Audit(Record):
    PREFIX = 'AUD'
    scope = models.ForeignKey(ScopeVersion, null=True, blank=True, on_delete=models.PROTECT, related_name='audits')
    audit_type = models.CharField(max_length=20, choices=[('internal', 'Internal audit'), ('stage1', 'Stage 1'), ('stage2', 'Stage 2'), ('surveillance', 'Surveillance'), ('recertification', 'Recertification')], default='internal')
    scheduled_date = models.DateField(null=True, blank=True)
    completed_date = models.DateField(null=True, blank=True)
    criteria = models.TextField(blank=True)
    auditor = models.ForeignKey(USER, null=True, blank=True, on_delete=models.PROTECT, related_name='audit_assignments')
    independence_notes = models.TextField(blank=True)
    certification_body = models.CharField(max_length=200, blank=True)
    recommendation = models.TextField(blank=True)
    report = models.TextField(blank=True)
    evidence = models.ManyToManyField(EvidenceVersion, blank=True, related_name='audits')


class Finding(Record):
    PREFIX = 'FND'
    audit = models.ForeignKey(Audit, on_delete=models.PROTECT, related_name='findings')
    requirement = models.ForeignKey(RequirementReference, null=True, blank=True, on_delete=models.PROTECT)
    control = models.ForeignKey(ControlReference, null=True, blank=True, on_delete=models.PROTECT)
    condition = models.TextField(blank=True)
    objective_evidence = models.TextField(blank=True)
    severity = models.CharField(max_length=20, choices=[('observation', 'Observation'), ('minor', 'Minor'), ('major', 'Major')], default='minor')
    due_date = models.DateField(null=True, blank=True)
    evidence = models.ManyToManyField(EvidenceVersion, blank=True, related_name='findings')


class CorrectiveAction(Record):
    PREFIX = 'CAP'
    finding = models.ForeignKey(Finding, on_delete=models.PROTECT, related_name='corrective_actions')
    correction = models.TextField(blank=True)
    root_cause = models.TextField(blank=True)
    plan = models.TextField(blank=True)
    implementation_notes = models.TextField(blank=True)
    effectiveness_notes = models.TextField(blank=True)
    verified_by = models.ForeignKey(USER, null=True, blank=True, on_delete=models.PROTECT, related_name='verified_actions')
    verified_on = models.DateField(null=True, blank=True)
    closure_rationale = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    evidence = models.ManyToManyField(EvidenceVersion, blank=True, related_name='corrective_actions')


class ManagementReview(VersionedRecord):
    PREFIX = 'REV'
    scope = models.ForeignKey(ScopeVersion, null=True, blank=True, on_delete=models.PROTECT, related_name='management_reviews')
    meeting_date = models.DateField(default=timezone.localdate)
    attendees = models.TextField(blank=True)
    agenda = models.TextField(blank=True)
    minutes = models.TextField(blank=True)
    decisions = models.TextField(blank=True)
    resource_needs = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    actions = models.ManyToManyField(Task, blank=True, related_name='management_reviews')


class MetricResult(Record):
    PREFIX = 'KPI'
    scope = models.ForeignKey(ScopeVersion, null=True, blank=True, on_delete=models.PROTECT)
    definition = models.TextField(blank=True)
    data_source = models.TextField(blank=True)
    target = models.CharField(max_length=100, blank=True)
    period = models.CharField(max_length=100, blank=True)
    result = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=30, blank=True)
    interpretation = models.TextField(blank=True)


class CertificationRecord(VersionedRecord):
    PREFIX = 'CRT'
    scope = models.ForeignKey(ScopeVersion, on_delete=models.PROTECT, related_name='certifications')
    decision = models.CharField(max_length=24, choices=[('pending', 'Pending decision'), ('granted', 'Granted'), ('suspended', 'Suspended'), ('withdrawn', 'Withdrawn'), ('expired', 'Expired')], default='pending')
    issuer = models.CharField(max_length=200, blank=True)
    certificate_number = models.CharField(max_length=120, blank=True)
    certified_scope = models.TextField(blank=True)
    standard_edition = models.CharField(max_length=100, default='ISO/IEC 27001:2022 + Amd 1:2024')
    issued_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    supporting_evidence = models.ForeignKey(EvidenceVersion, null=True, blank=True, on_delete=models.PROTECT, related_name='certification_decisions')
    next_surveillance = models.DateField(null=True, blank=True)


class AuditPack(VersionedRecord):
    PREFIX = 'PAK'
    FROZEN_STATUSES = ('complete', 'approved', 'published', 'superseded')
    scope = models.ForeignKey(ScopeVersion, on_delete=models.PROTECT, related_name='audit_packs')
    framework = models.ForeignKey(FrameworkVersion, null=True, blank=True, on_delete=models.PROTECT)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    selection_criteria = models.TextField(blank=True)
    manifest = models.JSONField(default=dict, blank=True)
    file = models.FileField(upload_to='audit-packs/', blank=True)
    checksum = models.CharField(max_length=64, blank=True)
    evidence = models.ManyToManyField(EvidenceVersion, blank=True, related_name='audit_packs')


class ActivityEvent(models.Model):
    actor = models.ForeignKey(USER, null=True, blank=True, on_delete=models.PROTECT)
    action = models.CharField(max_length=80, db_index=True)
    content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.PROTECT)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    record = GenericForeignKey('content_type', 'object_id')
    record_label = models.CharField(max_length=280, blank=True)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at', '-pk']

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError('Activity events are append-only.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Activity events are append-only.')


# Related-manager writes do not call Model.save(). Protect the content relations of
# frozen versions in both directions (including control.risks.add(approved_risk)).
# Access membership is intentionally separate: share_record can grant/revoke access
# to a frozen version without changing the content approved by its reviewer.
from django.db.models.signals import m2m_changed
from django.dispatch import receiver


@receiver(m2m_changed, dispatch_uid='nava.protect_frozen_version_relations')
def protect_frozen_version_relations(sender, instance, action, reverse, model, pk_set, **kwargs):
    if action not in {'pre_add', 'pre_remove', 'pre_clear'}:
        return
    for versioned_model in VersionedRecord.__subclasses__():
        for field in versioned_model._meta.many_to_many:
            if field.name == 'allowed_users' or field.remote_field.through is not sender:
                continue
            if reverse:
                queryset = versioned_model.objects.filter(pk__in=pk_set) if pk_set is not None else versioned_model.objects.filter(**{field.name: instance})
            else:
                queryset = versioned_model.objects.filter(pk=instance.pk)
            if queryset.filter(status__in=versioned_model.FROZEN_STATUSES).exists():
                raise ValidationError('The relationships of an approved version are frozen. Create a revision to change them.')
