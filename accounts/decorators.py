"""Decorator RBAC — stub peran untuk Sprint 1-2 (§4)."""
import functools
from django.conf import settings
from django.http import HttpResponseForbidden


def _get_acting_role(request):
    """Kembalikan peran aktif: dari user.role jika login, kalau tidak DEV_ACTING_ROLE."""
    if request.user and request.user.is_authenticated:
        return request.user.role
    return getattr(settings, 'DEV_ACTING_ROLE', None)


def role_required(*roles):
    """Decorator: hanya izinkan peran tertentu. Selain itu 403."""
    def decorator(view_func):
        @functools.wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            acting = _get_acting_role(request)
            if acting not in roles:
                return HttpResponseForbidden('Akses ditolak.')
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
