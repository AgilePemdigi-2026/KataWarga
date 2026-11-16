"""
Management command: python manage.py init_roles_admin
Idempoten untuk inisialisasi akun Superuser Admin dan akun percontohan 4 peran sistem.
Dijalankan secara manual setelah database siap (KW-01, KW-11).
Tidak mengubah atau menaikkan privilege akun yang sudah ada.
"""
import os
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from accounts.models import User


class Command(BaseCommand):
    help = 'Inisialisasi akun superuser admin dan 4 akun peran (RE, Analyst, PO, Developer)'

    def handle(self, *args, **options):
        with transaction.atomic():
            self.seed_superuser()
            self.seed_role_users()
        self.stdout.write(self.style.SUCCESS("Proses inisialisasi akun selesai."))

    def seed_superuser(self):
        admin_username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin').strip()
        admin_email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@katawarga.caiis.ai.id').strip()
        admin_password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '').strip()

        user = User.objects.filter(username=admin_username).first()
        if not user:
            if not admin_password:
                raise CommandError(
                    "Variabel lingkungan DJANGO_SUPERUSER_PASSWORD wajib diatur untuk membuat superuser."
                )
            user = User.objects.create_superuser(
                username=admin_username,
                email=admin_email,
                password=admin_password,
                role=User.RolePengguna.REQUIREMENTS_ENGINEER,
            )
            self.stdout.write(self.style.SUCCESS(f"Superuser '{admin_username}' berhasil dibuat."))
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Superuser '{admin_username}' sudah ada (dilewati, hak akses dan role tidak diubah)."
                )
            )

    def seed_role_users(self):
        demo_password = os.environ.get('DEMO_USERS_PASSWORD', '').strip()
        roles_data = [
            ('re_user', 're@katawarga.caiis.ai.id', User.RolePengguna.REQUIREMENTS_ENGINEER),
            ('analyst_user', 'analyst@katawarga.caiis.ai.id', User.RolePengguna.ANALYST),
            ('po_user', 'po@katawarga.caiis.ai.id', User.RolePengguna.PRODUCT_OWNER),
            ('dev_user', 'dev@katawarga.caiis.ai.id', User.RolePengguna.TIM_DEVELOPER),
        ]
        for username, email, role in roles_data:
            user = User.objects.filter(username=username).first()
            if not user:
                if not demo_password:
                    raise CommandError(
                        "Variabel lingkungan DEMO_USERS_PASSWORD wajib diatur untuk membuat akun demo peran."
                    )
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=demo_password,
                    role=role,
                )
                self.stdout.write(self.style.SUCCESS(f"Akun demo '{username}' ({role}) berhasil dibuat."))
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Akun demo '{username}' sudah ada (dilewati, role tidak diubah)."
                    )
                )
