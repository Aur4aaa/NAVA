from django.conf import settings
from django.utils import timezone
from .registry import MODULES


def shell(request):
    from .models import Organization
    from .models import Task, VersionedRecord
    from .permissions import can_create, can_approve, visible_queryset
    organization = Organization.objects.first()
    nav_kinds = ['scopes', 'risks', 'controls', 'documents', 'evidence', 'tasks', 'audits', 'reviews', 'packs']
    navigation = [{'label': 'Overview', 'url': '/', 'icon': 'grid', 'active': request.path == '/', 'section': 'WORKSPACE'}, {'label': 'Certification roadmap', 'url': '/roadmap/', 'icon': 'map', 'active': request.path.startswith('/roadmap'), 'section': 'WORKSPACE'}]
    for kind in nav_kinds:
        module = MODULES[kind]
        navigation.append({'label': module.title, 'url': f'/records/{kind}/', 'icon': module.icon, 'active': f'/records/{kind}/' in request.path, 'section': module.section})
    navigation.append({'label': 'Traceability map', 'url': '/traceability/', 'icon': 'git-branch', 'active': request.path.startswith('/traceability'), 'section': 'ASSURANCE'})
    user = request.user
    roles = list(user.groups.values_list('name', flat=True)) if user.is_authenticated else []
    pending = 0
    if user.is_authenticated:
        for module in MODULES.values():
            if issubclass(module.model, VersionedRecord):
                pending += sum(can_approve(user, row) for row in visible_queryset(user, module.model).filter(status='in_review'))
    return {'app_name': settings.APP_NAME, 'organization': organization, 'navigation': navigation, 'role_name': roles[0] if roles else ('System administrator' if user.is_authenticated and user.is_superuser else 'Workspace member'), 'today': timezone.localdate(), 'primary_create_url': '/records/tasks/new/' if can_create(user, Task) else None, 'pending_approvals_url': '/approvals/', 'pending_count': pending}
