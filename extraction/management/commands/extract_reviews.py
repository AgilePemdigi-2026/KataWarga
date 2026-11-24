"""
Mengekstraksi who-what-why dari ulasan yang lolos filter dan belum diekstraksi (UC-1).

Contoh:
    python manage.py extract_reviews --dry-run --limit 20
    python manage.py extract_reviews
    python manage.py extract_reviews --app com.contoh.app --extractor aturan
    python manage.py extract_reviews --extractor gemini --limit 20
"""
import logging
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from extraction.services import registry, runner

logger = logging.getLogger('extraction.pipeline')


def _siapkan_log_file():
    """Catat kegagalan ke logs/extraction.log (waktu, ulasan, penyebab)."""
    if any(isinstance(h, logging.FileHandler) for h in logger.handlers):
        return
    log_dir = Path(settings.BASE_DIR) / 'logs'
    log_dir.mkdir(exist_ok=True)
    handler = logging.FileHandler(log_dir / 'extraction.log', encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class Command(BaseCommand):
    help = 'Ekstraksi who-what-why untuk ulasan LOLOS yang belum punya hasil ekstraksi.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=None, help='Batasi jumlah ulasan yang diproses.')
        parser.add_argument('--app', action='append', default=[], metavar='PACKAGE',
                            help='Batasi pada package_name tertentu (boleh diulang).')
        parser.add_argument('--extractor', default=None,
                            help="Nama ekstraktor (default: settings.EXTRACTION['ekstraktor']).")
        parser.add_argument('--batch-size', type=int, default=None, help='Ulasan per transaksi.')
        parser.add_argument('--batch-llm', type=int, default=None,
                            help='Ulasan per permintaan LLM (default settings.EXTRACTION["batch_llm"]=50).')
        parser.add_argument('--bintang-min', type=int, default=None, help='Hanya ulasan dengan bintang >= nilai ini.')
        parser.add_argument('--bintang-maks', type=int, default=None,
                            help='Hanya ulasan dengan bintang <= nilai ini (mis. 2 untuk ulasan negatif).')
        parser.add_argument('--ulangi-tanpa-kebutuhan', action='store_true',
                            help='Buka kembali ulasan yang ditandai "tanpa kebutuhan" (mis. setelah prompt diperbaiki) '
                                 'agar diekstraksi ulang.')
        parser.add_argument('--dry-run', action='store_true', help='Hitung saja, tanpa menyimpan.')

    def handle(self, *args, **opts):
        _siapkan_log_file()
        if opts['batch_llm']:
            settings.EXTRACTION['batch_llm'] = opts['batch_llm']
        try:
            ekstraktor = registry.get_ekstraktor(opts['extractor'])
        except ValueError as exc:
            raise CommandError(str(exc))

        if opts['ulangi_tanpa_kebutuhan'] and not opts['dry_run']:
            from reviews.models import Ulasan
            qs = Ulasan.objects.filter(alasan_filter=Ulasan.AlasanFilter.TANPA_KEBUTUHAN,
                                       hasil_ekstraksi_set__isnull=True)
            if opts['app']:
                qs = qs.filter(aplikasi__package_name__in=opts['app'])
            n = qs.update(status_filter=Ulasan.StatusFilter.LOLOS, alasan_filter='')
            self.stdout.write(f'{n} ulasan "tanpa kebutuhan" dibuka kembali.')

        r = runner.ekstrak_ulasan_baru(
            ekstraktor,
            batas=opts['limit'],
            aplikasi_pkg=opts['app'] or None,
            batch_size=opts['batch_size'] or settings.EXTRACTION['batch_size'],
            dry_run=opts['dry_run'],
            bintang_min=opts['bintang_min'], bintang_maks=opts['bintang_maks'],
        )
        logger.info('ekstraktor=%s diproses=%s hasil=%s tanpa_hasil=%s gagal=%s dry_run=%s',
                    ekstraktor.nama, r.diproses, r.hasil, r.tanpa_hasil, r.gagal, opts['dry_run'])
        self.stdout.write(self.style.SUCCESS(
            f'[{ekstraktor.nama}] diproses={r.diproses} hasil={r.hasil} '
            f'tanpa_hasil={r.tanpa_hasil} gagal={r.gagal}' + (' (dry-run)' if opts['dry_run'] else '')))
        if r.gagal:
            raise CommandError(f'{r.gagal} ulasan gagal diekstraksi. Lihat logs/extraction.log.')
