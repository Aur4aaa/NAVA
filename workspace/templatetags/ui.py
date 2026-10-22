from django import template
from django.utils.safestring import mark_safe

register = template.Library()

ICONS = {
    'grid': '<rect x="3" y="3" width="7" height="7" rx="1.7"/><rect x="14" y="3" width="7" height="7" rx="1.7"/><rect x="3" y="14" width="7" height="7" rx="1.7"/><rect x="14" y="14" width="7" height="7" rx="1.7"/>',
    'dashboard': '<rect x="3" y="3" width="7" height="7" rx="1.7"/><rect x="14" y="3" width="7" height="7" rx="1.7"/><rect x="3" y="14" width="7" height="7" rx="1.7"/><rect x="14" y="14" width="7" height="7" rx="1.7"/>',
    'route': '<circle cx="6" cy="5" r="2"/><circle cx="18" cy="19" r="2"/><path d="M8 5h7a4 4 0 0 1 0 8H9a3 3 0 0 0 0 6h7"/>',
    'roadmap': '<circle cx="6" cy="5" r="2"/><circle cx="18" cy="19" r="2"/><path d="M8 5h7a4 4 0 0 1 0 8H9a3 3 0 0 0 0 6h7"/>',
    'scope': '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 1v4m0 14v4M1 12h4m14 0h4"/>',
    'target': '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="m16 8 5-5m-1 4 1-4-4 1"/>',
    'shield': '<path d="m12 3 8 3v6c0 4-4 7-8 9-4-2-8-5-8-9V6l8-3Z"/><path d="m8 12 3 3 5-6"/>',
    'risk': '<path d="m10.3 4-8 14a2 2 0 0 0 1.7 3h16a2 2 0 0 0 1.7-3l-8-14a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4m0 4h.01"/>',
    'controls': '<path d="m12 3 8 3v6c0 4-4 7-8 9-4-2-8-5-8-9V6l8-3Z"/><path d="m8 12 3 3 5-6"/>',
    'file': '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Z"/><path d="M14 3v6h6M8 13h8m-8 4h5"/>',
    'documents': '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Z"/><path d="M14 3v6h6M8 13h8m-8 4h5"/>',
    'folder': '<path d="M3 7V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/>',
    'evidence': '<path d="M3 7V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/><path d="m8 14 3 3 5-6"/>',
    'checklist': '<rect x="5" y="3" width="16" height="18" rx="2"/><path d="m8 8 1 1 2-2m3 1h4m-10 6 1 1 2-2m3 1h4"/>',
    'audit': '<rect x="5" y="3" width="16" height="18" rx="2"/><path d="m8 8 1 1 2-2m3 1h4m-10 6 1 1 2-2m3 1h4"/>',
    'tasks': '<rect x="3" y="3" width="18" height="18" rx="4"/><path d="m7 12 3 3 7-7"/>',
    'check': '<path d="m5 12 4 4L19 6"/>',
    'clock': '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    'calendar': '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18m-13 5h2m4 0h2"/>',
    'users': '<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3m2-16a3 3 0 0 1 0 6m4 10v-3a6 6 0 0 0-4-5"/>',
    'review': '<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3m2-16a3 3 0 0 1 0 6m4 10v-3a6 6 0 0 0-4-5"/>',
    'network': '<circle cx="12" cy="5" r="3"/><circle cx="5" cy="19" r="3"/><circle cx="19" cy="19" r="3"/><path d="m11 8-5 8m7-8 5 8M8 19h8"/>',
    'search': '<circle cx="10.8" cy="10.8" r="7.3"/><path d="m16 16 4.5 4.5"/>',
    'plus': '<path d="M12 5v14M5 12h14"/>',
    'arrow': '<path d="M5 12h14m-5-5 5 5-5 5"/>',
    'arrow-up': '<path d="M7 17 17 7M7 7h10v10"/>',
    'chevron': '<path d="m9 5 7 7-7 7"/>',
    'down': '<path d="m6 9 6 6 6-6"/>',
    'download': '<path d="M12 3v12m-4-4 4 4 4-4M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/>',
    'upload': '<path d="M12 16V4m-4 4 4-4 4 4M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/>',
    'bell': '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
    'settings': '<path d="m10 3-1 3-3 1-3-1-1 3 2 2v3l-2 2 1 3 3-1 3 1 1 3h4l1-3 3-1 3 1 1-3-2-2v-3l2-2-1-3-3 1-3-1-1-3Z"/><circle cx="12" cy="12" r="3"/>',
    'logout': '<path d="M9 4H4v16h5m4-4 4-4-4-4M7 12h14"/>',
    'menu': '<path d="M4 6h16M4 12h16M4 18h16"/>',
    'close': '<path d="m6 6 12 12M18 6 6 18"/>',
    'info': '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/>',
    'lock': '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2"/>',
    'activity': '<path d="M2 12h5l3-8 4 16 3-8h5"/>',
    'edit': '<path d="m16 3 5 5-12 12-6 1 1-6Z"/><path d="m13 6 5 5"/>',
    'layers': '<path d="m12 3 10 5-10 5L2 8Zm-10 9 10 5 10-5M2 17l10 5 10-5"/>',
    'building': '<path d="M4 21V3h12v18M2 21h20m-6-13h4v13M8 7h4M8 11h4m-4 4h4m-2 6v-3"/>',
    'certificate': '<circle cx="12" cy="9" r="6"/><path d="m8 14-1 8 5-3 5 3-1-8"/>',
    'filter': '<path d="M3 5h18l-7 8v6l-4 2v-8Z"/>',
    'link': '<path d="m10 13 4-4m-6 7-1 1a4 4 0 0 1-6-6l5-5a4 4 0 0 1 6 0m0 2 1-1a4 4 0 0 1 6 6l-5 5a4 4 0 0 1-6 0"/>',
}

@register.simple_tag
def icon(name, size=20):
    aliases = {'map': 'route', 'git-branch': 'network', 'check-square': 'tasks', 'check-circle': 'check', 'file-text': 'file', 'clipboard': 'checklist', 'alert-circle': 'risk', 'archive': 'folder', 'award': 'certificate'}
    name = aliases.get(name, name)
    path = ICONS.get(name, ICONS['file'])
    try:
        size = max(10, min(64, int(size)))
    except (ValueError, TypeError):
        size = 20
    return mark_safe(f'<svg class="icon" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{path}</svg>')

@register.filter
def initials(value):
    words = str(value or '').split()
    return ''.join(word[0] for word in words[:2]).upper() or 'N'

@register.filter
def humanize(value):
    return str(value or '').replace('_', ' ').replace('-', ' ').capitalize()

@register.filter
def percentage(value, total):
    try:
        return round(float(value) / float(total) * 100)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0
