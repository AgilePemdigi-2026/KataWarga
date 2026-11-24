"""Model HasilEkstraksi, Cluster, ClusterAnggota (§5)."""
from django.conf import settings
from django.db import models


class HasilEkstraksi(models.Model):
    class StatusValidasi(models.TextChoices):
        MENUNGGU_VALIDASI = 'MENUNGGU_VALIDASI', 'Menunggu Validasi'
        TERVALIDASI = 'TERVALIDASI', 'Tervalidasi'
        DIHAPUS = 'DIHAPUS', 'Dihapus'

    ulasan = models.ForeignKey('reviews.Ulasan', on_delete=models.CASCADE, related_name='hasil_ekstraksi_set')
    teks_who = models.CharField(max_length=100, blank=True, default='')
    teks_what = models.CharField(max_length=1000)
    teks_why = models.CharField(max_length=1000, blank=True, default='')
    skor_confidence = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    # Metadata ekstraksi LLM (Sprint 3 bagian C). Kosong untuk ekstraktor aturan.
    kalimat_user_story = models.TextField(blank=True, default='')  # "As a ..., I want to ..., so that ..."
    evidence = models.TextField(blank=True, default='')            # kutipan dari ulasan yang mendukung
    evidence_why = models.TextField(blank=True, default='')        # kutipan yang menjadi dasar WHY (kosong bila WHY kosong)
    sentimen = models.CharField(max_length=20, blank=True, default='')
    nama_ekstraktor = models.CharField(max_length=30, blank=True, default='')
    model_llm = models.CharField(max_length=60, blank=True, default='')
    versi_prompt = models.CharField(max_length=20, blank=True, default='')
    # Embedding teks WHAT (bagian D), disimpan agar tidak memanggil API berulang. L2-normalized.
    embedding_what = models.JSONField(null=True, blank=True, default=None)
    model_embedding = models.CharField(max_length=60, blank=True, default='')
    status_validasi = models.CharField(max_length=20, choices=StatusValidasi.choices, default=StatusValidasi.MENUNGGU_VALIDASI)
    pengguna = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='validasi_ekstraksi_set')
    tanggal_ekstraksi = models.DateTimeField(auto_now_add=True)
    tanggal_validasi = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Hasil Ekstraksi'
        verbose_name_plural = 'Hasil Ekstraksi'

    def __str__(self):
        return f"Ekstraksi #{self.pk}"


class GalatEkstraksi(models.Model):
    """Log kegagalan ekstraksi/verifikasi, agar tidak ada hasil yang hilang diam-diam."""
    ulasan = models.ForeignKey('reviews.Ulasan', on_delete=models.CASCADE, null=True, blank=True,
                               related_name='galat_ekstraksi_set')
    nama_ekstraktor = models.CharField(max_length=30, blank=True, default='')
    versi_prompt = models.CharField(max_length=20, blank=True, default='')
    jenis = models.CharField(max_length=40)   # mis. LLMTimeoutError, evidence_tidak_ditemukan
    pesan = models.TextField(blank=True, default='')
    tanggal = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Galat Ekstraksi'
        verbose_name_plural = 'Galat Ekstraksi'

    def __str__(self):
        return f"{self.jenis} (ulasan {self.ulasan_id})"


class Cluster(models.Model):
    class StatusCluster(models.TextChoices):
        MENUNGGU_VALIDASI = 'MENUNGGU_VALIDASI', 'Menunggu Validasi'
        TERVALIDASI = 'TERVALIDASI', 'Tervalidasi'
        SIGNIFIKAN = 'SIGNIFIKAN', 'Signifikan'
        DIABAIKAN = 'DIABAIKAN', 'Diabaikan'

    nama_topik = models.CharField(max_length=200)
    nama_topik_manual = models.BooleanField(
        default=False,
        help_text="Menandai apakah label nama topik diubah atau ditentukan secara manual oleh analis/admin.",
    )
    jumlah_anggota = models.PositiveIntegerField(default=0)
    skor_signifikansi = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    status_cluster = models.CharField(max_length=20, choices=StatusCluster.choices, default=StatusCluster.MENUNGGU_VALIDASI)
    tanggal_dibuat = models.DateTimeField(auto_now_add=True)
    # Bagian D: hasil ekstraksi yang paling mewakili cluster (terdekat ke centroid) + parameter pembentukan.
    representatif = models.ForeignKey('HasilEkstraksi', on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='+')
    metode = models.CharField(max_length=20, blank=True, default='')
    ambang_jarak = models.FloatField(null=True, blank=True)
    rata_jarak = models.FloatField(null=True, blank=True)  # rata-rata jarak cosine antar-anggota (kohesi)

    class Meta:
        verbose_name = 'Cluster'
        verbose_name_plural = 'Cluster'

    def __str__(self):
        return f"Cluster: {self.nama_topik}"


class ClusterAnggota(models.Model):
    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE, related_name='anggota_set')
    hasil_ekstraksi = models.ForeignKey(HasilEkstraksi, on_delete=models.CASCADE, related_name='cluster_set')
    tanggal_cluster_anggota = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Anggota Cluster'
        verbose_name_plural = 'Anggota Cluster'
        unique_together = ('cluster', 'hasil_ekstraksi')

    def __str__(self):
        return f"Cluster {self.cluster_id} ← Ekstraksi {self.hasil_ekstraksi_id}"


class LogValidasi(models.Model):
    """Jejak audit tindakan analis: siapa, kapan, apa yang diubah (nilai lama -> baru)."""
    class Aksi(models.TextChoices):
        SETUJUI = 'SETUJUI', 'Setujui'
        TOLAK = 'TOLAK', 'Tolak'
        PERBAIKI = 'PERBAIKI', 'Perbaiki'

    class Objek(models.TextChoices):
        EKSTRAKSI = 'EKSTRAKSI', 'Hasil Ekstraksi'
        CLUSTER = 'CLUSTER', 'Cluster'

    objek_jenis = models.CharField(max_length=12, choices=Objek.choices)
    objek_id = models.PositiveIntegerField()
    aksi = models.CharField(max_length=10, choices=Aksi.choices)
    pengguna = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='log_validasi_set')
    nilai_lama = models.JSONField(null=True, blank=True)
    nilai_baru = models.JSONField(null=True, blank=True)
    catatan = models.CharField(max_length=500, blank=True, default='')
    tanggal = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Log Validasi'
        verbose_name_plural = 'Log Validasi'
        ordering = ['-tanggal', '-id']
        indexes = [models.Index(fields=['objek_jenis', 'objek_id'])]

    def __str__(self):
        return f"{self.aksi} {self.objek_jenis} #{self.objek_id}"
