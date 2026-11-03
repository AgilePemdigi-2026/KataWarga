"""
Views untuk Kelola Akses Role (Backlog #4, FR-AUT).
"""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import _get_acting_role

User = get_user_model()


def kelola_role_view(request):
    """
    Halaman /kelola-role:
    Menampilkan daftar akun pengguna, perannya saat ini, serta formulir pengubahan peran.
    """
    acting_role = _get_acting_role(request)
    # Izinkan Requirements Engineer, Admin/Staff, atau Dev Mode
    if acting_role not in [User.RolePengguna.REQUIREMENTS_ENGINEER] and not (request.user and request.user.is_staff):
        return HttpResponseForbidden('Hanya Requirements Engineer atau Administrator yang dapat mengelola peran.')

    users = User.objects.all().order_by('username')
    roles = User.RolePengguna.choices

    return render(request, 'accounts/kelola_role.html', {
        'users': users,
        'roles': roles,
        'acting_role': acting_role,
    })


def ubah_role_view(request, pk):
    """
    POST /kelola-role/<pk>/ubah:
    Mengubah peran pengguna tertentu.
    """
    if request.method != 'POST':
        return HttpResponseForbidden('Metode tidak diizinkan.')

    acting_role = _get_acting_role(request)
    if acting_role not in [User.RolePengguna.REQUIREMENTS_ENGINEER] and not (request.user and request.user.is_staff):
        return HttpResponseForbidden('Hanya Requirements Engineer atau Administrator yang dapat mengubah peran.')

    target_user = get_object_or_404(User, pk=pk)
    new_role = request.POST.get('role', '').strip()

    valid_roles = [c[0] for c in User.RolePengguna.choices]
    if new_role not in valid_roles:
        messages.error(request, 'Pilihan peran tidak valid.')
        return redirect('accounts:kelola_role')

    target_user.role = new_role
    target_user.save(update_fields=['role'])

    messages.success(
        request,
        f"Peran untuk pengguna '{target_user.username}' berhasil diubah menjadi {target_user.get_role_display()}."
    )
    return redirect('accounts:kelola_role')


def switch_acting_role_view(request):
    """
    POST /kelola-role/switch:
    Mengubah peran aktif dev mode dalam sesi untuk pengujian alur antarmuka antar role.
    """
    if request.method != 'POST':
        return HttpResponseForbidden('Metode tidak diizinkan.')

    new_role = request.POST.get('acting_role', '').strip()
    valid_roles = [c[0] for c in User.RolePengguna.choices]

    if new_role in valid_roles:
        request.session['acting_role'] = new_role
        messages.info(request, f"Simulasi peran aktif diubah menjadi: {new_role}")
    else:
        request.session.pop('acting_role', None)
        messages.info(request, "Simulasi peran aktif dikembalikan ke default.")

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/'
    return redirect(next_url)

