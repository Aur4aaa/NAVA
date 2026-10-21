"""Read models for dashboards. Every count derives from permission-filtered records."""
from django.db.models import Q
from django.utils import timezone
from . import models as m
from .permissions import visible_queryset, can_view
from .registry import record_url, label_status

COLORS = ['#8f7bf5', '#39d7c8', '#efb66b', '#7cafff']


def initials(user):
    if not user:
        return '—'
    words = (user.get_full_name() or user.username.replace('.', ' ')).split()
    return ''.join(w[0] for w in words[:2]).upper()


def owner_name(user):
    return (user.get_full_name() or user.username) if user else 'Unassigned'


def selected_scope(user, scope_id=None):
    scopes = visible_queryset(user, m.ScopeVersion)
    if scope_id:
        return scopes.filter(pk=scope_id).first()
    return scopes.filter(status__in=['approved', 'published']).order_by('-created_at').first() or scopes.first()


def scoped(user, model, scope):
    qs = visible_queryset(user, model)
    if scope and any(f.name == 'scope' for f in model._meta.fields):
        qs = qs.filter(scope=scope)
    if issubclass(model, m.VersionedRecord):
        qs = qs.filter(revisions__isnull=True)
    return qs


def stage_context(user, scope):
    tasks = scoped(user, m.Task, scope)
    stages = []
    for number, title in m.Task.STAGES:
        group = tasks.filter(stage=number)
        total = group.count()
        done = group.filter(status__in=['complete', 'closed']).count()
        blockers = group.exclude(status__in=['complete', 'closed']).filter(dependencies__isnull=False).distinct().count()
        status = 'complete' if total and total == done else 'in_progress' if group.filter(status='in_progress').exists() or done else 'planned'
        stages.append({'number': number, 'title': title, 'status': status, 'label': 'Complete' if status == 'complete' else 'In progress' if status == 'in_progress' else 'Not started', 'percent': round(done / total * 100) if total else 0, 'total': total, 'completed': done, 'blockers': blockers, 'url': f'/records/tasks/?stage={number}', 'description': f'{done} of {total} project tasks complete. These milestones are internal planning aids.', 'tasks': list(group[:6])})
    return stages


def dashboard_context(user, scope_id=None):
    today = timezone.localdate()
    scope = selected_scope(user, scope_id)
    implementations = scoped(user, m.ControlImplementation, scope)
    applicable = implementations.filter(applicability='applicable')
    total = applicable.count()
    excluded = implementations.filter(applicability='excluded').count()
    implemented = applicable.filter(implementation_status='implemented').count()
    accepted = visible_queryset(user, m.EvidenceVersion).filter(status='accepted').filter(Q(expires_on__gte=today) | Q(expires_on__isnull=True))
    covered = applicable.filter(evidence__in=accepted).distinct().count()
    effective = applicable.filter(effectiveness='effective', evidence__in=accepted, tested_on__isnull=False).distinct().count()
    risks = scoped(user, m.RiskAssessmentVersion, scope)
    task_qs = scoped(user, m.Task, scope)
    open_tasks = task_qs.exclude(status__in=['complete', 'closed'])
    overdue = open_tasks.filter(due_date__lt=today).count()
    high_risks = sum(r.current_score >= 12 for r in risks)
    evidence = scoped(user, m.EvidenceVersion, scope)
    expired = evidence.filter(expires_on__lt=today).count()
    docs = scoped(user, m.DocumentVersion, scope)
    approved_docs = docs.filter(status__in=['approved', 'published']).count()
    completed_tasks = task_qs.filter(status__in=['complete', 'closed']).count()
    num_tasks = task_qs.count()
    readiness = round(100 * completed_tasks / num_tasks) if num_tasks else 0
    themes = []
    for name, label in m.ControlReference._meta.get_field('theme').choices:
        group = applicable.filter(control__theme=name)
        n = group.count()
        done = group.filter(implementation_status='implemented').count()
        themes.append({'name': label, 'total': n, 'implemented': done, 'percent': round(100 * done / n) if n else 0, 'color': COLORS[len(themes)], 'url': f'/records/controls/?theme={name}'})
    actions = []
    for task in open_tasks.select_related('owner').order_by('due_date', '-created_at')[:6]:
        actions.append({'id': task.identifier, 'title': task.title, 'kind': 'Task', 'owner': owner_name(task.owner), 'initials': initials(task.owner), 'due': task.due_date, 'status': 'Overdue' if task.overdue else label_status(task.status), 'priority': task.priority, 'url': record_url(task)})
    matrix = []
    risk_list = list(risks)
    for likelihood in range(5, 0, -1):
        row = []
        for impact in range(1, 6):
            score = likelihood * impact
            level = 'critical' if score >= 20 else 'high' if score >= 12 else 'medium' if score >= 6 else 'low'
            count = sum(r.current_likelihood == likelihood and r.current_impact == impact for r in risk_list)
            row.append({'count': count, 'color': level, 'url': f'/records/risks/?likelihood={likelihood}&impact={impact}', 'label': f'Likelihood {likelihood}, impact {impact}: {count} risks'})
        matrix.append(row)
    recent = []
    for event in m.ActivityEvent.objects.select_related('actor', 'content_type').all()[:150]:
        record = event.record
        if isinstance(record, m.Record) and can_view(user, record):
            recent.append({'actor': owner_name(event.actor), 'initials': initials(event.actor), 'verb': event.action.replace('_', ' '), 'title': record.title, 'time': event.created_at, 'url': record_url(record)})
        if len(recent) == 4:
            break
    upcoming = [{'title': a.title, 'stage': a.get_audit_type_display(), 'date': a.scheduled_date, 'url': record_url(a)} for a in scoped(user, m.Audit, scope).filter(scheduled_date__gte=today).order_by('scheduled_date')[:3]]
    blockers = []
    if not scope or scope.status not in ['approved', 'published']:
        blockers.append({'title': 'Approve the ISMS scope', 'url': '/records/scopes/'})
    undecided = implementations.filter(applicability='undecided').count()
    if undecided:
        blockers.append({'title': f'{undecided} controls need an applicability decision', 'url': '/records/controls/?applicability=undecided'})
    if total > covered:
        blockers.append({'title': f'{total - covered} applicable controls need current accepted evidence', 'url': '/records/controls/?coverage=missing'})
    if expired:
        blockers.append({'title': f'{expired} evidence versions have expired', 'url': '/records/evidence/?expired=1'})
    if overdue:
        blockers.append({'title': f'{overdue} actions are overdue', 'url': '/records/tasks/?overdue=1'})
    result = {'scope': scope, 'current_scope_url': record_url(scope) if scope else '/records/scopes/new/', 'metrics': [
        {'label': 'Controls implemented', 'value': f'{round(100 * implemented / total) if total else 0}%', 'detail': f'{implemented} of {total} applicable · {excluded} excluded', 'url': '/records/controls/?implementation_status=implemented', 'icon': 'shield', 'color': 'purple'},
        {'label': 'Evidence coverage', 'value': f'{round(100 * covered / total) if total else 0}%', 'detail': f'{covered} of {total} controls · accepted & current', 'url': '/records/controls/?coverage=current', 'icon': 'folder', 'color': 'cyan'},
        {'label': 'High & critical risks', 'value': high_risks, 'detail': f'Of {risks.count()} assessed risk scenarios', 'url': '/records/risks/?level=high', 'icon': 'alert-circle', 'color': 'orange'},
        {'label': 'Actions overdue', 'value': overdue, 'detail': f'Of {open_tasks.count()} open actions', 'url': '/records/tasks/?overdue=1', 'icon': 'clock', 'color': 'pink'},
    ], 'controls_total': total, 'excluded_count': excluded, 'implemented_count': implemented, 'evidence_count': covered, 'effectiveness_count': effective, 'approved_documents_count': approved_docs, 'documents_total': docs.count(), 'readiness_percent': readiness, 'completed_tasks': completed_tasks, 'tasks_total': num_tasks, 'stages': stage_context(user, scope), 'controls_by_theme': themes, 'matrix_rows': matrix, 'next_actions': actions, 'recent_activity': recent, 'upcoming_audits': upcoming, 'snapshot_date': today, 'scope_approved': bool(scope and scope.status in ['approved', 'published']), 'blockers': blockers, 'chart_segments': [{'label': 'Implemented', 'value': implemented, 'color': COLORS[0]}, {'label': 'In progress', 'value': applicable.filter(implementation_status='partial').count(), 'color': COLORS[1]}, {'label': 'Remaining', 'value': applicable.exclude(implementation_status__in=['implemented', 'partial']).count(), 'color': '#35344d'}]}

    # Drill-downs use the same selected scope and latest-version convention as counts.
    def scope_url(url):
        if not url or not url.startswith('/records/'):
            return url
        kind = url.split('/')[2]
        from .registry import MODULES
        model = MODULES[kind].model if kind in MODULES else None
        values = []
        if model and scope and any(f.name == 'scope' for f in model._meta.fields):
            values.append(f'scope={scope.pk}')
        if model and issubclass(model, m.VersionedRecord):
            values.append('latest=1')
        return url + ('&' if '?' in url else '?') + '&'.join(values) if values else url
    for collection in ('metrics', 'controls_by_theme', 'stages', 'blockers'):
        for item in result[collection]:
            item['url'] = scope_url(item['url'])
    for row in result['matrix_rows']:
        for cell in row:
            cell['url'] = scope_url(cell['url'])
    if not total:
        result['metrics'][0]['value'] = '—'
        result['metrics'][1]['value'] = '—'
    return result
