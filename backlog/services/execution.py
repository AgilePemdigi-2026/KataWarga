
"""
Fitur #10 — Mengeksekusi Item Backlog.

Alur status:
SIAP_DIEKSEKUSI -> SEDANG_DIKERJAKAN -> SELESAI
"""

from django.db import transaction
from django.utils import timezone

from accounts.models import User
from backlog.models import BacklogItem


class BacklogExecutionError(Exception):
    """Error ketika eksekusi backlog tidak diperbolehkan."""
    pass


def validasi_developer(pengguna):
    """Pastikan pengguna login dan memiliki role Tim Developer."""
    if pengguna is None or not getattr(
        pengguna, "is_authenticated", False
    ):
        raise BacklogExecutionError(
            "Pengguna harus login terlebih dahulu."
        )

    if pengguna.role != User.RolePengguna.TIM_DEVELOPER:
        raise BacklogExecutionError(
            "Hanya Tim Developer yang boleh mengeksekusi backlog."
        )


@transaction.atomic
def mulai_kerjakan(backlog_item, pengguna):
    """
    Mengubah status:
    SIAP_DIEKSEKUSI -> SEDANG_DIKERJAKAN
    """
    validasi_developer(pengguna)

    item = BacklogItem.objects.select_for_update().get(
        pk=backlog_item.pk
    )

    if (
        item.status_eksekusi
        != BacklogItem.StatusEksekusi.SIAP_DIEKSEKUSI
    ):
        raise BacklogExecutionError(
            "Item backlog tidak berstatus SIAP_DIEKSEKUSI."
        )

    item.status_eksekusi = (
        BacklogItem.StatusEksekusi.SEDANG_DIKERJAKAN
    )
    item.pengguna = pengguna
    item.tanggal_mulai_dikerjakan = timezone.now()

    item.save(
        update_fields=[
            "status_eksekusi",
            "pengguna",
            "tanggal_mulai_dikerjakan",
        ]
    )

    return item


@transaction.atomic
def tandai_selesai(backlog_item, pengguna):
    """
    Mengubah status:
    SEDANG_DIKERJAKAN -> SELESAI
    """
    validasi_developer(pengguna)

    item = BacklogItem.objects.select_for_update().get(
        pk=backlog_item.pk
    )

    if (
        item.status_eksekusi
        != BacklogItem.StatusEksekusi.SEDANG_DIKERJAKAN
    ):
        raise BacklogExecutionError(
            "Item backlog belum berstatus SEDANG_DIKERJAKAN."
        )

    item.status_eksekusi = BacklogItem.StatusEksekusi.SELESAI
    item.tanggal_selesai = timezone.now()

    item.save(
        update_fields=[
            "status_eksekusi",
            "tanggal_selesai",
        ]
    )

    return item
