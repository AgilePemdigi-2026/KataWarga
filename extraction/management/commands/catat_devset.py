"""
Mencatat ulasan yang SUDAH dikirim ke LLM saat menyetel prompt (himpunan pengembangan).

Ulasan ini tidak boleh masuk 150 ulasan evaluasi (Sprint 3 bagian F), karena prompt sudah
disesuaikan dengan isinya. Yang dicatat: review_id Play Store (stabil antar-database), bukan ID lokal.
File hanya bertambah (union), jadi aman dijalankan berulang; jalankan SEBELUM ekstraksi massal.

    python manage.py catat_devset            # tulis ke data/devset_review_ids.txt
    python manage.py catat_devset --dry-run  # hanya tampilkan jumlah
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from reviews.models import Ulasan


class Command(BaseCommand):
    help = 'Catat review_id ulasan yang sudah dikirim ke LLM sebagai himpunan pengembangan prompt.'

    def add_arguments(self, parser):
        parser.add_argument('--file', default=None, help='Lokasi file (default data/devset_review_ids.txt).')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        path = Path(opts['file'] or Path(settings.BASE_DIR) / 'data' / 'devset_review_ids.txt')
        qs = Ulasan.objects.filter(review_id__isnull=False).filter(
            Q(hasil_ekstraksi_set__nama_ekstraktor='gemini')
            | Q(galat_ekstraksi_set__nama_ekstraktor='gemini')
            | Q(alasan_filter=Ulasan.AlasanFilter.TANPA_KEBUTUHAN)
        ).distinct().select_related('aplikasi')
        baru = {f'{u.aplikasi.package_name}\t{u.review_id}' for u in qs}
        lama = set(path.read_text(encoding='utf-8').split('\n')) - {''} if path.exists() else set()
        gabungan = sorted(lama | baru)
        self.stdout.write(f'Himpunan pengembangan: {len(gabungan)} ulasan '
                          f'({len(baru - lama)} baru, {len(lama)} sudah tercatat).')
        if opts['dry_run']:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('\n'.join(gabungan) + '\n', encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'Ditulis ke {path}'))
