
"""
Layanan persetujuan dan validasi User Story oleh Product Owner.

Fitur #8: Persetujuan User Story
Fitur #9: Menyimpan User Story ke Backlog
"""

from django.db import transaction
from django.utils import timezone

from backlog.services.saver import save_to_backlog
from stories.models import UserStory


class ApprovalError(Exception):
    """Error saat persetujuan atau penyimpanan backlog gagal."""
    pass


def setujui_user_story(user_story, validator_user=None):
    """
    Menyetujui User Story dan menyimpannya ke backlog.

    Alur:
    1. Mengubah status User Story menjadi DISETUJUI.
    2. Mencatat tanggal persetujuan dan Product Owner.
    3. Menyimpan User Story ke BacklogItem.
    4. Rollback seluruh transaksi jika penyimpanan gagal.
    """
    with transaction.atomic():
        user_story.status_persetujuan = (
            UserStory.StatusPersetujuan.DISETUJUI
        )
        user_story.tanggal_persetujuan = timezone.now()

        if validator_user and getattr(
            validator_user, "is_authenticated", False
        ):
            user_story.pengguna = validator_user

        user_story.save()

        try:
            save_to_backlog(user_story)
        except Exception as exc:
            raise ApprovalError(
                f"Gagal menyimpan User Story ke backlog: {exc}"
            ) from exc

    return user_story


def abaikan_user_story(user_story, alasan=""):
    """
    Mengabaikan User Story.

    Mengubah status menjadi DIABAIKAN
    dan mencatat alasan pengabaian.
    """
    user_story.status_persetujuan = (
        UserStory.StatusPersetujuan.DIABAIKAN
    )

    user_story.alasan_diabaikan = (alasan or "").strip()

    user_story.save(
        update_fields=[
            "status_persetujuan",
            "alasan_diabaikan",
        ]
    )

    return user_story
