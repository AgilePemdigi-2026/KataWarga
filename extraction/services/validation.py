"""
Layanan validasi hasil ekstraksi dan cluster oleh peran Analyst (UC-2, FR-VAL-01 s/d FR-VAL-05).
Dilengkapi state machine guard dan penguncian transaksi (KW-04).
"""
from django.db import transaction
from django.utils import timezone
from extraction.models import Cluster, HasilEkstraksi


class ValidationError(Exception):
    pass


@transaction.atomic
def setujui_cluster(cluster: Cluster, validator_user=None) -> Cluster:
    """
    Menyetujui cluster dan seluruh anggota ekstraksinya (FR-VAL-03).
    Transisi yang diizinkan hanya dari MENUNGGU_VALIDASI -> TERVALIDASI.
    Status ekstraksi anggota -> TERVALIDASI.
    """
    # Ambil record terkini dengan row-level lock (KW-04)
    cluster_locked = Cluster.objects.select_for_update().get(pk=cluster.pk)

    if cluster_locked.status_cluster != Cluster.StatusCluster.MENUNGGU_VALIDASI:
        raise ValidationError(
            f"Hanya cluster berstatus 'Menunggu Validasi' yang dapat disetujui. "
            f"Status saat ini: {cluster_locked.get_status_cluster_display()}."
        )

    now = timezone.now()
    cluster_locked.status_cluster = Cluster.StatusCluster.TERVALIDASI
    cluster_locked.save(update_fields=['status_cluster'])

    for anggota in cluster_locked.anggota_set.select_related('hasil_ekstraksi'):
        he = anggota.hasil_ekstraksi
        he.status_validasi = HasilEkstraksi.StatusValidasi.TERVALIDASI
        he.pengguna = validator_user if getattr(validator_user, 'is_authenticated', False) else None
        he.tanggal_validasi = now
        he.save(update_fields=['status_validasi', 'pengguna', 'tanggal_validasi'])

    return cluster_locked


@transaction.atomic
def tolak_cluster(cluster: Cluster, validator_user=None) -> Cluster:
    """
    Menolak cluster dan menandai anggotanya DIHAPUS (FR-VAL-04, soft delete).
    Transisi yang diizinkan hanya dari MENUNGGU_VALIDASI -> DIABAIKAN.
    Status ekstraksi anggota -> DIHAPUS.
    """
    # Ambil record terkini dengan row-level lock (KW-04)
    cluster_locked = Cluster.objects.select_for_update().get(pk=cluster.pk)

    if cluster_locked.status_cluster != Cluster.StatusCluster.MENUNGGU_VALIDASI:
        raise ValidationError(
            f"Hanya cluster berstatus 'Menunggu Validasi' yang dapat ditolak. "
            f"Status saat ini: {cluster_locked.get_status_cluster_display()}."
        )

    now = timezone.now()
    cluster_locked.status_cluster = Cluster.StatusCluster.DIABAIKAN
    cluster_locked.save(update_fields=['status_cluster'])

    for anggota in cluster_locked.anggota_set.select_related('hasil_ekstraksi'):
        he = anggota.hasil_ekstraksi
        he.status_validasi = HasilEkstraksi.StatusValidasi.DIHAPUS
        he.pengguna = validator_user if getattr(validator_user, 'is_authenticated', False) else None
        he.tanggal_validasi = now
        he.save(update_fields=['status_validasi', 'pengguna', 'tanggal_validasi'])

    return cluster_locked
