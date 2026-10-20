"""
Management command: python manage.py seed_dummy
Idempoten dan menggunakan bulk_create (§11, Decision 9).
Membuat:
- 3 Aplikasi dummy (dummy.<slug>)
- 4 User (satu per peran)
- 4 Cluster TERVALIDASI:
    1. 'Gagal Login': 150 ulasan (bintang 1-2) -> target TINGGI
    2. 'Notifikasi Lambat': 40 ulasan (bintang 1-2) -> target SEDANG
    3. 'Fitur Kecil': 5 ulasan (bintang 1-2) -> target RENDAH (who kosong untuk uji fallback)
    4. 'Warna Tombol': 2 ulasan (bintang 3) -> target DIABAIKAN (< 5 ulasan)
"""
from datetime import date
from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import User
from reviews.models import Aplikasi, Ulasan
from extraction.models import Cluster, HasilEkstraksi, ClusterAnggota


class Command(BaseCommand):
    help = 'Seed data dummy untuk sprint 1 secara idempoten'

    def handle(self, *args, **options):
        with transaction.atomic():
            self.seed_users()
            apps = self.seed_apps()
            self.seed_clusters(apps)
        self.stdout.write(self.style.SUCCESS("Berhasil menjalankan seed_dummy secara idempoten."))

    def seed_users(self):
        users_data = [
            ('re_user', 're@katawarga.local', User.RolePengguna.REQUIREMENTS_ENGINEER),
            ('analyst_user', 'analyst@katawarga.local', User.RolePengguna.ANALYST),
            ('po_user', 'po@katawarga.local', User.RolePengguna.PRODUCT_OWNER),
            ('dev_user', 'dev@katawarga.local', User.RolePengguna.TIM_DEVELOPER),
        ]
        for username, email, role in users_data:
            user = User.objects.filter(username=username).first()
            if not user:
                user = User.objects.create_user(username=username, email=email, password='password123', role=role)
            else:
                user.role = role
                user.save(update_fields=['role'])

    def seed_apps(self):
        apps_data = [
            ('SATU SEHAT', 'dummy.satusehat', 'Kesehatan'),
            ('Identitas Kependudukan Digital', 'dummy.ikd', 'Administrasi'),
            ('M-Pajak', 'dummy.mpajak', 'Keuangan'),
        ]
        created_apps = []
        for nama, pkg, kat in apps_data:
            app, _ = Aplikasi.objects.get_or_create(
                package_name=pkg,
                defaults={'nama_aplikasi': nama, 'kategori': kat, 'aktif': True}
            )
            created_apps.append(app)
        return created_apps

    def seed_clusters(self, apps):
        cluster_specs = [
            {
                'nama': 'Gagal Login',
                'app': apps[2],  # M-Pajak
                'count': 150,
                'stars': [1, 2],
                'who': 'wajib pajak',
                'what': 'bisa masuk ke akun tanpa gangguan force close',
                'why': 'dapat melaporkan SPT tepat waktu',
            },
            {
                'nama': 'Notifikasi Lambat',
                'app': apps[0],  # SATU SEHAT
                'count': 40,
                'stars': [1, 2],
                'who': 'masyarakat',
                'what': 'menerima notifikasi sertifikat vaksin tepat waktu',
                'why': 'tidak tertahan saat pemeriksaan perjalanan',
            },
            {
                'nama': 'Fitur Kecil',
                'app': apps[1],  # IKD
                'count': 5,
                'stars': [1, 2],
                'who': '',  # Kosong untuk menguji fallback FR-USR-04
                'what': 'melihat riwayat pembaruan dokumen',
                'why': 'bisa memastikan data sudah tersinkron',
            },
            {
                'nama': 'Warna Tombol',
                'app': apps[0],  # SATU SEHAT
                'count': 2,
                'stars': [3, 3],
                'who': 'pengguna',
                'what': 'warna tombol konfirmasi dibuat lebih kontras',
                'why': '',
            },
        ]

        today = date.today()

        for spec in cluster_specs:
            cluster, created = Cluster.objects.get_or_create(
                nama_topik=spec['nama'],
                defaults={
                    'jumlah_anggota': spec['count'],
                    'skor_signifikansi': spec['count'],
                    'status_cluster': Cluster.StatusCluster.TERVALIDASI,
                }
            )

            # Jika sudah punya anggota sebanyak spec['count'], lewati pembuatan ulasan
            existing_count = cluster.anggota_set.count()
            if existing_count >= spec['count']:
                continue

            needed = spec['count'] - existing_count
            ulasan_batch = []
            for i in range(needed):
                idx = existing_count + i + 1
                star = spec['stars'][i % len(spec['stars'])]
                ulasan_batch.append(Ulasan(
                    aplikasi=spec['app'],
                    username_reviewer=f"reviewer_{spec['nama'].lower().replace(' ', '_')}_{idx}",
                    isi_ulasan=f"Keluhan #{idx} terkait {spec['nama']} pada aplikasi {spec['app'].nama_aplikasi}",
                    tanggal_ulasan=today,
                    skor_bintang=star,
                    status_filter=Ulasan.StatusFilter.LOLOS,
                ))
            created_ulasans = Ulasan.objects.bulk_create(ulasan_batch)

            ekstraksi_batch = []
            for u in created_ulasans:
                ekstraksi_batch.append(HasilEkstraksi(
                    ulasan=u,
                    teks_who=spec['who'],
                    teks_what=spec['what'],
                    teks_why=spec['why'],
                    skor_confidence=0.92,
                    status_validasi=HasilEkstraksi.StatusValidasi.TERVALIDASI,
                ))
            created_ekstraksis = HasilEkstraksi.objects.bulk_create(ekstraksi_batch)

            anggota_batch = []
            for e in created_ekstraksis:
                anggota_batch.append(ClusterAnggota(
                    cluster=cluster,
                    hasil_ekstraksi=e,
                ))
            ClusterAnggota.objects.bulk_create(anggota_batch)

            cluster.jumlah_anggota = cluster.anggota_set.count()
            cluster.skor_signifikansi = cluster.jumlah_anggota
            cluster.save(update_fields=['jumlah_anggota', 'skor_signifikansi'])
