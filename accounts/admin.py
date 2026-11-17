"""Konfigurasi Django Admin untuk Model Pengguna KataWarga dengan proteksi RBAC."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import PermissionDenied

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'is_active', 'is_staff', 'is_superuser')
    list_filter = ('role', 'is_active', 'is_staff', 'is_superuser')
    fieldsets = UserAdmin.fieldsets + (
        ('Peran', {'fields': ('role',)}),
    )

    def has_change_permission(self, request, obj=None):
        """Non-superuser staf dilarang mengubah akun superuser."""
        if obj is not None and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """Non-superuser staf dilarang menghapus akun superuser, dan superuser terakhir dilindungi."""
        if obj is not None:
            if obj.is_superuser and not request.user.is_superuser:
                return False
            if obj.is_superuser and obj.is_active:
                remaining = (
                    User.objects.filter(is_superuser=True, is_active=True)
                    .exclude(pk=obj.pk)
                    .count()
                )
                if remaining < 1:
                    return False
        return super().has_delete_permission(request, obj)

    def get_readonly_fields(self, request, obj=None):
        """Cegah non-superuser memanipulasi permission/superuser flags."""
        readonly = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            for field in ('is_superuser', 'user_permissions', 'groups'):
                if field not in readonly:
                    readonly.append(field)
            if obj and obj.is_superuser:
                return [f.name for f in self.model._meta.fields]
        return readonly

    def save_model(self, request, obj, form, change):
        """Backend guard saat penyimpanan instance User melalui Django Admin."""
        if obj.is_superuser and not request.user.is_superuser:
            raise PermissionDenied("Hanya superuser yang dapat memodifikasi akun superuser.")

        if obj.pk == request.user.pk and not obj.is_active:
            raise PermissionDenied("Anda tidak dapat menonaktifkan akun Anda sendiri.")

        if obj.is_superuser and not obj.is_active and change:
            remaining = (
                User.objects.filter(is_superuser=True, is_active=True)
                .exclude(pk=obj.pk)
                .count()
            )
            if remaining < 1:
                raise PermissionDenied("Tidak dapat menonaktifkan superuser aktif terakhir.")

        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        """Backend guard saat penghapusan satu instance User melalui Django Admin."""
        if obj.is_superuser and not request.user.is_superuser:
            raise PermissionDenied("Hanya superuser yang dapat menghapus akun superuser.")
        if obj.is_superuser and obj.is_active:
            remaining = (
                User.objects.filter(is_superuser=True, is_active=True)
                .exclude(pk=obj.pk)
                .count()
            )
            if remaining < 1:
                raise PermissionDenied("Tidak dapat menghapus superuser aktif terakhir.")
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        """Backend guard saat penghapusan bulk User melalui Django Admin."""
        if not request.user.is_superuser and queryset.filter(is_superuser=True).exists():
            raise PermissionDenied("Hanya superuser yang dapat menghapus akun superuser.")
        active_su_in_qs = queryset.filter(is_superuser=True, is_active=True).count()
        total_active_su = User.objects.filter(is_superuser=True, is_active=True).count()
        if total_active_su > 0 and active_su_in_qs >= total_active_su:
            raise PermissionDenied("Operasi ini akan menghapus semua superuser aktif.")
        super().delete_queryset(request, queryset)
