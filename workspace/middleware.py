from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django.utils import timezone


class OrganizationTimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from .models import Organization
        name = Organization.objects.values_list('timezone', flat=True).first()
        try:
            timezone.activate(ZoneInfo(name)) if name else timezone.deactivate()
        except (ZoneInfoNotFoundError, ValueError):
            timezone.deactivate()
        try:
            return self.get_response(request)
        finally:
            timezone.deactivate()
