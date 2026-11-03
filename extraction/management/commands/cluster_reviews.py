"""
Mengelompokkan hasil ekstraksi yang belum masuk ke dalam cluster (UC-1, FR-EKS-08, FR-EKS-09).

Contoh:
    python manage.py cluster_reviews --dry-run
    python manage.py cluster_reviews
    python manage.py cluster_reviews --threshold 0.5
"""
import logging
from django.core.management.base import BaseCommand
from extraction.services import clustering

logger = logging.getLogger('extraction.clustering')


class Command(BaseCommand):
    help = 'Kelompokkan hasil ekstraksi yang belum ber-cluster berdasarkan kemiripan semantik.'

    def add_arguments(self, parser):
        parser.add_argument('--threshold', type=float, default=None,
                            help='Ambang batas jarak kemiripan cosine (default: settings.CLUSTERING).')
        parser.add_argument('--dry-run', action='store_true',
                            help='Hitung dan simulasikan tanpa menyimpan ke basis data.')

    def handle(self, *args, **opts):
        r = clustering.kelompokkan_ekstraksi(
            distance_threshold=opts['threshold'],
            dry_run=opts['dry_run'],
        )

        msg = (
            f"Clustering selesai: {r.diproses} hasil ekstraksi diproses, "
            f"{r.cluster_baru} cluster {'disimulasikan' if opts['dry_run'] else 'berhasil dibuat'}."
        )
        logger.info(msg)
        self.stdout.write(self.style.SUCCESS(msg))

