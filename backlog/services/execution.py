
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


def validasi_developer(pengguna, role=None):
    """
    Pastikan pengguna login dan memiliki role efektif Tim Developer.

    ``role`` memungkinkan view meneruskan role simulasi development tanpa
    mengubah role asli pengguna di database.
    """
    if pengguna is None or not getattr(
        pengguna, "is_authenticated", False
    ):
        raise BacklogExecutionError(
            "Pengguna harus login terlebih dahulu."
        )

    peran_efektif = role or pengguna.role
    if peran_efektif != User.RolePengguna.TIM_DEVELOPER:
        raise BacklogExecutionError(
            "Hanya Tim Developer yang boleh mengeksekusi backlog."
        )


@transaction.atomic
def mulai_kerjakan(backlog_item, pengguna, *, role=None):
    """
    Mengubah status:
    SIAP_DIEKSEKUSI -> SEDANG_DIKERJAKAN
    """
    validasi_developer(pengguna, role=role)

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
def tandai_selesai(backlog_item, pengguna, *, role=None):
    """
    Mengubah status:
    SEDANG_DIKERJAKAN -> SELESAI
    """
    validasi_developer(pengguna, role=role)

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
