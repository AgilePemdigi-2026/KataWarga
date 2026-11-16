"""
Unit tests untuk management command init_roles_admin (KW-01 & KW-11).
Memverifikasi:
1. Gagal aman jika variabel password tidak diatur.
2. Berhasil membuat akun bila kredensial tersedia.
3. Idempoten dan TIDAK menimpa role atau hak akses akun yang sudah ada.
"""
import os
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from accounts.models import User


@pytest.mark.django_db
def test_init_roles_admin_gagal_bila_password_kosong(monkeypatch):
    monkeypatch.delenv('DJANGO_SUPERUSER_PASSWORD', raising=False)
    monkeypatch.delenv('DEMO_USERS_PASSWORD', raising=False)

    with pytest.raises(CommandError) as exc:
        call_command('init_roles_admin')
    assert 'DJANGO_SUPERUSER_PASSWORD' in str(exc.value)


@pytest.mark.django_db
def test_init_roles_admin_berhasil_buat_akun(monkeypatch):
    monkeypatch.setenv('DJANGO_SUPERUSER_PASSWORD', 'SecureAdminPass123!')
    monkeypatch.setenv('DEMO_USERS_PASSWORD', 'SecureDemoPass123!')

    call_command('init_roles_admin')

    admin_user = User.objects.get(username='admin')
    assert admin_user.is_superuser
    assert admin_user.is_staff
    assert admin_user.check_password('SecureAdminPass123!')

    for username, role in [
        ('re_user', User.RolePengguna.REQUIREMENTS_ENGINEER),
        ('analyst_user', User.RolePengguna.ANALYST),
        ('po_user', User.RolePengguna.PRODUCT_OWNER),
        ('dev_user', User.RolePengguna.TIM_DEVELOPER),
    ]:
        u = User.objects.get(username=username)
        assert u.role == role
        assert u.check_password('SecureDemoPass123!')


@pytest.mark.django_db
def test_init_roles_admin_tidak_menimpa_role_akun_lama(monkeypatch):
    """
    KW-11: Jika akun demo sudah ada dan perannya diubah manual,
    menjalankan command ulang TIDAK boleh mereset peran tersebut.
    """
    monkeypatch.setenv('DJANGO_SUPERUSER_PASSWORD', 'SecureAdminPass123!')
    monkeypatch.setenv('DEMO_USERS_PASSWORD', 'SecureDemoPass123!')

    # Buat akun awal
    call_command('init_roles_admin')

    # Ubah peran akun secara manual
    re_user = User.objects.get(username='re_user')
    re_user.role = User.RolePengguna.TIM_DEVELOPER
    re_user.save(update_fields=['role'])

    # Turunkan privilege admin
    admin_user = User.objects.get(username='admin')
    admin_user.is_superuser = False
    admin_user.save(update_fields=['is_superuser'])

    # Jalankan kembali command
    call_command('init_roles_admin')

    # Verifikasi role dan privilege tidak di-reset otomatis
    re_user.refresh_from_db()
    assert re_user.role == User.RolePengguna.TIM_DEVELOPER

    admin_user.refresh_from_db()
    assert not admin_user.is_superuser

