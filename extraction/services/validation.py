"""
Layanan validasi hasil ekstraksi dan cluster oleh peran Analyst (UC-2, FR-VAL-01 s/d FR-VAL-05).
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
    Status cluster -> TERVALIDASI (siap disusun menjadi User Story di UC-3).
    Status ekstraksi anggota -> TERVALIDASI.
    """
    if cluster.status_cluster == Cluster.StatusCluster.TERVALIDASI:
        raise ValidationError('Cluster sudah berstatus tervalidasi.')

    now = timezone.now()
    cluster.status_cluster = Cluster.StatusCluster.TERVALIDASI
    cluster.save(update_fields=['status_cluster'])

    for anggota in cluster.anggota_set.select_related('hasil_ekstraksi'):
        he = anggota.hasil_ekstraksi
        he.status_validasi = HasilEkstraksi.StatusValidasi.TERVALIDASI
        he.pengguna = validator_user if getattr(validator_user, 'is_authenticated', False) else None
        he.tanggal_validasi = now
        he.save(update_fields=['status_validasi', 'pengguna', 'tanggal_validasi'])

    return cluster


@transaction.atomic
def tolak_cluster(cluster: Cluster, validator_user=None) -> Cluster:
    """
    Menolak cluster dan menandai anggotanya DIHAPUS (FR-VAL-04, soft delete).
    Status cluster -> DIABAIKAN.
    Status ekstraksi anggota -> DIHAPUS.
    """
    now = timezone.now()
    cluster.status_cluster = Cluster.StatusCluster.DIABAIKAN
    cluster.save(update_fields=['status_cluster'])

    for anggota in cluster.anggota_set.select_related('hasil_ekstraksi'):
        he = anggota.hasil_ekstraksi
        he.status_validasi = HasilEkstraksi.StatusValidasi.DIHAPUS
        he.pengguna = validator_user if getattr(validator_user, 'is_authenticated', False) else None
        he.tanggal_validasi = now
        he.save(update_fields=['status_validasi', 'pengguna', 'tanggal_validasi'])

    return cluster

