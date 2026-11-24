"""
Management command untuk memperbarui nama_topik cluster lama menjadi ringkas dan representatif.

Prinsip proteksi data:
- Hanya memproses cluster berstatus MENUNGGU_VALIDASI yang belum disusun menjadi User Story.
- Tidak pernah mengubah status validasi atau menimpa cluster yang sudah disetujui Analyst.
- Tidak mengubah keanggotaan cluster, relasi anggota, atau jumlah anggota.
- Mendukung opsi --dry-run untuk simulasi tanpa perubahan basis data.
"""
from django.core.management.base import BaseCommand

from extraction.models import Cluster
from extraction.services.clustering import bentuk_label_topik


class Command(BaseCommand):
    help = "Perbarui nama_topik cluster lama menjadi ringkas dan representatif (aman & idempoten)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulasikan perubahan nama topik tanpa menyimpan ke basis data.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Batasi jumlah cluster yang diperbarui.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]

        # Proteksi database: hanya perbarui cluster yang otomatis, belum tervalidasi/diedit Analyst
        # (nama_topik_manual=False) dan belum disusun menjadi User Story.
        qs = (
            Cluster.objects
            .filter(
                status_cluster=Cluster.StatusCluster.MENUNGGU_VALIDASI,
                nama_topik_manual=False,
                user_story__isnull=True,
            )
            .prefetch_related("anggota_set__hasil_ekstraksi")
            .order_by("id")
        )

        if limit:
            qs = qs[:limit]

        total_diproses = 0
        total_diubah = 0

        for cluster in qs:
            total_diproses += 1
            anggota_pertama = cluster.anggota_set.first()
            if cluster.representatif_id:  # cluster embedding (Sprint 3 D): pakai story perwakilan
                teks_what = cluster.representatif.teks_what
                teks_why = cluster.representatif.teks_why
            elif anggota_pertama and anggota_pertama.hasil_ekstraksi:
                teks_what = anggota_pertama.hasil_ekstraksi.teks_what
                teks_why = anggota_pertama.hasil_ekstraksi.teks_why
            else:
                teks_what = cluster.nama_topik
                teks_why = ""

            label_baru = bentuk_label_topik(teks_what, teks_why)
            if label_baru and label_baru != cluster.nama_topik:
                self.stdout.write(
                    f"[Cluster #{cluster.pk}] '{cluster.nama_topik}' -> '{label_baru}'"
                )
                if not dry_run:
                    cluster.nama_topik = label_baru[:200]
                    cluster.save(update_fields=["nama_topik"])
                total_diubah += 1

        prefix = "[DRY-RUN] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Selesai: {total_diproses} cluster diperiksa, {total_diubah} label cluster diperbarui."
            )
        )
