"""Server-side role and record visibility policies; UI visibility is not authority."""
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils import timezone

ROLE_NAMES = ('System administrator', 'Manager', 'Approver', 'Risk owner', 'Control owner', 'Document approver', 'Internal auditor', 'External auditor', 'Contributor', 'Viewer')
BUSINESS_ROLES = set(ROLE_NAMES) - {'System administrator', 'External auditor'}
OWNER_EDIT_TYPES = {
    'Risk owner': {'riskassessmentversion', 'treatmentplan', 'riskacceptance', 'task', 'evidenceversion', 'correctiveaction'},
    'Control owner': {'controlimplementation', 'documentversion', 'evidenceversion', 'task', 'asset', 'supplier', 'metricresult', 'correctiveaction'},
    'Document approver': {'documentversion', 'task', 'evidenceversion'},
    'Internal auditor': {'audit', 'finding', 'correctiveaction', 'evidenceversion', 'task'},
    'Contributor': {'task', 'evidenceversion'},
}


def ensure_roles():
    """Idempotently create presets; management authority requires explicit membership."""
    groups = {}
    for name in ROLE_NAMES:
        group, _ = Group.objects.get_or_create(name=name)
        groups[name] = group
    # Permissions are useful in standard Django integrations; application policies below
    # additionally check record ownership, classification, and workflow status.
    groups['Viewer'].permissions.set(Permission.objects.filter(content_type__app_label='workspace', codename__startswith='view_'))
    groups['Manager'].permissions.set(Permission.objects.filter(content_type__app_label='workspace').exclude(codename__startswith='delete_'))
    groups['System administrator'].permissions.set(Permission.objects.filter(content_type__app_label__in=['auth', 'sessions']))
    return groups


def roles(user):
    if not user or not user.is_authenticated or not user.is_active:
        return set()
    return set(user.groups.values_list('name', flat=True))


def has_role(user, *names):
    return bool(roles(user).intersection(names))


def _model(value):
    return value if isinstance(value, type) else value.model if hasattr(value, 'model') else type(value)


def visible_queryset(user, model_or_queryset):
    model = _model(model_or_queryset)
    qs = model.objects.all() if isinstance(model_or_queryset, type) else model_or_queryset
    user_roles = roles(user)
    if not user_roles:
        return qs.none()
    if not hasattr(model, 'classification'):
        return qs if user_roles.intersection(BUSINESS_ROLES) else qs.none()
    if user_roles.intersection(BUSINESS_ROLES):
        return qs.filter(Q(classification='internal') | Q(owner=user) | Q(created_by=user) | Q(allowed_users=user) | Q(classification='confidential', owner=user) | (Q(classification='confidential') if 'Manager' in user_roles else Q(pk__in=[]))).distinct()
    if 'External auditor' in user_roles and model._meta.model_name in {'evidenceversion', 'auditpack'}:
        return qs.filter(allowed_users=user, access_expires__gt=timezone.now()).distinct()
    return qs.none()


def can_view(user, record):
    return bool(record.pk and visible_queryset(user, type(record)).filter(pk=record.pk).exists())


def require_view(user, record):
    if not can_view(user, record):
        raise PermissionDenied('You do not have access to this record.')


def can_create(user, model):
    user_roles = roles(user)
    name = _model(model)._meta.model_name
    if name in {'approval', 'activityevent', 'frameworkversion', 'controlreference', 'requirementreference', 'organization'}:
        return False
    if 'Manager' in user_roles:
        return True
    return any(name in OWNER_EDIT_TYPES.get(role, set()) for role in user_roles)


def can_edit(user, record=None):
    if record is None:
        return has_role(user, 'Manager')
    if not can_view(user, record):
        return False
    if record._meta.model_name in {'approval', 'activityevent', 'frameworkversion', 'controlreference', 'requirementreference'}:
        return False
    if record.status in getattr(record, 'FROZEN_STATUSES', ()):
        return False
    if record._meta.model_name in {'task', 'audit', 'finding', 'correctiveaction'} and record.status in {'complete', 'closed'}:
        return False
    if has_role(user, 'Manager'):
        return True
    return bool(record.owner_id == user.pk and can_create(user, type(record)))


def require_edit(user, record=None):
    if not can_edit(user, record):
        raise PermissionDenied('Only the ISMS manager or an assigned, authorized owner may edit this record.')


def can_approve(user, record):
    if not can_view(user, record):
        return False
    name = record._meta.model_name
    if name in {'treatmentplan', 'riskacceptance'}:
        return has_role(user, 'Approver') or (has_role(user, 'Risk owner') and record.risk.owner_id == user.pk)
    if name == 'documentversion':
        if record.approver_id and record.approver_id != user.pk:
            return False
        return has_role(user, 'Approver', 'Document approver')
    if name == 'evidenceversion':
        return has_role(user, 'Manager', 'Approver') or (has_role(user, 'Control owner', 'Internal auditor') and record.reviewer_id == user.pk)
    if name not in {'scopeversion', 'riskmethodologyversion', 'riskassessmentversion', 'soaversion', 'gapassessment', 'managementreview', 'certificationrecord'}:
        return False
    return has_role(user, 'Approver')
