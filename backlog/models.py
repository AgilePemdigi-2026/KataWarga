
"""Model BacklogItem untuk fitur #9 dan #10."""

from django.conf import settings
from django.db import models


class BacklogItem(models.Model):

    class StatusEksekusi(models.TextChoices):
        SIAP_DIEKSEKUSI = (
            "SIAP_DIEKSEKUSI",
            "Siap Dieksekusi",
        )
        SEDANG_DIKERJAKAN = (
            "SEDANG_DIKERJAKAN",
            "Sedang Dikerjakan",
        )
        SELESAI = (
            "SELESAI",
            "Selesai",
        )

    user_story = models.OneToOneField(
        "stories.UserStory",
        on_delete=models.CASCADE,
        related_name="backlog_item",
    )

    status_eksekusi = models.CharField(
        max_length=25,
        choices=StatusEksekusi.choices,
        default=StatusEksekusi.SIAP_DIEKSEKUSI,
    )

    pengguna = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="backlog_dikerjakan_set",
    )

    tanggal_masuk_backlog = models.DateTimeField(
        auto_now_add=True,
    )

    tanggal_mulai_dikerjakan = models.DateTimeField(
        null=True,
        blank=True,
    )

    tanggal_selesai = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Item Backlog"
        verbose_name_plural = "Item Backlog"
        ordering = [
            "-user_story__skor_prioritas",
            "tanggal_masuk_backlog",
        ]

    def __str__(self):
        return (
            f"Backlog #{self.pk} - "
            f"{self.user_story.kebutuhan[:50]}"
        )
