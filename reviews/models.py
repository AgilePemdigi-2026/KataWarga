"""Model Aplikasi dan Ulasan (§5)."""
from django.db import models


class Aplikasi(models.Model):
    nama_aplikasi = models.CharField(max_length=100)
    package_name = models.CharField(max_length=150, unique=True)
    kategori = models.CharField(max_length=100, blank=True, default='')
    aktif = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Aplikasi'
        verbose_name_plural = 'Aplikasi'

    def __str__(self):
        return self.nama_aplikasi


class Ulasan(models.Model):
    class StatusFilter(models.TextChoices):
        LOLOS = 'LOLOS', 'Lolos'
        DIBUANG = 'DIBUANG', 'Dibuang'

    aplikasi = models.ForeignKey(Aplikasi, on_delete=models.CASCADE, related_name='ulasan_set')
    # ID ulasan dari Play Store (reviewId). Kunci pencegah duplikat (FR-EKS-04);
    # kosong (NULL) untuk data dummy/unggahan CSV. # USULAN: kolom tambahan di luar ERD SRS
    review_id = models.CharField(max_length=100, null=True, blank=True, default=None)
    username_reviewer = models.CharField(max_length=150, blank=True, default='')
    isi_ulasan = models.TextField()
    tanggal_ulasan = models.DateField()
    skor_bintang = models.PositiveSmallIntegerField()
    status_filter = models.CharField(max_length=20, choices=StatusFilter.choices, default=StatusFilter.LOLOS)
    tanggal_scraping = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ulasan'
        verbose_name_plural = 'Ulasan'
        constraints = [
            models.UniqueConstraint(
                fields=['aplikasi', 'review_id'],
                condition=models.Q(review_id__isnull=False),
                name='uniq_ulasan_aplikasi_review_id',
            ),
        ]

    def __str__(self):
        return f"Ulasan {self.aplikasi} - {self.skor_bintang}★"
