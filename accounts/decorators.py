"""Helper RBAC dan decorator peran untuk KataWarga (§4)."""
import functools

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden

from accounts.models import User


def _valid_roles():
    """Daftar kode peran yang valid, diambil dari model User."""
    return [role[0] for role in User.RolePengguna.choices]


def _get_acting_role(request):
    """
    Kembalikan peran efektif pengguna.

    - Pengguna anonim tidak memiliki peran efektif (``None``).
    - Staf pada mode DEBUG boleh memakai simulasi ``acting_role`` dari session
      selama nilainya termasuk peran yang valid.
    - Selain itu, gunakan peran asli dari akun Django.
    """
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return None

    if settings.DEBUG and user.is_staff:
        session = getattr(request, 'session', None)
        simulated_role = session.get('acting_role') if session is not None else None
        if simulated_role in _valid_roles():
            return simulated_role

    return user.role


def role_required(*roles):
    """
    Decorator: hanya izinkan peran efektif tertentu.

    Pengguna yang belum login diarahkan ke halaman Login. Pengguna yang sudah
    login tetapi tidak memiliki peran yang diizinkan menerima HTTP 403.
    """

    def decorator(view_func):
        @functools.wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = getattr(request, 'user', None)
            if user is None or not user.is_authenticated:
                return redirect_to_login(request.get_full_path())

            acting = _get_acting_role(request)
            if acting not in roles:
                return HttpResponseForbidden('Akses ditolak.')

            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
