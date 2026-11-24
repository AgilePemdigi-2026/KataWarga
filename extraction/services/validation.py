"""
Layanan validasi hasil ekstraksi dan cluster oleh peran Analyst (UC-2, FR-VAL-01 s/d FR-VAL-05).
Dilengkapi state machine guard dan penguncian transaksi (KW-04).
"""
from django.db import transaction
from django.utils import timezone
from extraction.models import Cluster, HasilEkstraksi, LogValidasi
from extraction.services.llm.verifikasi import susun_user_story


class ValidationError(Exception):
    pass


def _pengguna(user):
    return user if getattr(user, 'is_authenticated', False) else None


def _catat(jenis, objek_id, aksi, user, lama=None, baru=None, catatan=''):
    LogValidasi.objects.create(
        objek_jenis=jenis, objek_id=objek_id, aksi=aksi, pengguna=_pengguna(user),
        nilai_lama=lama, nilai_baru=baru, catatan=(catatan or '')[:500])


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
        if he.status_validasi == HasilEkstraksi.StatusValidasi.DIHAPUS:
            continue  # sudah ditolak satu per satu oleh analis
        he.status_validasi = HasilEkstraksi.StatusValidasi.TERVALIDASI
        he.pengguna = validator_user if getattr(validator_user, 'is_authenticated', False) else None
        he.tanggal_validasi = now
        he.save(update_fields=['status_validasi', 'pengguna', 'tanggal_validasi'])

    _catat('CLUSTER', cluster_locked.pk, LogValidasi.Aksi.SETUJUI, validator_user,
           lama={'status': 'MENUNGGU_VALIDASI'}, baru={'status': 'TERVALIDASI'})
    return cluster_locked


@transaction.atomic
def tolak_cluster(cluster: Cluster, validator_user=None, alasan: str = '') -> Cluster:
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

    _catat('CLUSTER', cluster_locked.pk, LogValidasi.Aksi.TOLAK, validator_user,
           lama={'status': 'MENUNGGU_VALIDASI'}, baru={'status': 'DIABAIKAN'}, catatan=alasan)
    return cluster_locked


# --------------------------------------------------------------------------- per user story (hasil ekstraksi)
def _kunci_ekstraksi(he):
    he = HasilEkstraksi.objects.select_for_update().get(pk=he.pk)
    if he.status_validasi != HasilEkstraksi.StatusValidasi.MENUNGGU_VALIDASI:
        raise ValidationError(
            f"Hanya user story berstatus 'Menunggu Validasi' yang dapat diubah. "
            f"Status saat ini: {he.get_status_validasi_display()}.")
    return he


def _nilai(he):
    return {'who': he.teks_who, 'what': he.teks_what, 'why': he.teks_why, 'story': he.kalimat_user_story}


def _perbarui_jumlah_cluster(he):
    from extraction.models import ClusterAnggota
    for ca in ClusterAnggota.objects.filter(hasil_ekstraksi=he).select_related('cluster'):
        c = ca.cluster
        c.jumlah_anggota = c.anggota_set.exclude(
            hasil_ekstraksi__status_validasi=HasilEkstraksi.StatusValidasi.DIHAPUS).count()
        c.save(update_fields=['jumlah_anggota'])


@transaction.atomic
def setujui_ekstraksi(he: HasilEkstraksi, validator_user=None, catatan: str = '') -> HasilEkstraksi:
    """Setujui satu user story (MENUNGGU_VALIDASI -> TERVALIDASI)."""
    he = _kunci_ekstraksi(he)
    he.status_validasi = HasilEkstraksi.StatusValidasi.TERVALIDASI
    he.pengguna = _pengguna(validator_user)
    he.tanggal_validasi = timezone.now()
    he.save(update_fields=['status_validasi', 'pengguna', 'tanggal_validasi'])
    _catat('EKSTRAKSI', he.pk, LogValidasi.Aksi.SETUJUI, validator_user, catatan=catatan)
    return he


@transaction.atomic
def tolak_ekstraksi(he: HasilEkstraksi, validator_user=None, alasan: str = '') -> HasilEkstraksi:
    """Tolak satu user story (soft delete: MENUNGGU_VALIDASI -> DIHAPUS)."""
    he = _kunci_ekstraksi(he)
    he.status_validasi = HasilEkstraksi.StatusValidasi.DIHAPUS
    he.pengguna = _pengguna(validator_user)
    he.tanggal_validasi = timezone.now()
    he.save(update_fields=['status_validasi', 'pengguna', 'tanggal_validasi'])
    _catat('EKSTRAKSI', he.pk, LogValidasi.Aksi.TOLAK, validator_user, catatan=alasan)
    _perbarui_jumlah_cluster(he)
    return he


@transaction.atomic
def perbaiki_ekstraksi(he: HasilEkstraksi, validator_user=None, *, who=None, what=None, why=None,
                       catatan: str = '') -> HasilEkstraksi:
    """
    Perbaiki WHO/WHAT/WHY oleh analis. Hanya field yang dikirim (bukan None) yang diubah; WHAT tidak boleh
    kosong; kalimat user story disusun ulang dari template. Perubahan dicatat (nilai lama -> baru).
    Status tetap MENUNGGU_VALIDASI (analis lalu menyetujui). Embedding WHAT dibuang bila WHAT berubah
    supaya dihitung ulang pada clustering berikutnya.
    """
    he = _kunci_ekstraksi(he)
    lama = _nilai(he)
    bersih = lambda t: ' '.join(str(t).split())  # noqa: E731
    who_b = bersih(who) if who is not None else he.teks_who
    what_b = bersih(what) if what is not None else he.teks_what
    why_b = bersih(why) if why is not None else he.teks_why
    if not what_b:
        raise ValidationError('WHAT tidak boleh kosong.')
    if len(who_b) > 100 or len(what_b) > 1000 or len(why_b) > 1000:
        raise ValidationError('Teks terlalu panjang (WHO maks. 100, WHAT/WHY maks. 1000 karakter).')
    if (who_b, what_b, why_b) == (he.teks_who, he.teks_what, he.teks_why):
        raise ValidationError('Tidak ada perubahan yang dikirim.')

    ubah_what = what_b != he.teks_what
    he.teks_who, he.teks_what, he.teks_why = who_b, what_b, why_b
    he.kalimat_user_story = susun_user_story(who_b or 'pengguna', what_b, why_b)
    kolom = ['teks_who', 'teks_what', 'teks_why', 'kalimat_user_story']
    if ubah_what:
        he.embedding_what, he.model_embedding = None, ''
        kolom += ['embedding_what', 'model_embedding']
    he.save(update_fields=kolom)
    _catat('EKSTRAKSI', he.pk, LogValidasi.Aksi.PERBAIKI, validator_user, lama=lama, baru=_nilai(he),
           catatan=catatan)
    return he
