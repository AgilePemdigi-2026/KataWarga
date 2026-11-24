"""
Terapkan ulang filter terbaru ke ulasan yang sudah tersimpan (Sprint 3 bagian B).

  python manage.py refilter_reviews                  # dry-run: hanya melaporkan
  python manage.py refilter_reviews --apply          # tulis perubahan
  python manage.py refilter_reviews --apply --pulihkan

Kebijakan aman:
- LOLOS yang kini terkena aturan -> DIBUANG beserta alasannya (hanya dengan --apply).
- DIBUANG tanpa alasan -> alasan diisi (aturan yang mengena; bila tidak ada: 'tanpa kebutuhan').
- DIBUANG -> LOLOS (pemulihan) HANYA dengan --pulihkan, dan hanya bila bukan 'duplikat'/'tanpa kebutuhan'.
- Ulasan yang sudah punya hasil ekstraksi tidak pernah diubah.
"""
from collections import Counter

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from reviews.models import Ulasan
from reviews.services import filtering


class Command(BaseCommand):
    help = 'Terapkan ulang filter ulasan dan catat alasan pembuangan.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Tulis perubahan (default: dry-run).')
        parser.add_argument('--pulihkan', action='store_true', help='Izinkan DIBUANG -> LOLOS bila aturan terbaru meloloskan.')
        parser.add_argument('--aplikasi', action='append', default=[], help='package_name (boleh berulang).')

    def handle(self, *args, **opts):
        cfg = settings.SCRAPING
        qs = Ulasan.objects.select_related('aplikasi').filter(hasil_ekstraksi_set__isnull=True).order_by('aplikasi_id', 'tanggal_ulasan', 'id')
        if opts['aplikasi']:
            qs = qs.filter(aplikasi__package_name__in=opts['aplikasi'])

        sudah_lolos = {}  # aplikasi_id -> kunci teks ulasan LOLOS yang dipertahankan
        ubah, ringkas = [], Counter()
        for u in qs.iterator():
            kunci_ada = sudah_lolos.setdefault(u.aplikasi_id, set())
            k = filtering.evaluasi_ulasan(u.isi_ulasan, u.skor_bintang, cfg)
            lolos, alasan = k.lolos, k.alasan
            kunci = filtering.kunci_duplikat(u.isi_ulasan)
            if lolos and kunci in kunci_ada:
                lolos, alasan = False, filtering.ALASAN_DUPLIKAT

            target_status, target_alasan = u.status_filter, u.alasan_filter
            if u.status_filter == Ulasan.StatusFilter.LOLOS:
                if not lolos:
                    target_status, target_alasan = Ulasan.StatusFilter.DIBUANG, alasan
            else:
                if not lolos:
                    if not u.alasan_filter:
                        target_alasan = alasan
                elif opts['pulihkan'] and u.alasan_filter not in (filtering.ALASAN_DUPLIKAT, filtering.ALASAN_TANPA_KEBUTUHAN) and u.alasan_filter:
                    target_status, target_alasan = Ulasan.StatusFilter.LOLOS, ''
                elif not u.alasan_filter:
                    target_alasan = filtering.ALASAN_TANPA_KEBUTUHAN  # lolos aturan, tetapi pernah dibuang (hasil ekstraksi kosong)
            if target_status == Ulasan.StatusFilter.LOLOS:
                kunci_ada.add(kunci)
            if (target_status, target_alasan) != (u.status_filter, u.alasan_filter):
                ubah.append((u, target_status, target_alasan))
                ringkas[f'{u.status_filter}->{target_status} [{target_alasan or "-"}]'] += 1

        for baris, jumlah in sorted(ringkas.items()):
            self.stdout.write(f'  {jumlah:5d}  {baris}')
        mode = 'DITERAPKAN' if opts['apply'] else 'dry-run (tidak ada yang ditulis)'
        if opts['apply'] and ubah:
            with transaction.atomic():
                for u, status, alasan in ubah:
                    Ulasan.objects.filter(pk=u.pk).update(status_filter=status, alasan_filter=alasan)
        self.stdout.write(self.style.SUCCESS(f'Selesai: {len(ubah)} ulasan berubah, {mode}.'))
