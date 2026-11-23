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
    status_validasi = models.CharField(max_length=20, choices=StatusValidasi.choices, default=StatusValidasi.MENUNGGU_VALIDASI)
    pengguna = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='validasi_ekstraksi_set')
    tanggal_ekstraksi = models.DateTimeField(auto_now_add=True)
    tanggal_validasi = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Hasil Ekstraksi'
        verbose_name_plural = 'Hasil Ekstraksi'

    def __str__(self):
        return f"Ekstraksi #{self.pk}"


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
