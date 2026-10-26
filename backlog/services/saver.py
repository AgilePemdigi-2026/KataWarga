
"""Service fitur #9: menyimpan User Story ke Backlog."""

from django.db import transaction

from backlog.models import BacklogItem
from stories.models import UserStory


@transaction.atomic
def save_to_backlog(user_story):
    """
    Simpan User Story yang sudah disetujui ke backlog.

    Return:
        (backlog_item, created)
    """

    if user_story.status_persetujuan != (
        UserStory.StatusPersetujuan.DISETUJUI
    ):
        raise ValueError(
            "Hanya User Story yang disetujui "
            "yang boleh masuk backlog."
        )

    backlog_item, created = BacklogItem.objects.get_or_create(
        user_story=user_story,
        defaults={
            "status_eksekusi": (
                BacklogItem.StatusEksekusi.SIAP_DIEKSEKUSI
            ),
        },
    )

    return backlog_item, created
