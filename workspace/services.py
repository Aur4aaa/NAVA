"""Transactional business operations. Views must never write workflow states directly."""
import hashlib
import io
import json
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from . import models as m
from .permissions import can_approve, can_create, can_edit, can_view, has_role, require_edit, require_view, visible_queryset

PROTECTED_FIELDS = {'id', 'pk', 'status', 'revision', 'created_by', 'created_at', 'updated_at', 'series', 'version', 'previous', 'checksum', 'size_bytes', 'original_filename', 'content_type', 'snapshot', 'manifest', 'omissions', 'file', 'verified_by', 'verified_on', 'recurrence_key', 'recurrence_source'}
ALLOWED_UPLOADS = {'.pdf', '.txt', '.csv', '.png', '.jpg', '.jpeg', '.webp', '.xlsx', '.docx', '.json', '.log'}


def record_snapshot(record):
    """Serialize the exact version and relationship IDs at a decision boundary."""
    values = {'model': record._meta.label_lower, 'id': record.pk, 'identifier': str(getattr(record, 'identifier', record.pk))}
    for field in record._meta.concrete_fields:
        value = getattr(record, field.attname)
        if hasattr(value, 'isoformat'):
            value = value.isoformat()
        elif isinstance(value, (dict, list, int, float, bool)) or value is None:
            pass
        else:
            value = str(value)
        values[field.name] = value
    for field in record._meta.many_to_many:
        values[field.name] = list(getattr(record, field.name).values_list('pk', flat=True))
    return values


def filtered_snapshot(actor, value):
    """Return a permission-filtered derivative; never rewrite frozen source data.

    A parent review/SoA does not grant access to a linked restricted record. Recheck
    the current source policy, including revocations, before displaying its snapshot.
    """
    if isinstance(value, list):
        return [filtered_snapshot(actor, item) for item in value]
    if not isinstance(value, dict):
        return value
    source_model = None
    if value.get('model') and value.get('id'):
        try:
            source_model = apps.get_model(value['model'])
            source = source_model.objects.filter(pk=value['id']).first()
        except (LookupError, ValueError, TypeError):
            source = None
        if not source or not isinstance(source, m.Record) or not can_view(actor, source):
            return {'omitted': 'Restricted or unavailable source record'}
    # SoA rows use record_id rather than the general record snapshot schema.
    if value.get('record_id') and value.get('control_id'):
        source = m.ControlImplementation.objects.filter(pk=value['record_id']).first()
        if source is None or not can_view(actor, source):
            return {'identifier': value.get('identifier', ''), 'summary': value.get('summary', ''), 'omissions': ['Restricted or unavailable implementation omitted']}
    result = {}
    for key, entry in value.items():
        if key in {'file', 'allowed_users', 'access_expires'}:
            continue
        relation_model = None
        is_many = False
        if source_model is not None:
            try:
                field = source_model._meta.get_field(key)
            except Exception:
                field = None
            if field and field.is_relation and field.related_model and issubclass(field.related_model, m.Record):
                relation_model, is_many = field.related_model, field.many_to_many
        if relation_model is None:
            relation_model = {'risks': m.RiskAssessmentVersion, 'evidence': m.EvidenceVersion, 'documents': m.DocumentVersion}.get(key)
            is_many = relation_model is not None
        if relation_model and is_many and isinstance(entry, list) and all(isinstance(pk, int) for pk in entry):
            visible = set(visible_queryset(actor, relation_model).filter(pk__in=entry).values_list('pk', flat=True))
            result[key] = [pk for pk in entry if pk in visible]
            if len(result[key]) != len(entry):
                result[f'{key}_omissions'] = 'Restricted or unavailable links omitted'
        elif relation_model and not is_many and isinstance(entry, int):
            if visible_queryset(actor, relation_model).filter(pk=entry).exists():
                result[key] = entry
            else:
                result[key] = None
                result.setdefault('omitted_fields', []).append(key)
        else:
            result[key] = filtered_snapshot(actor, entry)
    return result


def log_event(actor, action, record=None, detail=''):
    return m.ActivityEvent.objects.create(actor=actor if actor and actor.is_authenticated else None, action=action,
        content_type=ContentType.objects.get_for_model(record) if record else None,
        object_id=record.pk if record else None,
        record_label=f'{getattr(record, "identifier", "")} {str(record)}'.strip()[:280] if record else '', detail=detail)


def _locked(record, expected_revision=None):
    current = type(record).objects.select_for_update().get(pk=record.pk)
    expected = expected_revision if expected_revision is not None else record.revision
    if int(expected) != current.revision:
        raise ValidationError('This record changed while you were editing. Reload it before saving.')
    return current


def _refresh(original, updated):
    original.refresh_from_db()
    return original


def _check_relations(actor, record, changes):
    for name, value in changes.items():
        try:
            field = record._meta.get_field(name)
        except Exception:
            raise ValidationError(f'Unknown field: {name}.')
        if field.is_relation:
            values = value if field.many_to_many else [value]
            for linked in values:
                if linked is None:
                    continue
                if isinstance(linked, m.Record) and not can_view(actor, linked):
                    raise PermissionDenied('A linked record is outside your authorized material.')
    if isinstance(record, m.Task) and record.pk and 'dependencies' in changes:
        pending = list(changes['dependencies'])
        visited = set()
        while pending:
            dependency = pending.pop()
            if dependency.pk == record.pk:
                raise ValidationError('Task dependencies cannot contain a cycle.')
            if dependency.pk not in visited:
                visited.add(dependency.pk)
                pending.extend(dependency.dependencies.all())


def _unchanged_access_fields(actor, record, changes):
    """Owner forms may submit unchanged access fields, never reassign or broaden them."""
    if has_role(actor, 'Manager'):
        return
    for name in {'owner', 'classification', 'allowed_users', 'access_expires'}.intersection(changes):
        supplied = changes[name]
        if name == 'allowed_users':
            unchanged = {u.pk for u in supplied} == set(record.allowed_users.values_list('pk', flat=True))
        else:
            unchanged = supplied == getattr(record, name)
        if not unchanged:
            raise PermissionDenied('Only an ISMS manager can reassign or share records.')


@transaction.atomic
def update_record(actor, record, changes, expected_revision=None):
    current = _locked(record, expected_revision)
    require_edit(actor, current)
    if set(changes).intersection(PROTECTED_FIELDS):
        raise ValidationError('Workflow state and version metadata must be changed through their dedicated actions.')
    _unchanged_access_fields(actor, current, changes)
    _check_relations(actor, current, changes)
    relations = {}
    for name, value in changes.items():
        field = current._meta.get_field(name)
        if field.many_to_many:
            relations[name] = value
        else:
            setattr(current, name, value)
    current.full_clean()
    current.save()
    for name, value in relations.items():
        getattr(current, name).set(value)
    log_event(actor, 'record.updated', current, 'Changed fields: ' + ', '.join(sorted(changes)))
    return _refresh(record, current)


@transaction.atomic
def create_record(actor, model, **fields):
    if not can_create(actor, model):
        raise PermissionDenied('Your role cannot create this type of record.')
    if set(fields).intersection(PROTECTED_FIELDS):
        raise ValidationError('Workflow and version metadata cannot be supplied when creating a record.')
    if not has_role(actor, 'Manager'):
        if fields.get('owner') not in (None, actor):
            raise PermissionDenied('Contributors may create only their own assigned records.')
        if fields.get('allowed_users') or fields.get('access_expires'):
            raise PermissionDenied('Only an ISMS manager can share records.')
        fields['owner'] = actor
    relations = {}
    for name in list(fields):
        if model._meta.get_field(name).many_to_many:
            relations[name] = fields.pop(name)
    record = model(created_by=actor, **fields)
    _check_relations(actor, record, {**fields, **relations})
    record.full_clean()
    record.save()
    for name, values in relations.items():
        getattr(record, name).set(values)
    log_event(actor, 'record.created', record)
    return record


@transaction.atomic
def revise_record(actor, record, changes=None):
    current = _locked(record)
    require_view(actor, current)
    if not isinstance(current, m.VersionedRecord) or isinstance(current, m.EvidenceVersion):
        raise ValidationError('Use the evidence upload action for a new file version; this record does not support text revisions.')
    if not can_create(actor, type(current)) or (not has_role(actor, 'Manager') and current.owner_id != actor.pk):
        raise PermissionDenied('Only the assigned owner or ISMS manager can create a revision.')
    changes = changes or {}
    if set(changes).intersection(PROTECTED_FIELDS):
        raise ValidationError('Version metadata is assigned automatically.')
    _unchanged_access_fields(actor, current, changes)
    _check_relations(actor, current, changes)
    fields = {}
    for field in current._meta.concrete_fields:
        if field.name in {'id', 'created_at', 'updated_at', 'revision', 'status', 'version', 'previous', 'created_by', 'snapshot', 'manifest', 'omissions', 'file', 'checksum'}:
            continue
        fields[field.attname] = getattr(current, field.attname)
    fields.update(changes)
    next_version = (type(current).objects.filter(series=current.series).aggregate(v=Max('version'))['v'] or 0) + 1
    revised = type(current)(**fields, previous=current, version=next_version, created_by=actor, status='draft')
    revised.full_clean()
    revised.save()
    for field in current._meta.many_to_many:
        getattr(revised, field.name).set(getattr(current, field.name).all())
    log_event(actor, 'version.revised', revised, f'Previous version: {current.identifier} v{current.version}; original retained.')
    if isinstance(revised, m.ScopeVersion):
        m.Task.objects.create(title=f'Review impact of scope version {next_version}', description='Review assets, risks, SoA, documents and audit coverage against the changed boundaries.', owner=revised.owner, created_by=actor, scope=revised, stage=1, priority='high', status='open', required_output='Recorded impact review of assets, risks, SoA, documents and audit coverage.')
    return revised


@transaction.atomic
def share_record(actor, record, users, expires_at=None, reason='', expected_revision=None):
    """Change access metadata without rewriting the content of an approved version."""
    current = _locked(record, expected_revision)
    require_view(actor, current)
    if not has_role(actor, 'Manager'):
        raise PermissionDenied('Only an ISMS manager can change record sharing.')
    users = list(users)
    if not reason.strip():
        raise ValidationError('Explain the access grant or revocation.')
    if any(has_role(user, 'External auditor') for user in users):
        if not isinstance(current, (m.EvidenceVersion, m.AuditPack)):
            raise ValidationError('External auditors may be shared only evidence or frozen audit packages.')
        if not expires_at or expires_at <= timezone.now():
            raise ValidationError('External auditor sharing requires a future access expiry.')
    current.access_expires = expires_at
    current._allow_transition = True
    current.full_clean()
    current.save()
    current.allowed_users.set(users)
    log_event(actor, 'record.access_changed', current, reason)
    return _refresh(record, current)


def _accepted_evidence(queryset, actor=None):
    today = timezone.localdate()
    if actor is not None:
        queryset = visible_queryset(actor, queryset)
    return queryset.filter(status='accepted').filter(m.models.Q(expires_on__isnull=True) | m.models.Q(expires_on__gte=today))


def soa_snapshot(actor, scope, framework):
    rows, omissions = [], []
    implementations = {row.control_id: row for row in visible_queryset(actor, m.ControlImplementation).filter(scope=scope, control__framework=framework).select_related('control', 'owner')}
    for control in framework.controls.all():
        row = implementations.get(control.pk)
        missing = []
        if row is None:
            missing.append('No applicability decision')
        else:
            if row.applicability == 'undecided':
                missing.append('Applicability undecided')
            if not row.justification.strip():
                missing.append('Missing inclusion/exclusion justification')
            if row.applicability == 'applicable' and not row.owner_id:
                missing.append('Applicable control has no owner')
        rows.append({'control_id': control.pk, 'identifier': control.identifier, 'title': control.title, 'summary': control.summary,
                     'applicability': row.applicability if row else 'undecided', 'justification': row.justification if row else '',
                     'implementation_status': row.implementation_status if row else 'not_assessed', 'effectiveness': row.effectiveness if row else 'not_tested',
                     'owner': row.owner.get_full_name() or row.owner.username if row and row.owner else '',
                     'record_id': row.pk if row else None, 'revision': row.revision if row else None,
                     'risks': list(row.risks.values_list('pk', flat=True)) if row else [], 'evidence': list(row.evidence.values_list('pk', flat=True)) if row else [],
                     'documents': list(row.documents.values_list('pk', flat=True)) if row else [], 'omissions': missing})
        omissions.extend(f'{control.identifier}: {message}' for message in missing)
    return rows, omissions


def management_snapshot(actor, scope):
    result = {'generated_at': timezone.now().isoformat(), 'scope_id': scope.pk if scope else None}
    for label, model in [('risks', m.RiskAssessmentVersion), ('controls', m.ControlImplementation), ('tasks', m.Task), ('audits', m.Audit), ('objectives', m.MetricResult)]:
        qs = visible_queryset(actor, model)
        if scope:
            qs = qs.filter(scope=scope)
        result[label] = [record_snapshot(row) for row in qs]
    findings = visible_queryset(actor, m.Finding)
    if scope:
        findings = findings.filter(audit__scope=scope)
    result['findings'] = [record_snapshot(row) for row in findings]
    return result


def _approval_checks(actor, record):
    errors = []
    if record.status != 'in_review':
        errors.append('Submit the record for review before approval.')
    if not record.owner_id:
        errors.append('Assign an owner before approval.')
    if isinstance(record, m.ScopeVersion):
        if not record.statement.strip() or not record.boundaries.strip():
            errors.append('Scope statement and boundaries are required.')
        if record.climate_relevance == 'undecided' or not record.climate_rationale.strip():
            errors.append('Record the climate relevance decision and rationale.')
    elif isinstance(record, m.RiskMethodologyVersion):
        if any(str(n) not in record.likelihood_criteria or str(n) not in record.impact_criteria for n in range(1, 6)):
            errors.append('Define likelihood and impact criteria for all five levels.')
    elif isinstance(record, m.RiskAssessmentVersion):
        if record.methodology.status != 'approved':
            errors.append('Approve the referenced risk methodology first.')
        if not record.scenario.strip() or not record.scoring_rationale.strip():
            errors.append('A risk scenario and scoring rationale are required.')
    elif isinstance(record, m.TreatmentPlan):
        if record.risk.status != 'approved':
            errors.append('Approve the risk assessment before its treatment.')
        if not record.risk.owner_id or not record.rationale.strip() or not record.actions.strip():
            errors.append('Treatment requires a risk owner, rationale and actions.')
        if record.decision == 'modify' and not record.controls.exists():
            errors.append('Select the controls used to modify this risk.')
    elif isinstance(record, m.RiskAcceptance):
        if record.risk.status != 'approved':
            errors.append('Approve the risk assessment before accepting residual risk.')
        if record.treatment and record.treatment.status != 'approved':
            errors.append('Approve the treatment plan before residual-risk acceptance.')
        if record.treatment and record.treatment.risk_id != record.risk_id:
            errors.append('The acceptance and treatment must refer to the same risk assessment version.')
        if record.expires_on <= timezone.localdate():
            errors.append('Risk acceptance must have a future expiry date.')
        if record.accepted_score != record.risk.current_score:
            errors.append('Acceptance must explicitly match the recorded current risk score; linking controls does not reduce it.')
        if not record.rationale.strip():
            errors.append('Risk acceptance requires a justification.')
    elif isinstance(record, m.DocumentVersion):
        if not record.body.strip():
            errors.append('A document cannot be approved with empty content.')
    elif isinstance(record, m.SoAVersion):
        record.snapshot, record.omissions = soa_snapshot(actor, record.scope, record.framework)
        if record.omissions:
            errors.append(f'The SoA has {len(record.omissions)} omissions. Resolve applicability, justification and ownership before approval.')
    elif isinstance(record, m.GapAssessment):
        if record.implementation_status == 'implemented' and not _accepted_evidence(record.evidence, actor).exists():
            errors.append('An implemented assessment requires accepted, current supporting evidence.')
        if record.effectiveness_verified and (not record.rationale.strip() or not _accepted_evidence(record.evidence, actor).exists()):
            errors.append('Effectiveness verification needs a rationale and accepted, current evidence.')
    elif isinstance(record, m.ManagementReview):
        if not record.attendees.strip() or not record.minutes.strip() or not record.decisions.strip():
            errors.append('Record attendees, minutes and decisions before approval.')
        record.snapshot = management_snapshot(actor, record.scope)
    elif isinstance(record, m.CertificationRecord):
        if record.decision == 'granted':
            if not all([record.issuer, record.certificate_number, record.certified_scope, record.issued_on, record.expires_on, record.supporting_evidence_id]):
                errors.append('A granted decision requires issuer, certificate number, certified scope, dates and supporting evidence.')
            elif not can_view(actor, record.supporting_evidence) or record.supporting_evidence.status != 'accepted':
                errors.append('Supporting certification evidence must be visible and accepted.')
    if errors:
        raise ValidationError(errors)


@transaction.atomic
def approve_record(actor, record, reason='', expected_revision=None):
    current = _locked(record, expected_revision)
    if not can_approve(actor, current):
        raise PermissionDenied('You do not hold the business approval authority for this record.')
    _approval_checks(actor, current)
    current.status = 'approved'
    current.full_clean()
    current._allow_transition = True
    current.save()
    m.Approval.objects.create(content_type=ContentType.objects.get_for_model(current), object_id=current.pk, actor=actor, reason=reason, snapshot=record_snapshot(current))
    log_event(actor, 'record.approved', current, reason)
    return _refresh(record, current)


@transaction.atomic
def transition_record(actor, record, action, reason='', expected_revision=None):
    if action == 'approve':
        return approve_record(actor, record, reason, expected_revision)
    current = _locked(record, expected_revision)
    require_view(actor, current)
    if action == 'publish':
        if not isinstance(current, (m.DocumentVersion, m.SoAVersion)) or current.status != 'approved':
            raise ValidationError('Only an approved document or SoA can be published.')
        if not can_approve(actor, current):
            raise PermissionDenied('Publication requires the assigned approval authority.')
        current.status = 'published'
    elif action in {'review_evidence', 'accept_evidence', 'reject_evidence'}:
        if not isinstance(current, m.EvidenceVersion) or not can_approve(actor, current):
            raise PermissionDenied('Evidence review requires an authorized reviewer.')
        if not reason.strip():
            raise ValidationError('Explain the evidence review, relevance and sufficiency for its intended purpose.')
        if current.status in current.FROZEN_STATUSES:
            raise ValidationError('Accepted evidence is frozen. Upload a new version for replacement.')
        if action == 'accept_evidence' and current.is_expired:
            raise ValidationError('Expired evidence cannot be accepted for the current period.')
        if action == 'accept_evidence' and current.status != 'reviewed':
            raise ValidationError('Review the evidence before accepting it for a purpose.')
        current.status = {'review_evidence': 'reviewed', 'accept_evidence': 'accepted', 'reject_evidence': 'rejected'}[action]
        current.reviewer = actor
        current.review_notes = reason
    elif action == 'approve_plan' and isinstance(current, m.CorrectiveAction):
        if not has_role(actor, 'Approver'):
            raise PermissionDenied('Corrective action plan approval requires explicit business approval authority.')
        if current.status in {'complete', 'closed'}:
            raise ValidationError('Reopen the corrective action before approving a changed plan.')
        if not current.root_cause.strip() or not current.plan.strip() or not reason.strip():
            raise ValidationError('A root cause, action plan and approval rationale are required.')
        m.Approval.objects.create(content_type=ContentType.objects.get_for_model(current), object_id=current.pk,
                                  actor=actor, decision='plan_approved', reason=reason, snapshot=record_snapshot(current))
        current.status = 'approved'
    elif action == 'close' and isinstance(current, m.CorrectiveAction):
        if not has_role(actor, 'Internal auditor'):
            raise PermissionDenied('Corrective action closure requires an internal auditor.')
        if actor.pk in {current.owner_id, current.finding.owner_id}:
            raise ValidationError('An independent verifier is required; the action or finding owner cannot verify their own work.')
        if current.status == 'closed':
            raise ValidationError('This corrective action is already closed.')
        approval = m.Approval.objects.filter(content_type=ContentType.objects.get_for_model(current), object_id=current.pk, decision='plan_approved').first()
        if not approval or any(approval.snapshot.get(field) != getattr(current, field) for field in ('root_cause', 'plan')):
            raise ValidationError('The current root cause and action plan require authorized approval before closure.')
        if not all([current.root_cause.strip(), current.plan.strip(), current.implementation_notes.strip(), current.effectiveness_notes.strip(), reason.strip()]):
            raise ValidationError('Root cause, action plan, implementation, effectiveness check and closure rationale are required.')
        if not _accepted_evidence(current.evidence, actor).exists():
            raise ValidationError('Closure requires accepted, current evidence of implementation and effectiveness.')
        current.status = 'closed'
        current.verified_by = actor
        current.verified_on = timezone.localdate()
        current.closure_rationale = reason
    elif action == 'close' and isinstance(current, m.Finding):
        if not has_role(actor, 'Internal auditor') or actor.pk == current.owner_id:
            raise PermissionDenied('Finding closure requires an independent internal auditor.')
        if not current.corrective_actions.exists() or current.corrective_actions.exclude(status='closed').exists():
            raise ValidationError('Close all verified corrective actions before closing the finding.')
        if not reason.strip():
            raise ValidationError('A closure rationale is required.')
        if not (current.requirement_id or current.control_id) or not current.objective_evidence.strip():
            raise ValidationError('Identify the applicable requirement or control and objective evidence before closure.')
        current.status = 'closed'
    elif action == 'reopen':
        if not isinstance(current, (m.Task, m.Finding, m.CorrectiveAction, m.Audit)) or current.status not in {'closed', 'complete'}:
            raise ValidationError('Only a completed task/audit or closed finding/action can be reopened.')
        if not (has_role(actor, 'Manager') or (current.owner_id == actor.pk and can_create(actor, type(current))) or (isinstance(current, (m.Finding, m.CorrectiveAction)) and has_role(actor, 'Internal auditor'))):
            raise PermissionDenied('Reopening requires the assigned owner, manager, or authorized auditor.')
        if not reason.strip():
            raise ValidationError('Explain why this record is being reopened.')
        current.status = 'open'
        if isinstance(current, m.CorrectiveAction):
            current.verified_by = None
            current.verified_on = None
    else:
        require_edit(actor, current)
        if action == 'submit':
            if current.status not in {'draft', 'rejected', 'open'}:
                raise ValidationError('Only a draft record may be submitted for review.')
            if not isinstance(current, m.VersionedRecord) or isinstance(current, (m.EvidenceVersion, m.AuditPack)):
                raise ValidationError('This type of record does not use the approval workflow.')
            current.status = 'in_review'
        elif action == 'start':
            valid_statuses = {'draft', 'open', 'scheduled'} | ({'approved'} if isinstance(current, m.CorrectiveAction) else set())
            if not isinstance(current, (m.Task, m.Audit, m.CorrectiveAction)) or current.status not in valid_statuses:
                raise ValidationError('This record cannot be started from its current state.')
            current.status = 'in_progress'
        elif action == 'complete':
            if current.status in {'complete', 'closed'}:
                raise ValidationError('This record has already been completed.')
            if isinstance(current, m.Task):
                if current.blockers.exists():
                    raise ValidationError('Complete blocking dependencies before completing this task.')
                if current.requires_evidence and not _accepted_evidence(current.evidence, actor).exists():
                    raise ValidationError('This task requires accepted, current evidence.')
                if not reason.strip():
                    raise ValidationError('Explain the completed output.')
                current.completion_notes = reason
            elif isinstance(current, m.Audit):
                if not current.report.strip() or not current.independence_notes.strip():
                    raise ValidationError('Audit completion requires a report and an independence/conflict assessment.')
                if current.audit_type == 'internal' and (not current.auditor_id or current.auditor_id == current.owner_id):
                    raise ValidationError('An internal audit requires a named auditor distinct from its owner; document any remaining conflicts in the independence assessment.')
                current.completed_date = timezone.localdate()
            else:
                raise ValidationError('Use the specific review or closure workflow for this record.')
            current.status = 'complete'
        else:
            raise ValidationError('Unknown workflow action.')
    current._allow_transition = True
    current.full_clean()
    current.save()
    log_event(actor, f'record.{action}', current, reason)
    return _refresh(record, current)


def _validate_file(uploaded_file):
    if not uploaded_file:
        return None
    filename = Path(uploaded_file.name.replace('\\', '/')).name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_UPLOADS:
        raise ValidationError('Allowed files: PDF, text, CSV, images, XLSX, DOCX, JSON and log files. Executable, HTML and script uploads are blocked.')
    if uploaded_file.size > settings.NAVA_MAX_UPLOAD_BYTES:
        raise ValidationError('Evidence files must be 10 MB or smaller.')
    digest = hashlib.sha256()
    actual_size = 0
    for chunk in uploaded_file.chunks():
        actual_size += len(chunk)
        if actual_size > settings.NAVA_MAX_UPLOAD_BYTES:
            raise ValidationError('Evidence files must be 10 MB or smaller.')
        digest.update(chunk)
    uploaded_file.seek(0)
    return filename, digest.hexdigest(), actual_size


@transaction.atomic
def upload_evidence(actor, uploaded_file=None, previous=None, **fields):
    if not can_create(actor, m.EvidenceVersion):
        raise PermissionDenied('Your role cannot upload evidence.')
    if set(fields).intersection(PROTECTED_FIELDS):
        raise ValidationError('Evidence metadata is recorded automatically.')
    details = _validate_file(uploaded_file)
    if not uploaded_file and not fields.get('external_url') and not fields.get('description'):
        raise ValidationError('Supply a file, external reference or structured evidence description.')
    if not has_role(actor, 'Manager'):
        if fields.get('owner') not in (None, actor):
            raise PermissionDenied('Contributors may upload only their own evidence.')
        if fields.get('allowed_users') or fields.get('access_expires'):
            raise PermissionDenied('Only an ISMS manager can share evidence.')
        fields['owner'] = actor
    relations = {}
    for name in list(fields):
        if m.EvidenceVersion._meta.get_field(name).many_to_many:
            relations[name] = fields.pop(name)
    version_fields = {}
    if previous:
        previous = _locked(previous)
        require_view(actor, previous)
        if not has_role(actor, 'Manager') and previous.owner_id != actor.pk:
            raise PermissionDenied('Only the evidence owner or ISMS manager can upload a replacement.')
        version = (m.EvidenceVersion.objects.filter(series=previous.series).aggregate(v=Max('version'))['v'] or 0) + 1
        version_fields = {'previous': previous, 'series': previous.series, 'version': version}
        # Carry access restrictions forward unless the manager deliberately changes them.
        fields.setdefault('classification', previous.classification)
        fields.setdefault('owner', previous.owner)
        fields.setdefault('scope', previous.scope)
        fields.setdefault('access_expires', previous.access_expires)
        if not has_role(actor, 'Manager') and fields.get('classification') != previous.classification:
            raise PermissionDenied('Only an ISMS manager may change an evidence version’s classification.')
        if 'allowed_users' not in relations:
            relations['allowed_users'] = previous.allowed_users.all()
    record = m.EvidenceVersion(created_by=actor, status='uploaded', **version_fields, **fields)
    _check_relations(actor, record, {**fields, **relations})
    if details:
        record.original_filename, record.checksum, record.size_bytes = details
        record.content_type = getattr(uploaded_file, 'content_type', '') or 'application/octet-stream'
    record.full_clean()
    try:
        if uploaded_file:
            record.file.save(details[0], uploaded_file, save=False)
        record.save()
        for name, values in relations.items():
            getattr(record, name).set(values)
        log_event(actor, 'evidence.uploaded', record, 'SHA-256 records byte integrity; malware scanning is not configured.')
    except Exception:
        if record.file and record.file.name:
            record.file.delete(save=False)
        raise
    return record


@transaction.atomic
def generate_recurring_tasks(actor, today=None):
    if not has_role(actor, 'Manager'):
        raise PermissionDenied('Only an ISMS manager can generate recurring work.')
    today = today or timezone.localdate()
    generated = []
    for source in visible_queryset(actor, m.Task).filter(recurrence_days__gt=0, due_date__isnull=False, recurrence_source__isnull=True):
        next_due = source.due_date + timedelta(days=source.recurrence_days)
        while next_due <= today:
            key = f'{source.pk}:{next_due.isoformat()}'
            task, created = m.Task.objects.get_or_create(recurrence_key=key, defaults={'title': source.title, 'description': source.description, 'owner': source.owner, 'created_by': actor, 'scope': source.scope, 'stage': source.stage, 'priority': source.priority, 'status': 'open', 'due_date': next_due, 'recurrence_source': source, 'required_output': source.required_output, 'requires_evidence': source.requires_evidence, 'classification': source.classification, 'access_expires': source.access_expires})
            if created:
                task.allowed_users.set(source.allowed_users.all())
                generated.append(task)
                log_event(actor, 'task.recurring_created', task, f'Source {source.identifier}')
            next_due += timedelta(days=source.recurrence_days)
    return generated
