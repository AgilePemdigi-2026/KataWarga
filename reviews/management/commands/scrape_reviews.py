"""
Menarik ulasan aplikasi target dari Google Play Store (UC-1, langkah scraping + filter).

Contoh:
    python manage.py scrape_reviews --seed            # buat/perbarui data Aplikasi dari settings
    python manage.py scrape_reviews                   # tarik semua aplikasi aktif
    python manage.py scrape_reviews --app com.contoh.app --count 50 --dry-run

Cocok dipanggil dari cron (FR-EKS-01). Keluar dengan kode != 0 bila ada aplikasi yang gagal.
"""
import logging
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from reviews.models import Aplikasi
from reviews.services import ingest, scraper

logger = logging.getLogger('reviews.scraping')


def _siapkan_log_file():
    """Catat kegagalan ke logs/scraping.log: waktu, aplikasi, penyebab (FR-EKS-10)."""
    if any(isinstance(h, logging.FileHandler) for h in logger.handlers):
        return
    log_dir = Path(settings.BASE_DIR) / 'logs'
    log_dir.mkdir(exist_ok=True)
    handler = logging.FileHandler(log_dir / 'scraping.log', encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class Command(BaseCommand):
    help = 'Tarik ulasan Play Store untuk aplikasi target, saring, lalu simpan tanpa duplikat.'

    def add_arguments(self, parser):
        parser.add_argument('--app', action='append', default=[], metavar='PACKAGE',
                            help='Batasi pada package_name tertentu (boleh diulang).')
        parser.add_argument('--count', type=int, default=None,
                            help='Jumlah ulasan per aplikasi (default: settings.SCRAPING).')
        parser.add_argument('--seed', action='store_true',
                            help='Buat/perbarui data Aplikasi dari settings.SCRAPER_TARGET_APPS.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Tarik dan hitung saja, tanpa menyimpan ke basis data.')

    # ------------------------------------------------------------------ seed
    def _seed(self):
        dibuat = diperbarui = 0
        for t in settings.SCRAPER_TARGET_APPS:
            if not t.get('package_name'):
                self.stderr.write(self.style.WARNING(
                    f"Lewati {t['nama_aplikasi']}: package_name belum diisi di settings."))
                continue
            _, baru = Aplikasi.objects.update_or_create(
                package_name=t['package_name'],
                defaults={'nama_aplikasi': t['nama_aplikasi'],
                          'kategori': t.get('kategori', ''), 'aktif': True},
            )
            dibuat += baru
            diperbarui += not baru
        self.stdout.write(f'Seed aplikasi: {dibuat} dibuat, {diperbarui} diperbarui.')

    # ---------------------------------------------------------------- handle
    def handle(self, *args, **opts):
        _siapkan_log_file()
        cfg = settings.SCRAPING
        if opts['seed']:
            self._seed()

        aplikasi_qs = Aplikasi.objects.filter(aktif=True).order_by('id')
        if opts['app']:
            aplikasi_qs = aplikasi_qs.filter(package_name__in=opts['app'])
        daftar = list(aplikasi_qs)
        if not daftar:
            raise CommandError('Tidak ada aplikasi aktif. Jalankan dengan --seed '
                               'atau tambahkan data Aplikasi lebih dulu.')

        jumlah = opts['count'] or cfg['jumlah_default']
        dry = opts['dry_run']
        gagal = []
        total = ingest.Hasil()

        for app in daftar:
            sub = ingest.Hasil()
            try:
                for batch in scraper.tarik_ulasan(
                    app.package_name, jumlah=jumlah, lang=cfg['lang'], country=cfg['country'],
                    batch_size=cfg['batch_size'], jeda=cfg['jeda_detik'],
                    max_retry=cfg['max_retry'], backoff_dasar=cfg['backoff_dasar_detik'],
                ):
                    sub.tambah(ingest.simpan_batch(app, batch, dry_run=dry, cfg=cfg))
            except scraper.ScrapingError as exc:
                # FR-EKS-10/11: catat log, jangan ubah data lama, lanjut ke aplikasi berikutnya.
                logger.error('app=%s gagal: %s', app.package_name, exc)
                gagal.append(app.nama_aplikasi)
                self.stderr.write(self.style.ERROR(f'[{app.nama_aplikasi}] GAGAL: {exc}'))
            logger.info('app=%s baru=%s duplikat=%s lolos=%s dibuang=%s dry_run=%s',
                        app.package_name, sub.baru, sub.duplikat, sub.lolos, sub.dibuang, dry)
            self.stdout.write(
                f'[{app.nama_aplikasi}] diterima={sub.diterima} baru={sub.baru} '
                f'duplikat={sub.duplikat} lolos={sub.lolos} dibuang={sub.dibuang} '
                f'dilewati={sub.dilewati}' + (' (dry-run)' if dry else ''))
            total.tambah(sub)

        self.stdout.write(self.style.SUCCESS(
            f'Selesai. Total baru={total.baru}, duplikat={total.duplikat}, '
            f'lolos={total.lolos}, dibuang={total.dibuang}.'))
        if gagal:
            raise CommandError(f"{len(gagal)} aplikasi gagal: {', '.join(gagal)}. "
                               'Lihat logs/scraping.log.')
