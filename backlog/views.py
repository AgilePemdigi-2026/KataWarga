from django.shortcuts import render

from backlog.models import BacklogItem


def backlog_list_view(request):
    """Menampilkan daftar User Story yang sudah masuk backlog."""

    backlog_items = (
        BacklogItem.objects
        .select_related("user_story", "pengguna")
        .order_by("-user_story__skor_prioritas")
    )

    return render(request, "backlog/list.html", {
        "backlog_items": backlog_items,
    })