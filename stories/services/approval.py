"""
Layanan persetujuan dan validasi user story oleh Product Owner (§6.4, FR-APP-01 s/d 04, FR-SIM-04).
"""
import importlib
import logging
from django.db import transaction
from django.utils import timezone
from stories.models import UserStory

logger = logging.getLogger(__name__)


class ApprovalError(Exception):
    """Exception khusus saat validasi atau penyimpanan persetujuan gagal."""
    pass


def setujui_user_story(user_story, validator_user=None):
    """
    Setujui user story dalam transaksi atomik (§6.4, FR-APP-03, FR-SIM-04).
    1. Update status_persetujuan -> DISETUJUI
    2. Catat tanggal_persetujuan & validator_user (jika ada)
    3. Panggil hook backlog.services.saver.save_to_backlog(user_story) jika ada.
       Jika hook gagal, rollback transaksi secara penuh.
    """
    with transaction.atomic():
        user_story.status_persetujuan = UserStory.StatusPersetujuan.DISETUJUI
        user_story.tanggal_persetujuan = timezone.now()
        if validator_user and getattr(validator_user, 'is_authenticated', False):
            user_story.pengguna = validator_user
        user_story.save()

        # Panggil hook integrasi backlog (#9) secara dinamis
        try:
            saver_mod = importlib.import_module('backlog.services.saver')
            save_fn = getattr(saver_mod, 'save_to_backlog', None)
            if callable(save_fn):
                save_fn(user_story)
            else:
                logger.warning("Fungsi backlog.services.saver.save_to_backlog belum diimplementasikan (Sprint 1 Backlog #9).")
        except ModuleNotFoundError:
            logger.warning("Modul backlog.services.saver belum ada (Sprint 1 Backlog #9). Melanjutkan tanpa pembuatan item backlog.")
        except Exception as e:
            logger.error(f"Gagal menyimpan ke backlog: {e}")
            raise ApprovalError(f"Gagal menyimpan ke backlog: {e}") from e

    return user_story


def abaikan_user_story(user_story, alasan=''):
    """
    Tolak/abaikan user story (§6.4, FR-APP-04).
    Update status_persetujuan -> DIABAIKAN dan catat alasan_diabaikan (opsional).
    """
    user_story.status_persetujuan = UserStory.StatusPersetujuan.DIABAIKAN
    user_story.alasan_diabaikan = (alasan or '').strip()
    user_story.save(update_fields=['status_persetujuan', 'alasan_diabaikan'])
    return user_story
