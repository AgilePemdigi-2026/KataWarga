"""
Management command: python manage.py init_roles_admin
Idempoten untuk inisialisasi akun Superuser Admin dan akun percontohan 4 peran sistem.
Sangat berguna untuk deployment Coolify/produksi agar dosen dan penguji dapat langsung login.
"""
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import User


class Command(BaseCommand):
    help = 'Inisialisasi akun superuser admin dan 4 akun peran (RE, Analyst, PO, Developer)'

    def handle(self, *args, **options):
        with transaction.atomic():
            self.seed_superuser()
            self.seed_role_users()
        self.stdout.write(self.style.SUCCESS("Berhasil inisialisasi akun admin & 4 peran."))

    def seed_superuser(self):
        admin_username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
        admin_email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@katawarga.caiis.ai.id')
        admin_password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123')

        user = User.objects.filter(username=admin_username).first()
        if not user:
            user = User.objects.create_superuser(
                username=admin_username,
                email=admin_email,
                password=admin_password,
                role=User.RolePengguna.REQUIREMENTS_ENGINEER,
            )
            self.stdout.write(self.style.SUCCESS(f"Superuser '{admin_username}' berhasil dibuat."))
        else:
            user.is_staff = True
            user.is_superuser = True
            user.save(update_fields=['is_staff', 'is_superuser'])
            self.stdout.write(f"Superuser '{admin_username}' sudah ada (status diperbarui).")

    def seed_role_users(self):
        default_password = os.environ.get('DEMO_USERS_PASSWORD', 'password123')
        roles_data = [
            ('re_user', 're@katawarga.caiis.ai.id', User.RolePengguna.REQUIREMENTS_ENGINEER),
            ('analyst_user', 'analyst@katawarga.caiis.ai.id', User.RolePengguna.ANALYST),
            ('po_user', 'po@katawarga.caiis.ai.id', User.RolePengguna.PRODUCT_OWNER),
            ('dev_user', 'dev@katawarga.caiis.ai.id', User.RolePengguna.TIM_DEVELOPER),
        ]
        for username, email, role in roles_data:
            user = User.objects.filter(username=username).first()
            if not user:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=default_password,
                    role=role,
                )
                self.stdout.write(self.style.SUCCESS(f"Akun demo '{username}' ({role}) berhasil dibuat."))
            else:
                user.role = role
                user.save(update_fields=['role'])
                self.stdout.write(f"Akun demo '{username}' sudah ada (role diperbarui).")
