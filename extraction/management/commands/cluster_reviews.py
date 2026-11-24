"""
Mengelompokkan hasil ekstraksi yang belum masuk ke dalam cluster (UC-1, FR-EKS-08, FR-EKS-09).

Metode default 'embedding' (Sprint 3 bagian D): embedding teks WHAT + agglomerative (cosine, average).
Metode 'tfidf' = baseline Sprint 2 (tanpa jaringan).

Contoh:
    python manage.py cluster_reviews --sweep 0.2,0.3,0.4,0.5      # kalibrasi ambang, tidak menyimpan cluster
    python manage.py cluster_reviews --dry-run --lihat            # simulasi + tampilkan isi cluster
    python manage.py cluster_reviews --threshold 0.35 --bangun-ulang
    python manage.py cluster_reviews --metode tfidf
"""
import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from extraction.services import clustering, clustering_embedding
from extraction.services.llm import LLMError

logger = logging.getLogger('extraction.clustering')


class Command(BaseCommand):
    help = 'Kelompokkan hasil ekstraksi yang belum ber-cluster berdasarkan kemiripan semantik.'

    def add_arguments(self, parser):
        parser.add_argument('--metode', choices=['embedding', 'tfidf'], default=None,
                            help="Default: settings.CLUSTERING['metode'].")
        parser.add_argument('--threshold', type=float, default=None,
                            help='Ambang jarak cosine (default: settings.CLUSTERING; berbeda per metode).')
        parser.add_argument('--sweep', default=None, metavar='A,B,C',
                            help='Daftar ambang untuk dibandingkan (metode embedding). Tidak menyimpan cluster.')
        parser.add_argument('--bangun-ulang', action='store_true',
                            help='Hapus cluster MENUNGGU_VALIDASI lalu kelompokkan ulang (metode embedding).')
        parser.add_argument('--pusatkan', action='store_true', default=None,
                            help='Pusatkan embedding (kurangi vektor rata-rata) sebelum cosine; kalibrasi ulang ambang dengan --sweep.')
        parser.add_argument('--lihat', action='store_true', help='Tampilkan isi tiap cluster (metode embedding).')
        parser.add_argument('--dry-run', action='store_true',
                            help='Simulasikan tanpa menyimpan cluster (cache embedding tetap disimpan).')

    def handle(self, *args, **opts):
        metode = opts['metode'] or settings.CLUSTERING.get('metode', 'embedding')
        if metode == 'tfidf':
            r = clustering.kelompokkan_ekstraksi(distance_threshold=opts['threshold'], dry_run=opts['dry_run'])
            msg = (f"Clustering [tfidf] selesai: {r.diproses} hasil ekstraksi diproses, "
                   f"{r.cluster_baru} cluster {'disimulasikan' if opts['dry_run'] else 'berhasil dibuat'}.")
            logger.info(msg)
            self.stdout.write(self.style.SUCCESS(msg))
            return

        try:
            if opts['sweep']:
                try:
                    ambang = [float(x) for x in opts['sweep'].split(',') if x.strip()]
                except ValueError:
                    raise CommandError('--sweep harus berupa angka dipisah koma, mis. 0.2,0.3,0.4')
                self.stdout.write('ambang | cluster | singleton | terbesar | silhouette')
                for b in clustering_embedding.sweep(ambang, pusat=opts['pusatkan']):
                    sil = '-' if b['silhouette'] is None else f"{b['silhouette']:.3f}"
                    self.stdout.write(f"{b['ambang']:<6} | {b['cluster']:<7} | {b['singleton']:<9} | "
                                      f"{b['ukuran_maks']:<8} | {sil}")
                return
            r = clustering_embedding.kelompokkan_embedding(
                distance_threshold=opts['threshold'], dry_run=opts['dry_run'], bangun_ulang=opts['bangun_ulang'],
                pusat=opts['pusatkan'])
        except LLMError as exc:
            raise CommandError(f'Embedding gagal: {type(exc).__name__}: {exc}')

        if opts['lihat']:
            for c in r.ringkasan:
                self.stdout.write(f"\n[{c['ukuran']} anggota, rata jarak {c['rata_jarak']}] {c['representatif']}")
                for a in c['anggota']:
                    self.stdout.write(f'    - {a}')
        sil = 'n/a' if r.silhouette is None else f'{r.silhouette:.3f}'
        msg = (f"Clustering [embedding] ambang={r.ambang}: {r.diproses} hasil diproses "
               f"({r.embedding_baru} embedding baru), {r.cluster_baru} cluster "
               f"{'disimulasikan' if opts['dry_run'] else 'dibuat'}, {r.singleton} singleton, "
               f"terbesar {r.ukuran_maks}, silhouette {sil}"
               + (f", {r.cluster_dihapus} cluster lama dihapus" if r.cluster_dihapus else '') + '.')
        logger.info(msg)
        self.stdout.write(self.style.SUCCESS(msg))
