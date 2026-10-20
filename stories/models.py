"""Model UserStory (§5)."""
from django.conf import settings
from django.db import models


class UserStory(models.Model):
    class StatusPersetujuan(models.TextChoices):
        MENUNGGU_PERSETUJUAN = 'MENUNGGU_PERSETUJUAN', 'Menunggu Persetujuan'
        DISETUJUI = 'DISETUJUI', 'Disetujui'
        DIABAIKAN = 'DIABAIKAN', 'Diabaikan'

    class LevelPrioritas(models.TextChoices):
        TINGGI = 'TINGGI', 'Tinggi'
        SEDANG = 'SEDANG', 'Sedang'
        RENDAH = 'RENDAH', 'Rendah'

    cluster = models.OneToOneField(
        'extraction.Cluster', on_delete=models.CASCADE, related_name='user_story',
    )
    peran = models.CharField(max_length=200)
    kebutuhan = models.CharField(max_length=1000)
    alasan = models.CharField(max_length=1000, blank=True, default='')
    skor_prioritas = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    kategori_prioritas = models.CharField(max_length=10, choices=LevelPrioritas.choices, default=LevelPrioritas.RENDAH)
    status_persetujuan = models.CharField(max_length=25, choices=StatusPersetujuan.choices, default=StatusPersetujuan.MENUNGGU_PERSETUJUAN)
    pengguna = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='user_story_disetujui_set')
    alasan_diabaikan = models.CharField(max_length=500, blank=True, default='')
    tanggal_disusun = models.DateTimeField(auto_now_add=True)
    tanggal_persetujuan = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'User Story'
        verbose_name_plural = 'User Story'
        ordering = ['-skor_prioritas']

    def __str__(self):
        return f"Sebagai {self.peran}, saya ingin {self.kebutuhan[:50]}..."

    @property
    def kalimat(self):
        s = f"Sebagai {self.peran}, saya ingin {self.kebutuhan}"
        if self.alasan:
            s += f", supaya {self.alasan}"
        return s
