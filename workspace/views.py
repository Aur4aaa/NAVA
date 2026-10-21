import hashlib
import json
import logging
import uuid
from datetime import date
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.contrib.auth.views import LoginView
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.forms.models import model_to_dict
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import models as m
from .dashboard import dashboard_context, owner_name, selected_scope, stage_context
from .forms import AccountForm, OrganizationForm, ShareForm, record_form_class
from .permissions import can_approve, can_create, can_edit, can_view, has_role, visible_queryset
from .registry import MODULES, label_status, record_url
from .services import create_record, filtered_snapshot, log_event, revise_record, soa_snapshot, transition_record, update_record, upload_evidence


class WorkspaceLoginView(LoginView):
    template_name = 'registration/login.html'
    redirect_authenticated_user = True

    def _key(self):
        # A local deployment has one trusted loopback address. Do not trust forwarded headers.
        return 'login:' + hashlib.sha256(self.request.META.get('REMOTE_ADDR', '').encode()).hexdigest()

    def post(self, request, *args, **kwargs):
        if cache.get(self._key(), 0) >= 10:
            return render(request, self.template_name, {'form': self.get_form(), 'rate_limited': True}, status=429)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        cache.set(self._key(), cache.get(self._key(), 0) + 1, timeout=300)
        log_event(None, 'auth.login_failed', detail='Invalid sign-in; no credentials recorded.')
        return super().form_invalid(form)

    def form_valid(self, form):
        response = super().form_valid(form)
        cache.delete(self._key())
        log_event(form.get_user(), 'auth.login')
        return response


def health(request):
    return JsonResponse({'status': 'ok'})


@login_required
def dashboard(request):
    return render(request, 'workspace/dashboard.html', dashboard_context(request.user, request.GET.get('scope')))


def get_module(kind):
    if kind not in MODULES:
        raise Http404('Unknown register.')
    return MODULES[kind]


def get_record(user, kind, pk):
    return get_object_or_404(visible_queryset(user, get_module(kind).model), pk=pk)


def filtered_queryset(user, kind, params):
    model = get_module(kind).model
    qs = visible_queryset(user, model).select_related('owner')
    if params.get('latest') == '1' and issubclass(model, m.VersionedRecord):
        qs = qs.filter(revisions__isnull=True)
    q = params.get('q', '').strip()[:200]
    if q:
        query = Q(title__icontains=q) | Q(description__icontains=q) | Q(owner__first_name__icontains=q) | Q(owner__last_name__icontains=q)
        suffix = q.rsplit('-', 1)[-1]
        if suffix.isdigit():
            query |= Q(pk=int(suffix))
        qs = qs.filter(query)
    if params.get('status'):
        qs = qs.filter(status=params['status'])
    field_names = {f.name for f in model._meta.fields}
    for key in ('scope', 'stage', 'implementation_status', 'applicability'):
        if params.get(key) and key in field_names:
            value = params[key]
            if key not in ('scope', 'stage') or value.isdigit():
                qs = qs.filter(**{key: value})
    today = timezone.localdate()
    if params.get('overdue') == '1':
        field = 'due_date' if 'due_date' in field_names else 'review_date' if 'review_date' in field_names else None
        if field:
            qs = qs.filter(**{field + '__lt': today}).exclude(status__in=['complete', 'closed'])
    if params.get('expired') == '1' and 'expires_on' in field_names:
        qs = qs.filter(expires_on__lt=today)
    if kind == 'risks':
        if params.get('likelihood', '').isdigit():
            qs = qs.filter(current_likelihood=params['likelihood'])
        if params.get('impact', '').isdigit():
            qs = qs.filter(current_impact=params['impact'])
        if params.get('level') == 'high':
            qs = qs.filter(pk__in=[r.pk for r in qs if r.current_score >= 12])
    if kind == 'controls':
        if params.get('theme'):
            qs = qs.filter(control__theme=params['theme'])
        accepted = visible_queryset(user, m.EvidenceVersion).filter(status='accepted').filter(Q(expires_on__isnull=True) | Q(expires_on__gte=today))
        covered = qs.filter(evidence__in=accepted).values_list('pk', flat=True)
        if params.get('coverage') == 'current':
            qs = qs.filter(pk__in=covered)
        elif params.get('coverage') == 'missing':
            qs = qs.filter(applicability='applicable').exclude(pk__in=covered)
    return qs.distinct()


RELATED_MODULES = {
    'scopes': ['scopes', 'parties', 'requirements', 'gaps'],
    'risks': ['risks', 'methodologies', 'treatments', 'acceptances'],
    'controls': ['controls', 'soa', 'gaps'],
    'audits': ['audits', 'findings', 'actions', 'certifications'],
    'documents': ['documents', 'evidence'],
}


def module_links(kind):
    group = next((kinds for kinds in RELATED_MODULES.values() if kind in kinds), [])
    return [{'label': MODULES[k].title, 'url': f'/records/{k}/', 'active': k == kind} for k in group]


def table_columns(kind):
    return {'risks': ['Current risk', 'Review date'], 'controls': ['Applicability', 'Implementation'], 'evidence': ['Version', 'Review / expiry'], 'tasks': ['Priority', 'Due date'], 'audits': ['Audit type', 'Scheduled'], 'documents': ['Version', 'Review date']}.get(kind, ['Version / type', 'Updated'])


def table_row(record, kind):
    def fmt(value):
        return value.strftime('%d %b %Y') if isinstance(value, date) else value or '—'
    if kind == 'risks':
        cells = [f'{record.current_score} / 25 · {record.level.title()}', fmt(record.review_date)]
    elif kind == 'controls':
        cells = [record.get_applicability_display(), record.get_implementation_status_display()]
    elif kind == 'evidence':
        cells = [f'v{record.version}', ('Expired · ' if record.is_expired else '') + fmt(record.expires_on)]
    elif kind == 'tasks':
        cells = [record.get_priority_display(), fmt(record.due_date)]
    elif kind == 'audits':
        cells = [record.get_audit_type_display(), fmt(record.scheduled_date)]
    elif kind == 'documents':
        cells = [f'v{record.version}', fmt(record.review_date)]
    else:
        cells = [f'v{record.version}' if hasattr(record, 'version') else record._meta.verbose_name.title(), fmt(record.updated_at)]
    return {'id': record.identifier, 'title': record.title, 'subtitle': record.control.identifier if kind == 'controls' else '', 'status': record.status, 'status_label': label_status(record.status), 'owner': owner_name(record.owner), 'url': record_url(record), 'cells': cells}


@login_required
def record_list(request, kind):
    module = get_module(kind)
    qs = filtered_queryset(request.user, kind, request.GET)
    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page'))
    guidance = ''
    if kind in ('controls', 'soa', 'gaps'):
        framework = m.FrameworkVersion.objects.order_by('-pk').first()
        if framework and framework.verification_status != 'verified':
            guidance = 'Reference catalog verification is pending. These original summaries are planning aids; consult your licensed standard. Clauses 4–10 are management-system requirements, not optional controls.'
    if kind == 'evidence':
        guidance = 'Uploads are stored privately and downloaded as attachments. Malware scanning is not configured. A checksum verifies bytes, not truth or authenticity.'
    return render(request, 'workspace/record_list.html', {'kind': kind, 'page_title': module.title, 'page_description': module.description, 'rows': [table_row(r, kind) for r in page], 'columns': table_columns(kind), 'page_obj': page, 'create_url': f'/records/{kind}/new/' if can_create(request.user, module.model) else None, 'create_label': f'Add {module.singular}', 'export_url': f'/records/{kind}/export/csv/?{request.GET.urlencode()}', 'export_links': [{'label': label, 'url': f'/records/{kind}/export/{extension}/?{request.GET.urlencode()}'} for extension, label in [('xlsx', 'XLSX'), ('pdf', 'PDF')]], 'filters': [{'value': value, 'label': label} for value, label in m.STATUS], 'selected_status': request.GET.get('status', ''), 'q': request.GET.get('q', ''), 'module_links': module_links(kind), 'guidance': guidance})


def _readable_fields(actor, record):
    fields = []
    hidden = {'id', 'title', 'description', 'body', 'status', 'revision', 'series', 'created_by', 'created_at', 'updated_at', 'file', 'manifest', 'snapshot', 'omissions'}
    for field in record._meta.concrete_fields:
        if field.name in hidden:
            continue
        value = getattr(record, field.name)
        link = ''
        if isinstance(value, m.Record):
            if can_view(actor, value):
                link = record_url(value)
                value = f'{value.identifier} · {value.title}'
            else:
                value = 'Restricted record'
        elif field.choices:
            value = getattr(record, f'get_{field.name}_display')()
        elif isinstance(value, dict):
            value = '\n'.join(f'{k}: {v}' for k, v in value.items())
        elif isinstance(value, bool):
            value = 'Yes' if value else 'No'
        fields.append({'label': field.verbose_name.capitalize(), 'value': value if value not in (None, '') else 'Not recorded', 'url': link, 'long': field.get_internal_type() in ('TextField', 'JSONField')})
    return fields


def _relation_context(actor, record):
    result = []
    for field in record._meta.many_to_many:
        if field.name == 'allowed_users':
            continue
        related = getattr(record, field.name).all()
        if issubclass(field.related_model, m.Record):
            related = visible_queryset(actor, related)
            items = [{'title': f'{r.identifier} · {r.title}', 'url': record_url(r), 'status': r.status} for r in related[:15]]
        else:
            items = []
        if items:
            result.append({'title': field.verbose_name.capitalize(), 'items': items})
    for relation in record._meta.related_objects:
        if not issubclass(relation.related_model, m.Record):
            continue
        try:
            qs = visible_queryset(actor, getattr(record, relation.get_accessor_name()).all())
        except AttributeError:
            continue
        items = [{'title': f'{r.identifier} · {r.title}', 'url': record_url(r), 'status': r.status} for r in qs[:10]]
        if items:
            result.append({'title': relation.get_accessor_name().replace('_', ' ').capitalize(), 'items': items})
    return result


def _actions(user, kind, record):
    actions = []
    def add(action, label, reason=False, method='post', url=None):
        actions.append({'action': action, 'label': label, 'url': url or f'/records/{kind}/{record.pk}/action/{action}/', 'reason_required': reason, 'method': method, 'style': 'button-primary' if not actions else 'button-secondary'})
    mutable = can_edit(user, record)
    if isinstance(record, m.EvidenceVersion):
        if can_approve(user, record):
            if record.status in ['uploaded', 'rejected']:
                add('review_evidence', 'Review evidence', True)
            elif record.status == 'reviewed':
                add('accept_evidence', 'Accept for purpose', True)
                add('reject_evidence', 'Reject', True)
        if can_create(user, m.EvidenceVersion) and (has_role(user, 'Manager') or record.owner_id == user.pk):
            add('new_version', 'Upload new version', method='get', url=f'/records/evidence/new/?previous={record.pk}')
    elif isinstance(record, m.AuditPack):
        if mutable and has_role(user, 'Manager'):
            add('freeze', 'Generate frozen package', True)
    elif isinstance(record, m.VersionedRecord):
        if mutable and record.status in ['draft', 'open', 'rejected']:
            add('submit', 'Submit for approval')
        if record.status == 'in_review' and can_approve(user, record):
            add('approve', 'Approve version', True)
        if isinstance(record, (m.DocumentVersion, m.SoAVersion)) and record.status == 'approved' and can_approve(user, record):
            add('publish', 'Publish version', True)
        if record.status in record.FROZEN_STATUSES and can_create(user, type(record)) and (has_role(user, 'Manager') or record.owner_id == user.pk):
            add('revise', 'Create revision')
    if isinstance(record, (m.Task, m.Audit)) and mutable:
        if record.status in ['draft', 'open', 'scheduled']:
            add('start', 'Start work')
        if record.status not in ['complete', 'closed']:
            add('complete', 'Mark complete', True)
    if isinstance(record, (m.Finding, m.CorrectiveAction)) and has_role(user, 'Internal auditor'):
        if record.status != 'closed':
            add('close', 'Verify & close', True)
        else:
            add('reopen', 'Reopen', True)
    if isinstance(record, m.CorrectiveAction) and record.status != 'closed' and has_role(user, 'Approver'):
        add('approve_plan', 'Approve corrective plan', True)
    return actions


@login_required
def record_detail(request, kind, pk):
    record = get_record(request.user, kind, pk)
    content_type = ContentType.objects.get_for_model(record)
    events = m.ActivityEvent.objects.filter(content_type=content_type, object_id=record.pk).select_related('actor')[:30]
    history = [{'description': event.action.replace('.', ' ').replace('_', ' '), 'actor': owner_name(event.actor), 'time': event.created_at} for event in events]
    snapshot = getattr(record, 'snapshot', None)
    guidance = ''
    if isinstance(record, m.SoAVersion) and not snapshot:
        snapshot, omissions = soa_snapshot(request.user, record.scope, record.framework)
        guidance = f'Current draft preview: {len(omissions)} omissions. Approval freezes all applicability decisions. ' + '; '.join(omissions[:3])
    elif isinstance(record, m.EvidenceVersion):
        guidance = 'File bytes are immutable. Replacing evidence creates a new version. Malware scanning is not configured.'
        if record.is_expired:
            guidance = 'This evidence has expired and does not count toward current coverage. ' + guidance
    elif isinstance(record, m.Task) and record.blockers.exists():
        visible_blockers = visible_queryset(request.user, record.blockers)
        guidance = 'Blocked by: ' + ', '.join(visible_blockers.values_list('title', flat=True)) + '. Complete dependencies before this action.'
    download = f'/evidence/{pk}/download/' if isinstance(record, m.EvidenceVersion) and record.file else f'/packs/{pk}/download/' if isinstance(record, m.AuditPack) and record.file else None
    if snapshot:
        snapshot = filtered_snapshot(request.user, snapshot)
    share_form = ShareForm(initial={'users': record.allowed_users.all(), 'expires_at': record.access_expires, 'revision': record.revision}) if has_role(request.user, 'Manager') else None
    return render(request, 'workspace/record_detail.html', {'record': record, 'title': record.title, 'kind': kind, 'fields': _readable_fields(request.user, record), 'relations': _relation_context(request.user, record), 'action_buttons': _actions(request.user, kind, record), 'history': history, 'back_url': f'/records/{kind}/', 'edit_url': f'/records/{kind}/{pk}/edit/' if can_edit(request.user, record) else None, 'download_url': download, 'body': getattr(record, 'body', ''), 'snapshot': json.dumps(snapshot, indent=2, ensure_ascii=False) if snapshot else '', 'guidance': guidance, 'share_form': share_form, 'share_url': f'/records/{kind}/{pk}/share/'})


@login_required
@require_POST
def record_share(request, kind, pk):
    from .services import share_record
    record = get_record(request.user, kind, pk)
    if not has_role(request.user, 'Manager'):
        raise PermissionDenied('Sharing requires an ISMS manager.')
    form = ShareForm(request.POST)
    if form.is_valid():
        try:
            data = form.cleaned_data
            share_record(request.user, record, data['users'], expires_at=data['expires_at'], reason=data['reason'], expected_revision=data['revision'])
            messages.success(request, 'Access assignments updated. Content and approved snapshots are unchanged.')
        except ValidationError as exc:
            messages.error(request, ' '.join(exc.messages))
    else:
        messages.error(request, ' '.join(error for errors in form.errors.values() for error in errors))
    return redirect(record_url(record))


def _form_errors(form, exc):
    # Service errors may mention fields intentionally hidden from the form.
    if hasattr(exc, 'message_dict'):
        for field, errors in exc.message_dict.items():
            for error in errors:
                form.add_error(field if field in form.fields else None, error)
    else:
        for error in exc.messages:
            form.add_error(None, error)


@login_required
def record_create(request, kind):
    module = get_module(kind)
    if not can_create(request.user, module.model):
        raise PermissionDenied('Your role cannot create this record.')
    previous = None
    initial = {'owner': request.user}
    if kind == 'evidence' and request.GET.get('previous'):
        previous = get_record(request.user, kind, request.GET['previous'])
        if not has_role(request.user, 'Manager') and previous.owner_id != request.user.pk:
            raise PermissionDenied('Only the owner or manager can replace evidence.')
        initial.update(model_to_dict(previous, exclude=['id', 'status', 'file', 'checksum', 'size_bytes', 'revision', 'series', 'version', 'previous', 'created_by']))
    form_class = record_form_class(module.model, request.user)
    form = form_class(request.POST or None, request.FILES or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        data = {name: value for name, value in form.cleaned_data.items() if name != 'expected_revision'}
        try:
            if module.model is m.EvidenceVersion:
                record = upload_evidence(request.user, uploaded_file=data.pop('file', None), previous=previous, **data)
            else:
                record = create_record(request.user, module.model, **data)
            messages.success(request, f'{record.identifier} created. Your record is saved.')
            return redirect(record_url(record))
        except ValidationError as exc:
            _form_errors(form, exc)
        except IntegrityError:
            form.add_error(None, 'This record conflicts with an existing version or control. Reload and check for duplicates.')
    return render(request, 'workspace/record_form.html', {'form': form, 'title': 'Upload new evidence version' if previous else f'Add {module.singular}', 'description': module.description, 'back_url': f'/records/{kind}/', 'kind': kind})


@login_required
def record_edit(request, kind, pk):
    record = get_record(request.user, kind, pk)
    if not can_edit(request.user, record):
        raise PermissionDenied('This record is frozen or outside your edit authority. Create a revision for approved content.')
    form_class = record_form_class(type(record), request.user, record)
    form = form_class(request.POST or None, request.FILES or None, instance=record)
    if request.method == 'POST' and form.is_valid():
        data = {name: value for name, value in form.cleaned_data.items() if name != 'expected_revision'}
        try:
            update_record(request.user, record, data, expected_revision=form.cleaned_data['expected_revision'])
            messages.success(request, 'Changes saved and recorded in the activity trail.')
            return redirect(record_url(record))
        except ValidationError as exc:
            _form_errors(form, exc)
        except IntegrityError:
            form.add_error(None, 'The record conflicts with another saved version. Reload and try again.')
    return render(request, 'workspace/record_form.html', {'form': form, 'title': f'Edit {record.identifier}', 'description': 'Changes to this working version are recorded. Approval and publication use separate actions.', 'back_url': record_url(record), 'kind': kind})


@login_required
@require_POST
def record_action(request, kind, pk, action):
    record = get_record(request.user, kind, pk)
    try:
        revision = int(request.POST.get('revision', ''))
        if revision != record.revision:
            raise ValidationError('This record changed. Reload before submitting a decision.')
        reason = request.POST.get('reason', '').strip()[:8000]
        if action == 'revise':
            record = revise_record(request.user, record)
            messages.success(request, 'New draft version created. The earlier approved version is preserved.')
            return redirect(f'{record_url(record)}edit/')
        elif action == 'freeze' and isinstance(record, m.AuditPack):
            from .exports import build_audit_pack
            build_audit_pack(request.user, record, expected_revision=revision)
        else:
            transition_record(request.user, record, action, reason=reason, expected_revision=revision)
        messages.success(request, 'The action is complete and recorded in the activity trail.')
    except (ValueError, TypeError):
        messages.error(request, 'A valid record revision is required. Reload this page.')
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
    return redirect(record_url(record))


@login_required
def evidence_download(request, pk):
    record = get_record(request.user, 'evidence', pk)
    if not record.file:
        raise Http404('This evidence contains an external reference rather than a stored file.')
    try:
        handle = record.file.open('rb')
    except FileNotFoundError:
        raise Http404('Evidence file unavailable. Contact your administrator.')
    digest = hashlib.file_digest(handle, 'sha256').hexdigest()
    if digest != record.checksum:
        handle.close()
        log_event(request.user, 'evidence.integrity_failed', record)
        return render(request, 'workspace/error.html', {'code': 409, 'title': 'Evidence integrity check failed', 'message': 'The stored bytes do not match the recorded checksum. Restore the original from a verified backup.'}, status=409)
    handle.seek(0)
    log_event(request.user, 'evidence.downloaded', record)
    response = FileResponse(handle, as_attachment=True, filename=Path(record.original_filename).name, content_type='application/octet-stream')
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required
def export_records(request, kind, format):
    from .exports import export_table
    if format not in {'csv', 'xlsx', 'pdf'}:
        raise Http404('Unknown export format.')
    qs = filtered_queryset(request.user, kind, request.GET)
    return export_table(request.user, kind, qs, format)


@login_required
def pack_download(request, pk):
    from .exports import pack_download_response
    pack = get_record(request.user, 'packs', pk)
    try:
        return pack_download_response(request.user, pack)
    except ValidationError as exc:
        return error_response(request, 409, 'Audit package unavailable', ' '.join(exc.messages))


@login_required
def roadmap(request):
    return render(request, 'workspace/roadmap.html', dashboard_context(request.user, request.GET.get('scope')))


@login_required
def search(request):
    query = request.GET.get('q', '').strip()[:200]
    results = []
    if query:
        for kind, module in MODULES.items():
            for record in filtered_queryset(request.user, kind, {'q': query})[:10]:
                results.append({'title': record.title, 'id': record.identifier, 'identifier': record.identifier, 'kind': module.title, 'url': record_url(record), 'status': label_status(record.status), 'description': record.description[:160]})
    return render(request, 'workspace/search.html', {'results': results, 'q': query})


@login_required
def approvals(request):
    rows = []
    for kind, module in MODULES.items():
        if not issubclass(module.model, m.VersionedRecord):
            continue
        for record in visible_queryset(request.user, module.model).filter(status='in_review'):
            if can_approve(request.user, record):
                row = table_row(record, kind)
                row['cells'] = [module.title]
                rows.append(row)
    return render(request, 'workspace/record_list.html', {'page_title': 'Decisions & approvals', 'page_description': 'Review the governance decisions that are within your assigned approval authority.', 'rows': rows, 'columns': ['Register'], 'guidance': 'System administration access does not automatically grant business approval authority.'})


@login_required
def traceability(request):
    risk = visible_queryset(request.user, m.RiskAssessmentVersion).filter(pk=request.GET.get('risk')) .first() if request.GET.get('risk', '').isdigit() else visible_queryset(request.user, m.RiskAssessmentVersion).filter(requirements__isnull=False).first()
    nodes, edges = [], []
    def node(record, kind, x, y, color):
        if record and can_view(request.user, record):
            nodes.append({'id': record.identifier, 'title': record.title[:34], 'subtitle': record.identifier, 'kind': kind, 'url': record_url(record), 'x': x, 'y': y, 'color': color})
            return len(nodes) - 1
        return None
    def edge(first, second):
        if first is not None and second is not None:
            a, b = nodes[first], nodes[second]
            edges.append({'x1': a['x'], 'y1': a['y'], 'x2': b['x'], 'y2': b['y'], 'mid_x': (a['x'] + b['x']) // 2})
    if risk:
        scope = node(risk.scope, 'Scope', 100, 235, '#8f7bf5')
        requirement = visible_queryset(request.user, risk.requirements.all()).first()
        req_node = node(requirement, 'Obligation', 295, 95, '#7cafff')
        risk_node = node(risk, 'Risk scenario', 295, 305, '#efb66b')
        edge(scope, req_node)
        edge(scope, risk_node)
        edge(req_node, risk_node)
        treatment = visible_queryset(request.user, risk.treatments.all()).first()
        trt_node = node(treatment, 'Treatment plan', 500, 305, '#c6a6ff')
        edge(risk_node, trt_node)
        implementation = visible_queryset(request.user, risk.implementations.all()).first()
        ctl_node = node(implementation, 'Selected control', 700, 235, '#39d7c8')
        edge(trt_node, ctl_node)
        if implementation:
            evidence = visible_queryset(request.user, implementation.evidence.all()).first()
            ev_node = node(evidence, 'Operating evidence', 900, 320, '#39d7c8')
            doc = visible_queryset(request.user, implementation.documents.all()).first()
            doc_node = node(doc, 'Controlled document', 900, 95, '#8f7bf5')
            edge(ctl_node, ev_node)
            edge(ctl_node, doc_node)
    return render(request, 'workspace/traceability.html', {'graph_nodes': nodes, 'graph_edges': edges, 'risk': risk, 'risks': visible_queryset(request.user, m.RiskAssessmentVersion)[:50]})


@login_required
def settings_page(request):
    admin = request.user.is_superuser or has_role(request.user, 'System administrator')
    manager = has_role(request.user, 'Manager')
    org = m.Organization.objects.first()
    org_form = OrganizationForm(request.POST if request.POST.get('action') == 'organization' else None, instance=org)
    account_form = AccountForm(request.POST if request.POST.get('action') == 'account' else None)
    if request.method == 'POST':
        if request.POST.get('action') == 'organization':
            if not (manager or admin):
                raise PermissionDenied('Organization settings require a manager or administrator.')
            if org_form.is_valid():
                org_form.save()
                log_event(request.user, 'organization.updated')
                messages.success(request, 'Organization settings saved.')
                return redirect('/settings/')
        elif request.POST.get('action') == 'account':
            if not admin:
                raise PermissionDenied('Account management requires a system administrator.')
            if account_form.is_valid():
                with transaction.atomic():
                    data = account_form.cleaned_data
                    user = get_user_model().objects.create_user(username=data['username'], password=data['password'], first_name=data['first_name'], last_name=data['last_name'])
                    user.groups.set(data['roles'])
                    log_event(request.user, 'permissions.account_created', detail=f'Account {user.pk}; roles: ' + ', '.join(data['roles'].values_list('name', flat=True)))
                messages.success(request, 'Account created with the selected role assignments.')
                return redirect('/settings/')
        else:
            raise Http404('Unknown settings action.')
    return render(request, 'workspace/settings.html', {'organization_form': org_form, 'account_form': account_form, 'is_admin': admin, 'can_manage_org': manager or admin, 'users': get_user_model().objects.all().prefetch_related('groups') if admin else [], 'frameworks': m.FrameworkVersion.objects.all(), 'timezone_name': org.timezone if org else settings.TIME_ZONE})


def error_response(request, status, title, message):
    return render(request, 'workspace/error.html', {'code': status, 'title': title, 'message': message}, status=status)


def permission_denied(request, exception):
    return error_response(request, 403, 'Access is restricted', str(exception) or 'Your role cannot access this material.')


def not_found(request, exception):
    return error_response(request, 404, 'Record not available', 'The record does not exist or is outside your authorized workspace.')


def server_error(request):
    incident = uuid.uuid4().hex[:12]
    logging.getLogger(__name__).error('Unhandled request error diagnostic_id=%s', incident)
    return error_response(request, 500, 'We could not complete that request', f'Contact your administrator with diagnostic ID {incident}.')
