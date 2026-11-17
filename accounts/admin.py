"""Konfigurasi Django Admin untuk Model Pengguna KataWarga dengan proteksi RBAC."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import PermissionDenied
from django.db import transaction

from .models import User


def _can_manage_users_admin(user):
    """
    Hanya Superuser dan Product Owner yang berhak mengelola Pengguna di Django Admin.
    Staf lain (Requirements Engineer, Analyst, Tim Developer) dilarang.
    """
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or user.role == User.RolePengguna.PRODUCT_OWNER)
    )


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'is_active', 'is_staff', 'is_superuser')
    list_filter = ('role', 'is_active', 'is_staff', 'is_superuser')
    fieldsets = UserAdmin.fieldsets + (
        ('Peran', {'fields': ('role',)}),
    )

    def has_module_permission(self, request):
        """Hanya superuser dan Product Owner yang dapat melihat modul User."""
        return _can_manage_users_admin(request.user)

    def has_view_permission(self, request, obj=None):
        """Hanya superuser dan Product Owner yang dapat melihat data User."""
        return _can_manage_users_admin(request.user)

    def has_add_permission(self, request):
        """Hanya superuser dan Product Owner yang dapat menambahkan User."""
        return _can_manage_users_admin(request.user)

    def has_change_permission(self, request, obj=None):
        """
        Non-superuser (termasuk Product Owner) dilarang mengubah akun superuser.
        Staf non-PO dilarang mengubah akun siapa pun.
        """
        if not _can_manage_users_admin(request.user):
            return False
        if obj is not None and obj.is_superuser and not request.user.is_superuser:
            return False
        return True

    def has_delete_permission(self, request, obj=None):
        """
        Non-superuser (termasuk PO) dilarang menghapus akun superuser atau akun sendiri.
        Superuser aktif terakhir tidak boleh dihapus.
        """
        if not _can_manage_users_admin(request.user):
            return False
        if obj is not None:
            if obj.is_superuser and not request.user.is_superuser:
                return False
            if obj.is_superuser and obj.is_active:
                remaining = list(
                    User.objects.filter(is_superuser=True, is_active=True)
                    .exclude(pk=obj.pk)
                    .order_by("id")
                )
                if len(remaining) < 1:
                    return False
            if obj.pk == request.user.pk:
                return False
        return True

    def get_readonly_fields(self, request, obj=None):
        """
        Cegah privilege escalation:
        - Non-superuser tidak boleh memberikan is_staff, is_superuser, groups, atau user_permissions.
        - Non-superuser tidak boleh mengubah akun superuser (semua field readonly).
        - Pengguna tidak boleh memodifikasi peran (role) akun sendiri di Django Admin.
        """
        readonly = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            for field in ('is_superuser', 'is_staff', 'groups', 'user_permissions'):
                if field not in readonly:
                    readonly.append(field)
            if obj and obj.pk == request.user.pk:
                if 'role' not in readonly:
                    readonly.append('role')
                if 'is_active' not in readonly:
                    readonly.append('is_active')
            if obj and obj.is_superuser:
                return [f.name for f in self.model._meta.fields]
        return readonly

    def save_model(self, request, obj, form, change):
        """
        Backend guard saat penyimpanan instance User melalui Django Admin.
        Menegakkan keamanan mutlak terlepas dari input form.
        """
        # 1. Otorisasi peran pengelola
        if not _can_manage_users_admin(request.user):
            raise PermissionDenied("Hanya superuser dan Product Owner yang dapat mengelola pengguna.")

        # 2. Pembatasan ketat untuk Product Owner (non-superuser)
        if not request.user.is_superuser:
            # Dilarang memberikan is_staff atau is_superuser saat membuat user baru
            if not change and (obj.is_superuser or obj.is_staff):
                raise PermissionDenied("Product Owner tidak boleh memberikan hak staf atau superuser.")

            # Dilarang memodifikasi akun superuser
            if obj.is_superuser:
                raise PermissionDenied("Product Owner tidak dapat memodifikasi akun superuser.")

            if change:
                orig = User.objects.get(pk=obj.pk)
                if (not orig.is_staff and obj.is_staff) or (not orig.is_superuser and obj.is_superuser):
                    raise PermissionDenied("Product Owner tidak boleh memberikan hak staf atau superuser.")
                if obj.pk == request.user.pk:
                    if obj.role != orig.role:
                        raise PermissionDenied("Product Owner tidak dapat mengubah peran akun sendiri.")
                    if not obj.is_active:
                        raise PermissionDenied("Anda tidak dapat menonaktifkan akun Anda sendiri.")

        # 3. Guard umum (berlaku juga untuk superuser)
        # Invariant: minimal satu superuser aktif harus selalu dipertahankan
        if change:
            orig = User.objects.filter(pk=obj.pk).first()
            if orig:
                was_active_su = orig.is_superuser and orig.is_active
                now_active_su = obj.is_superuser and obj.is_active
                if was_active_su and not now_active_su:
                    with transaction.atomic():
                        active_su = list(
                            User.objects.select_for_update()
                            .filter(is_superuser=True, is_active=True)
                            .order_by("id")
                        )
                        remaining = [u for u in active_su if u.pk != obj.pk]
                        if len(remaining) < 1:
                            raise PermissionDenied(
                                "Tidak dapat menonaktifkan atau mencabut hak superuser aktif terakhir."
                            )

        # Larangan menonaktifkan akun sendiri
        if obj.pk == request.user.pk and not obj.is_active:
            raise PermissionDenied("Anda tidak dapat menonaktifkan akun Anda sendiri.")

        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        """Cegah non-superuser memberikan groups atau user_permissions via related m2m."""
        if not request.user.is_superuser:
            if form.cleaned_data.get('groups') or form.cleaned_data.get('user_permissions'):
                raise PermissionDenied("Product Owner tidak boleh memberikan grup atau permissions.")
        super().save_related(request, form, formsets, change)

    def delete_model(self, request, obj):
        """Backend guard saat penghapusan satu instance User melalui Django Admin."""
        if not _can_manage_users_admin(request.user):
            raise PermissionDenied("Hanya superuser dan Product Owner yang dapat mengelola pengguna.")

        if not request.user.is_superuser and obj.is_superuser:
            raise PermissionDenied("Hanya superuser yang dapat menghapus akun superuser.")

        # Evaluasi superuser aktif terakhir sebelum aturan self-delete
        if obj.is_superuser and obj.is_active:
            with transaction.atomic():
                active_su = list(
                    User.objects.select_for_update()
                    .filter(is_superuser=True, is_active=True)
                    .order_by("id")
                )
                remaining = [u for u in active_su if u.pk != obj.pk]
                if len(remaining) < 1:
                    raise PermissionDenied("Tidak dapat menghapus superuser aktif terakhir.")

        if obj.pk == request.user.pk:
            raise PermissionDenied("Anda tidak dapat menghapus akun sendiri.")

        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        """Backend guard saat penghapusan bulk User melalui Django Admin."""
        if not _can_manage_users_admin(request.user):
            raise PermissionDenied("Hanya superuser dan Product Owner yang dapat mengelola pengguna.")

        if not request.user.is_superuser and queryset.filter(is_superuser=True).exists():
            raise PermissionDenied("Hanya superuser yang dapat menghapus akun superuser.")

        # Evaluasi invariant penghapusan semua superuser aktif sebelum self-delete
        with transaction.atomic():
            active_su = list(
                User.objects.select_for_update()
                .filter(is_superuser=True, is_active=True)
                .order_by("id")
            )
            deleting_ids = set(queryset.values_list("pk", flat=True))
            remaining = [u for u in active_su if u.pk not in deleting_ids]
            if len(active_su) > 0 and len(remaining) < 1:
                raise PermissionDenied("Operasi ini akan menghapus semua superuser aktif.")

        if queryset.filter(pk=request.user.pk).exists():
            raise PermissionDenied("Anda tidak dapat menghapus akun sendiri.")

        super().delete_queryset(request, queryset)

    def get_actions(self, request):
        """Sembunyikan actions untuk staf yang tidak berwenang."""
        actions = super().get_actions(request)
        if not _can_manage_users_admin(request.user):
            return {}
        return actions
